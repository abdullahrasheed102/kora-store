"""Product photos: match the optimized files to products and keep `product_images` in step.

`npm run images` (frontend/scripts/optimize-images.mjs) writes backend/seed/image-manifest.json,
a list of every WebP in frontend/public/images/products/. A file's name says what it shows:

    {product-slug}-{color-slug}   one colour of the garment, e.g. linen-button-up-shirt-sky-blue
    {product-slug}-lifestyle      the garment being worn

`sync_images` turns that list into `product_images` rows. It is idempotent: running it twice
gives the same rows as running it once, because each file's URL identifies its row (insert if
new, update if changed, leave it alone otherwise). It only touches rows for our own files
(URLs under /images/products/), never orders, users or the rest of the catalog.
"""

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.catalog import slugify
from app.models import ImageKind, Product, ProductImage

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "seed" / "image-manifest.json"
SYNCED_URL_PREFIX = "/images/products/"  # rows with other URLs (e.g. added by hand) are never touched
LIFESTYLE = "lifestyle"


class ManifestImage(BaseModel):
    name: str  # file name without .webp
    url: str
    width: int
    height: int


@dataclass(frozen=True)
class ExpectedImage:
    """A photo the catalog has a place for, and the row it should become."""

    name: str
    product: Product
    color: str | None
    kind: ImageKind
    position: int

    @property
    def alt_text(self) -> str:
        if self.kind is ImageKind.LIFESTYLE:
            return f"A model wearing the {self.product.name}"
        return f"{self.product.name} in {(self.color or '').lower()}, front view"


@dataclass
class SyncReport:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    unmatched: list[tuple[str, str | None]] = field(default_factory=list)  # (file name, closest expected name)
    missing: dict[str, list[str]] = field(default_factory=dict)  # product slug -> missing colour/lifestyle slugs
    coverage: dict[str, tuple[int, int]] = field(default_factory=dict)  # product slug -> (have, expected)


def load_manifest(path: Path = MANIFEST_PATH) -> list[ManifestImage]:
    data = json.loads(path.read_text())
    return TypeAdapter(list[ManifestImage]).validate_python(data["images"])


def expected_images(products: list[Product]) -> dict[str, ExpectedImage]:
    """Every file name we'd recognise: one per product colour, plus one lifestyle photo.

    Colour photos come first in the gallery, in the same order as the colour swatches;
    the lifestyle photo goes last.
    """
    expected: dict[str, ExpectedImage] = {}
    for product in products:
        colors = list(dict.fromkeys(variant.color for variant in product.variants))
        for position, color in enumerate(colors):
            name = f"{product.slug}-{slugify(color)}"
            expected[name] = ExpectedImage(name, product, color, ImageKind.PRODUCT, position)
        name = f"{product.slug}-{LIFESTYLE}"
        expected[name] = ExpectedImage(name, product, None, ImageKind.LIFESTYLE, len(colors))
    return expected


def sync_images(session: Session, manifest: list[ManifestImage], *, dry_run: bool = False) -> SyncReport:
    """Make product_images match the manifest. With dry_run, only report what would change."""
    products = list(
        session.scalars(select(Product).options(selectinload(Product.variants)).order_by(Product.id))
    )
    expected = expected_images(products)
    report = SyncReport()

    matched: dict[str, tuple[ExpectedImage, ManifestImage]] = {}  # url -> (expected, file)
    for image in manifest:
        if image.name in expected:
            matched[image.url] = (expected[image.name], image)
        else:
            # Most mismatches are typos, so suggest the nearest real name.
            close = difflib.get_close_matches(image.name, list(expected), n=1, cutoff=0.75)
            report.unmatched.append((image.name, close[0] if close else None))

    found = {exp.name for exp, _ in matched.values()}
    for product in products:
        names = [name for name, exp in expected.items() if exp.product is product]
        have = [name for name in names if name in found]
        report.coverage[product.slug] = (len(have), len(names))
        if missing := [name.removeprefix(f"{product.slug}-") for name in names if name not in found]:
            report.missing[product.slug] = missing

    existing = {
        row.url: row
        for row in session.scalars(select(ProductImage).where(ProductImage.url.startswith(SYNCED_URL_PREFIX)))
    }
    for url, (exp, _image) in matched.items():
        wanted = {
            "product_id": exp.product.id,
            "color": exp.color,
            "kind": exp.kind,
            "alt_text": exp.alt_text,
            "position": exp.position,
        }
        row = existing.get(url)
        if row is None:
            report.added += 1
            if not dry_run:
                session.add(ProductImage(url=url, **wanted))
        elif any(getattr(row, key) != value for key, value in wanted.items()):
            report.updated += 1
            if not dry_run:
                for key, value in wanted.items():
                    setattr(row, key, value)
        else:
            report.unchanged += 1

    # A file that was renamed or deleted leaves a row pointing at nothing: remove it, so the
    # site shows the placeholder instead of a broken image.
    for url, row in existing.items():
        if url not in matched:
            report.removed += 1
            if not dry_run:
                session.delete(row)

    if dry_run:
        session.rollback()
    else:
        session.commit()
    return report


def format_report(report: SyncReport, *, dry_run: bool = False, show_coverage: bool = False) -> str:
    """Human-readable summary for the CLI."""
    verb = "Would sync" if dry_run else "Synced"
    lines = [
        f"{verb} product images: {report.added} added, {report.updated} updated, "
        f"{report.unchanged} unchanged, {report.removed} removed."
    ]
    if report.unmatched:
        lines.append(f"\n{len(report.unmatched)} file(s) match no product + colour, so they were NOT synced:")
        for name, close in report.unmatched:
            lines.append(f"  {name}" + (f"   (did you mean {close}?)" if close else ""))
    if show_coverage:
        lines.append("\nCoverage (photos found / expected):")
        for slug, (have, total) in report.coverage.items():
            mark = "done" if have == total else "none" if have == 0 else "part"
            lines.append(f"  [{mark}] {slug:<26} {have}/{total}")
    if report.missing:
        total = sum(len(names) for names in report.missing.values())
        lines.append(f"\nStill missing {total} image(s):")
        for slug, names in report.missing.items():
            lines.append(f"  {slug}: {', '.join(names)}")
    return "\n".join(lines)
