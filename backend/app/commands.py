"""Maintenance commands: `flask orders expire-unpaid`, `flask images sync` and `flask images check`."""

from datetime import timedelta
from pathlib import Path

import click
from flask.cli import AppGroup

from app.checkout import expire_unpaid_orders
from app.extensions import db
from app.images import MANIFEST_PATH, format_report, load_manifest, sync_images

orders_cli = AppGroup("orders", help="Order maintenance.")


@orders_cli.command("expire-unpaid")
@click.option("--older-than", default=60, show_default=True, help="Minutes since checkout started.")
def expire_unpaid(older_than: int) -> None:
    """Cancel orders still awaiting payment after OLDER_THAN minutes.

    A safety net for missed `checkout.session.expired` webhooks. Keep OLDER_THAN above the
    Stripe session lifetime (30 minutes) so no order can still be paid after we cancel it.
    """
    if older_than < 31:
        raise click.BadParameter("must be more than the 30-minute Stripe session lifetime", param_hint="--older-than")
    expired = expire_unpaid_orders(db.session, timedelta(minutes=older_than))
    click.echo(f"Expired {len(expired)} unpaid order(s){': ' + ', '.join(expired) if expired else '.'}")


images_cli = AppGroup("images", help="Product photos.")
manifest_option = click.option(
    "--manifest",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=MANIFEST_PATH,
    show_default="backend/seed/image-manifest.json",
    help="The list written by `npm run images`.",
)


@images_cli.command("sync")
@manifest_option
def images_sync(manifest: Path) -> None:
    """Insert or update product_images rows from the image manifest.

    Safe to run any number of times, and safe on a live database: it changes only the
    product_images rows for our own photo files, never orders, users or products.
    """
    report = sync_images(db.session, load_manifest(manifest))
    click.echo(format_report(report))


@images_cli.command("check")
@manifest_option
def images_check(manifest: Path) -> None:
    """Report which photos match, which file names look wrong, and which are missing. Changes nothing."""
    report = sync_images(db.session, load_manifest(manifest), dry_run=True)
    click.echo(format_report(report, dry_run=True, show_coverage=True))
