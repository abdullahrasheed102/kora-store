"""Product photos: the manifest, `flask images sync` (idempotent, never touches orders) and the API."""

import json
from pathlib import Path

from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.images import MANIFEST_PATH, ManifestImage, expected_images, load_manifest, sync_images
from app.models import ImageKind, Order, Product, ProductImage, User
from app.seed import SeedCounts

FRONTEND_PUBLIC = Path(__file__).resolve().parents[2] / "frontend" / "public"


def photo(name: str) -> ManifestImage:
    return ManifestImage(name=name, url=f"/images/products/{name}.webp", width=1200, height=1500)


SHIRT = ["linen-button-up-shirt-sand", "linen-button-up-shirt-sky-blue", "linen-button-up-shirt-lifestyle"]


def images_of(session: Session, slug: str) -> list[ProductImage]:
    product = session.scalars(select(Product).where(Product.slug == slug)).one()
    return list(product.images)


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


# --- matching file names ------------------------------------------------------------------------


def test_expected_names_use_the_colour_slug_and_put_lifestyle_last(db_session: Session, seeded: SeedCounts) -> None:
    shirt = db_session.scalars(select(Product).where(Product.slug == "linen-button-up-shirt")).one()
    expected = expected_images([shirt])
    assert list(expected) == SHIRT  # "Sky Blue" -> sky-blue
    lifestyle = expected["linen-button-up-shirt-lifestyle"]
    assert (lifestyle.kind, lifestyle.color, lifestyle.position) == (ImageKind.LIFESTYLE, None, 2)


def test_sync_creates_rows_with_descriptive_alt_text(db_session: Session, seeded: SeedCounts) -> None:
    report = sync_images(db_session, [photo(name) for name in SHIRT])

    assert (report.added, report.updated, report.unchanged, report.removed) == (3, 0, 0, 0)
    rows = images_of(db_session, "linen-button-up-shirt")
    assert [(row.kind, row.color, row.position) for row in rows] == [
        (ImageKind.PRODUCT, "Sand", 0),
        (ImageKind.PRODUCT, "Sky Blue", 1),
        (ImageKind.LIFESTYLE, None, 2),
    ]
    assert rows[1].alt_text == "Linen Button-Up Shirt in sky blue, front view"
    assert rows[2].alt_text == "A model wearing the Linen Button-Up Shirt"


def test_sync_is_idempotent(db_session: Session, seeded: SeedCounts) -> None:
    manifest = [photo(name) for name in SHIRT]
    sync_images(db_session, manifest)
    ids_before = [row.id for row in images_of(db_session, "linen-button-up-shirt")]

    report = sync_images(db_session, manifest)

    assert (report.added, report.updated, report.unchanged, report.removed) == (0, 0, 3, 0)
    assert [row.id for row in images_of(db_session, "linen-button-up-shirt")] == ids_before


def test_sync_never_touches_orders_or_users(db_session: Session, seeded: SeedCounts) -> None:
    before = (count(db_session, Order), count(db_session, User), count(db_session, Product))
    sync_images(db_session, [photo(name) for name in SHIRT])
    sync_images(db_session, [])
    assert (count(db_session, Order), count(db_session, User), count(db_session, Product)) == before


def test_sync_repairs_a_row_that_was_changed(db_session: Session, seeded: SeedCounts) -> None:
    sync_images(db_session, [photo(SHIRT[0])])
    row = images_of(db_session, "linen-button-up-shirt")[0]
    row.alt_text = "oops"
    db_session.commit()

    report = sync_images(db_session, [photo(SHIRT[0])])

    assert report.updated == 1
    db_session.refresh(row)
    assert row.alt_text == "Linen Button-Up Shirt in sand, front view"


def test_a_misspelled_file_is_reported_with_a_suggestion_and_not_synced(db_session: Session, seeded: SeedCounts) -> None:
    report = sync_images(db_session, [photo("everyday-cotton-tee-white.png"), photo("linen-buton-up-shirt-sand")])

    assert report.unmatched == [
        ("everyday-cotton-tee-white.png", "everyday-cotton-tee-white"),
        ("linen-buton-up-shirt-sand", "linen-button-up-shirt-sand"),
    ]
    assert count(db_session, ProductImage) == 0


def test_missing_photos_are_listed_per_product(db_session: Session, seeded: SeedCounts) -> None:
    report = sync_images(db_session, [photo(SHIRT[0])])
    assert report.missing["linen-button-up-shirt"] == ["sky-blue", "lifestyle"]
    assert report.coverage["linen-button-up-shirt"] == (1, 3)
    assert report.missing["gift-card"] == ["digital", "lifestyle"]


def test_a_file_removed_from_the_manifest_loses_its_row_but_hand_added_rows_stay(
    db_session: Session, seeded: SeedCounts
) -> None:
    sync_images(db_session, [photo(name) for name in SHIRT])
    shirt = db_session.scalars(select(Product).where(Product.slug == "linen-button-up-shirt")).one()
    db_session.add(
        ProductImage(product=shirt, kind=ImageKind.PRODUCT, url="https://cdn.example.com/shirt.jpg", alt_text="x")
    )
    db_session.commit()

    report = sync_images(db_session, [photo(SHIRT[0])])  # sky-blue and lifestyle were deleted

    assert report.removed == 2
    assert sorted(row.url for row in images_of(db_session, "linen-button-up-shirt")) == [
        "/images/products/linen-button-up-shirt-sand.webp",
        "https://cdn.example.com/shirt.jpg",
    ]


def test_dry_run_changes_nothing(db_session: Session, seeded: SeedCounts) -> None:
    report = sync_images(db_session, [photo(name) for name in SHIRT], dry_run=True)
    assert report.added == 3
    assert count(db_session, ProductImage) == 0


# --- the committed manifest -------------------------------------------------------------------


def test_every_manifest_entry_points_at_a_real_4x5_file() -> None:
    for image in load_manifest():
        assert (FRONTEND_PUBLIC / image.url.lstrip("/")).is_file(), image.url
        assert image.width * 5 == image.height * 4, image.name


# --- CLI ------------------------------------------------------------------------------------------


def test_cli_sync_and_check(app: Flask, db_session: Session, seeded: SeedCounts, tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"images": [photo(name).model_dump() for name in SHIRT]}))
    runner = app.test_cli_runner()

    check = runner.invoke(args=["images", "check", "--manifest", str(manifest)])
    assert check.exit_code == 0, check.output
    assert "Would sync product images: 3 added" in check.output
    assert "[done] linen-button-up-shirt" in check.output
    assert count(db_session, ProductImage) == 0

    first = runner.invoke(args=["images", "sync", "--manifest", str(manifest)])
    second = runner.invoke(args=["images", "sync", "--manifest", str(manifest)])
    assert "3 added" in first.output
    assert "0 added, 0 updated, 3 unchanged, 0 removed" in second.output


def test_seed_reset_attaches_the_photos_in_the_manifest(app: Flask, db_session: Session) -> None:
    result = app.test_cli_runner().invoke(args=["seed", "--reset"])
    assert result.exit_code == 0, result.output
    assert "Synced product images" in result.output
    known = set(expected_images(list(db_session.scalars(select(Product)))))
    assert count(db_session, ProductImage) == sum(image.name in known for image in load_manifest(MANIFEST_PATH))


# --- API --------------------------------------------------------------------------------------------


def test_product_list_and_detail_include_images(client: FlaskClient, db_session: Session, seeded: SeedCounts) -> None:
    sync_images(db_session, [photo(name) for name in SHIRT])

    listing = client.get("/api/products?per_page=48").get_json()["items"]
    shirt = next(item for item in listing if item["slug"] == "linen-button-up-shirt")
    assert [image["kind"] for image in shirt["images"]] == ["product", "product", "lifestyle"]
    assert shirt["images"][1] == {
        "url": "/images/products/linen-button-up-shirt-sky-blue.webp",
        "alt_text": "Linen Button-Up Shirt in sky blue, front view",
        "kind": "product",
        "color": "Sky Blue",
    }
    tote = next(item for item in listing if item["slug"] == "canvas-tote-bag")
    assert tote["images"] == []  # not photographed yet: the site shows a placeholder

    detail = client.get("/api/products/linen-button-up-shirt").get_json()
    assert [image["color"] for image in detail["images"]] == ["Sand", "Sky Blue", None]
    assert all("images" in related for related in detail["related"])


def test_cart_quote_lines_carry_the_photo_of_their_colour(
    client: FlaskClient, db_session: Session, seeded: SeedCounts
) -> None:
    sync_images(db_session, [photo(SHIRT[1])])  # only Sky Blue is photographed
    shirt = db_session.scalars(select(Product).where(Product.slug == "linen-button-up-shirt")).one()
    sky = next(v for v in shirt.variants if v.color == "Sky Blue" and v.stock > 0)
    sand = next(v for v in shirt.variants if v.color == "Sand" and v.stock > 0)

    quote = client.post(
        "/api/cart/quote", json={"items": [{"variant_id": sky.id, "quantity": 1}, {"variant_id": sand.id, "quantity": 1}]}
    ).get_json()

    by_color = {item["color"]: item["image"] for item in quote["items"]}
    assert by_color["Sky Blue"]["url"] == "/images/products/linen-button-up-shirt-sky-blue.webp"
    assert by_color["Sand"] is None
