"""Products and their sellable variants (one row per size + color)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.types import CreatedAt, ImageKind, IntPK, enum_column


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="price_not_negative"),
        # GIN indexes the array's *elements*, so "tags contains 'new'" (tags @> '{new}') uses it.
        Index("ix_products_tags", "tags", postgresql_using="gin"),
    )

    id: Mapped[IntPK]
    slug: Mapped[str] = mapped_column(String(120), unique=True)  # URL name: /products/<slug>
    name: Mapped[str] = mapped_column(String(160))
    # A plain column rather than a categories table: six fixed names, no extra data per category.
    category: Mapped[str] = mapped_column(String(60), index=True)
    description: Mapped[str] = mapped_column(Text)
    fit_notes: Mapped[str | None] = mapped_column(Text)
    material_care: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int]  # integer cents: 2400 means $24.00; floats can't store money exactly
    is_final_sale: Mapped[bool] = mapped_column(default=False, server_default="false")
    restock_note: Mapped[str | None] = mapped_column(String(200))
    image_url: Mapped[str | None] = mapped_column(String(500))
    # Merchandising labels such as "new", "bestseller", "autumn-edit". They drive the homepage
    # sections, so editing tags in the admin changes the homepage without a code change.
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list, server_default="{}")
    # Products are deactivated, never deleted: old order items still point at their variants.
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[CreatedAt]

    variants: Mapped[list[ProductVariant]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductVariant.id"
    )
    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.position, ProductImage.id"
    )

    def __repr__(self) -> str:
        return f"<Product {self.slug}>"


class ProductVariant(db.Model):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "size", "color", name="uq_product_variants_product_size_color"),
        # The last line of defence against overselling: the database refuses negative stock,
        # even if two checkouts race for the last item (phase 4).
        CheckConstraint("stock >= 0", name="stock_not_negative"),
        CheckConstraint("price_cents IS NULL OR price_cents >= 0", name="price_not_negative"),
    )

    id: Mapped[IntPK]
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    sku: Mapped[str] = mapped_column(String(40), unique=True)  # stock keeping unit: KO-001-WHIT-M
    size: Mapped[str] = mapped_column(String(20))
    color: Mapped[str] = mapped_column(String(40))
    stock: Mapped[int] = mapped_column(default=0, server_default="0")
    # NULL means "use the product's price". Only gift cards override it ($25 / $50 / $100).
    price_cents: Mapped[int | None]

    product: Mapped[Product] = relationship(back_populates="variants")

    @property
    def effective_price_cents(self) -> int:
        return self.price_cents if self.price_cents is not None else self.product.price_cents

    def __repr__(self) -> str:
        return f"<ProductVariant {self.sku} stock={self.stock}>"


class ProductImage(db.Model):
    """One photo of a product. Rows for files in public/images/products are written by
    `flask images sync` from backend/seed/image-manifest.json (see app/images.py)."""

    __tablename__ = "product_images"

    id: Mapped[IntPK]
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    # The variant colour this photo shows, e.g. "Sky Blue". NULL for a lifestyle photo,
    # which belongs to the product as a whole.
    color: Mapped[str | None] = mapped_column(String(40))
    kind: Mapped[ImageKind] = mapped_column(enum_column(ImageKind, "image_kind"))
    # One file = one row: the sync command uses the URL to find a photo's existing row.
    url: Mapped[str] = mapped_column(String(500), unique=True)
    alt_text: Mapped[str] = mapped_column(String(300))
    position: Mapped[int] = mapped_column(default=0, server_default="0")  # gallery order, lowest first

    product: Mapped[Product] = relationship(back_populates="images")

    def __repr__(self) -> str:
        return f"<ProductImage {self.url}>"
