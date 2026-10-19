"""Catalog queries: product listing (filters, search, sort, pagination), detail, categories, policies.

Routes in app/api/products.py stay thin and call these functions. The AI agent's product
search (phase 8) will reuse them, so the website and the agent always agree.
"""

import math
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import ColumnElement, Select, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.errors import APIError
from app.models import Order, OrderItem, OrderStatus, Policy, Product, ProductImage, ProductVariant

SortOption = Literal["best_selling", "newest", "price_asc", "price_desc", "name_asc"]

# Display order for the shop. Categories not listed here are shown after these, A-Z.
CATEGORY_ORDER = ["Tops", "Bottoms", "Outerwear", "Footwear", "Accessories", "Gift Cards"]
LETTER_SIZES = ["XXS", "XS", "S", "M", "L", "XL", "XXL"]
RELATED_LIMIT = 4
# Orders that never completed don't count as sales.
UNSOLD_STATUSES = (OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED)


class ProductListQuery(BaseModel):
    category: str | None = Field(None, max_length=60)  # category *slug*, e.g. "gift-cards"
    q: str | None = Field(None, max_length=100)
    # A merchandising tag, e.g. "new" or "autumn-edit" (lowercase letters, digits, hyphens).
    tag: str | None = Field(None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=40)
    size: list[str] = Field(default_factory=list, max_length=20)
    color: list[str] = Field(default_factory=list, max_length=20)
    min_price: int | None = Field(None, ge=0)  # cents
    max_price: int | None = Field(None, ge=0)  # cents
    sort: SortOption = "best_selling"
    page: int = Field(1, ge=1)
    per_page: int = Field(12, ge=1, le=48)

    @model_validator(mode="after")
    def _price_range_is_valid(self) -> "ProductListQuery":
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price must not be greater than max_price")
        return self


# --- helpers ----------------------------------------------------------------------------------


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def size_sort_key(size: str) -> tuple[int, float, str]:
    """Sort sizes the way a shopper expects: XS < S < M, 28 < 30, US 7 < US 10, $25 < $100."""
    if size in LETTER_SIZES:
        return (0, LETTER_SIZES.index(size), size)
    number = re.search(r"\d+(?:\.\d+)?", size)
    if number is None:
        return (4, 0, size)  # "One size"
    group = 2 if size.startswith("US") else 3 if size.startswith("$") else 1
    return (group, float(number.group()), size)


def escape_like(text: str) -> str:
    """Make % and _ in user input match literally instead of acting as LIKE wildcards."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))  # keeps first-seen order


def _active_category_names(session: Session) -> list[str]:
    names = session.scalars(select(Product.category).where(Product.is_active).distinct())
    order = {name: index for index, name in enumerate(CATEGORY_ORDER)}
    return sorted(names, key=lambda name: (order.get(name, len(order)), name))


def _category_name_for_slug(session: Session, slug: str) -> str:
    for name in _active_category_names(session):
        if slugify(name) == slug:
            return name
    raise APIError("category_not_found", f"No category called '{slug}'.", 404)


# --- product listing --------------------------------------------------------------------------


def list_products(session: Session, query: ProductListQuery) -> dict[str, Any]:
    category = _category_name_for_slug(session, query.category) if query.category else None

    # Facets use only category + tag + search, so choosing "M" doesn't hide the other sizes.
    base_filters = _base_filters(category, query.q, query.tag)
    filters = base_filters + _variant_and_price_filters(query)

    total = session.scalar(select(func.count()).select_from(Product).where(*filters)) or 0

    stmt = (
        _sorted(select(Product).where(*filters), query.sort)
        # 1 extra query each for ALL variants and ALL images, not 1 per product (the N+1 problem)
        .options(selectinload(Product.variants), selectinload(Product.images))
        .limit(query.per_page)
        .offset((query.page - 1) * query.per_page)
    )
    products = session.scalars(stmt).all()

    return {
        "items": [product_summary(product) for product in products],
        "page": query.page,
        "per_page": query.per_page,
        "total": total,
        "total_pages": math.ceil(total / query.per_page),
        "facets": _facets(session, base_filters),
    }


def _base_filters(category: str | None, q: str | None, tag: str | None = None) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [Product.is_active]
    if category:
        filters.append(Product.category == category)
    if tag:
        filters.append(Product.tags.contains([tag]))  # tags @> '{new}': can use the GIN index
    if q:
        # ILIKE = case-insensitive LIKE. Fine for a catalog this size; a big catalog would
        # use Postgres full-text search or a trigram index instead.
        pattern = f"%{escape_like(q)}%"
        filters.append(
            or_(
                Product.name.ilike(pattern, escape="\\"),
                Product.description.ilike(pattern, escape="\\"),
                Product.category.ilike(pattern, escape="\\"),
            )
        )
    return filters


def _variant_and_price_filters(query: ProductListQuery) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if query.size or query.color:
        # One EXISTS for both, so size and color must match the SAME in-stock variant:
        # "M in Black" must not match a product that only has M in White and L in Black.
        conditions = [ProductVariant.product_id == Product.id, ProductVariant.stock > 0]
        if query.size:
            conditions.append(ProductVariant.size.in_(query.size))
        if query.color:
            conditions.append(ProductVariant.color.in_(query.color))
        filters.append(exists().where(*conditions))
    if query.min_price is not None:
        filters.append(Product.price_cents >= query.min_price)
    if query.max_price is not None:
        filters.append(Product.price_cents <= query.max_price)
    return filters


def _units_sold() -> Any:
    """Subquery: product_id -> total units sold in completed orders."""
    return (
        select(ProductVariant.product_id, func.sum(OrderItem.quantity).label("units"))
        .join(OrderItem, OrderItem.variant_id == ProductVariant.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status.not_in(UNSOLD_STATUSES))
        .group_by(ProductVariant.product_id)
        .subquery()
    )


def _sorted(stmt: Select[tuple[Product]], sort: SortOption) -> Select[tuple[Product]]:
    # Every sort ends with Product.id so the order is stable: without a unique tie-breaker,
    # Postgres may return tied rows in a different order on each page, and items can repeat.
    if sort == "best_selling":
        sold = _units_sold()
        return stmt.outerjoin(sold, sold.c.product_id == Product.id).order_by(
            func.coalesce(sold.c.units, 0).desc(), Product.id
        )
    if sort == "newest":
        return stmt.order_by(Product.created_at.desc(), Product.id.desc())
    if sort == "price_asc":
        return stmt.order_by(Product.price_cents, Product.id)
    if sort == "price_desc":
        return stmt.order_by(Product.price_cents.desc(), Product.id)
    return stmt.order_by(Product.name, Product.id)


def _facets(session: Session, base_filters: list[ColumnElement[bool]]) -> dict[str, Any]:
    """The filter options that exist for this category/search: sizes, colors and price range."""
    pairs = session.execute(
        select(ProductVariant.size, ProductVariant.color)
        .join(Product)
        .where(*base_filters, ProductVariant.stock > 0)
        .distinct()
    ).all()
    low, high = session.execute(
        select(func.min(Product.price_cents), func.max(Product.price_cents)).where(*base_filters)
    ).one()
    return {
        "sizes": sorted({size for size, _ in pairs}, key=size_sort_key),
        "colors": sorted({color for _, color in pairs}),
        "price_min_cents": low,
        "price_max_cents": high,
    }


# --- serializers ------------------------------------------------------------------------------


def product_summary(product: Product) -> dict[str, Any]:
    """The fields a product card needs. Expects product.variants and product.images to be loaded already."""
    prices = [variant.effective_price_cents for variant in product.variants] or [product.price_cents]
    return {
        "slug": product.slug,
        "name": product.name,
        "category": product.category,
        "category_slug": slugify(product.category),
        "price_cents": product.price_cents,
        "price_min_cents": min(prices),
        "price_max_cents": max(prices),
        "image_url": product.image_url,
        "is_final_sale": product.is_final_sale,
        "in_stock": any(variant.stock > 0 for variant in product.variants),
        "colors": _unique([variant.color for variant in product.variants]),
        "tags": product.tags,
        # Already in gallery order. Products whose photos aren't ready yet get [] and the
        # site shows a placeholder.
        "images": [image_dict(image) for image in product.images],
    }


def image_dict(image: ProductImage) -> dict[str, Any]:
    return {"url": image.url, "alt_text": image.alt_text, "kind": image.kind, "color": image.color}


def get_product(session: Session, slug: str) -> dict[str, Any]:
    product = session.scalars(
        select(Product)
        .where(Product.slug == slug, Product.is_active)
        .options(selectinload(Product.variants), selectinload(Product.images))
    ).one_or_none()
    if product is None:
        raise APIError("product_not_found", f"No product called '{slug}'.", 404)

    related = session.scalars(
        _sorted(
            select(Product).where(
                Product.is_active, Product.category == product.category, Product.id != product.id
            ),
            "best_selling",
        )
        .options(selectinload(Product.variants), selectinload(Product.images))
        .limit(RELATED_LIMIT)
    ).all()

    return {
        **product_summary(product),
        "description": product.description,
        "fit_notes": product.fit_notes,
        "material_care": product.material_care,
        "restock_note": product.restock_note,
        "sizes": sorted(_unique([variant.size for variant in product.variants]), key=size_sort_key),
        "variants": [
            {
                "id": variant.id,
                "sku": variant.sku,
                "size": variant.size,
                "color": variant.color,
                "stock": variant.stock,
                "price_cents": variant.effective_price_cents,
                "in_stock": variant.stock > 0,
            }
            for variant in product.variants
        ],
        "related": [product_summary(item) for item in related],
    }


# --- categories and policies ------------------------------------------------------------------


def list_categories(session: Session) -> list[dict[str, Any]]:
    counts = dict(
        session.execute(
            select(Product.category, func.count()).where(Product.is_active).group_by(Product.category)
        ).all()
    )
    return [
        {"name": name, "slug": slugify(name), "product_count": counts[name]}
        for name in _active_category_names(session)
    ]


def policy_dict(policy: Policy) -> dict[str, Any]:
    return {
        "key": policy.key,
        "title": policy.title,
        "summary": policy.summary,
        "body": policy.body,
        "updated_at": policy.updated_at.isoformat(),
    }


def list_policies(session: Session) -> list[dict[str, Any]]:
    return [policy_dict(policy) for policy in session.scalars(select(Policy).order_by(Policy.id))]


def get_policy(session: Session, key: str) -> dict[str, Any]:
    policy = session.scalars(select(Policy).where(Policy.key == key)).one_or_none()
    if policy is None:
        raise APIError("policy_not_found", f"No policy called '{key}'.", 404)
    return policy_dict(policy)
