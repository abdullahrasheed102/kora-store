"""Maintenance commands: `flask orders expire-unpaid`, `flask images sync|check`, `flask policies sync`,
`flask outbox process` and `flask email preview`."""

from datetime import timedelta
from pathlib import Path

import click
from flask.cli import AppGroup

from app.checkout import expire_unpaid_orders
from app.extensions import db
from app.images import MANIFEST_PATH, format_report, load_manifest, sync_images
from app.mail import outbox
from app.mail.preview import PREVIEWS, write_preview
from app.policies import POLICIES_PATH, load_policy_seed, sync_policies

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


policies_cli = AppGroup("policies", help="Store policy text.")


@policies_cli.command("sync")
@click.option(
    "--file",
    "path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=POLICIES_PATH,
    show_default="backend/seed/policies.json",
)
def policies_sync(path: Path) -> None:
    """Update policy text from the seed file, for policies whose `version` went up.

    Safe on a live database: it never deletes or reseeds anything, and running it again
    changes nothing. Admin edits are kept until a higher version is shipped.
    """
    click.echo(str(sync_policies(db.session, load_policy_seed(path))))


outbox_cli = AppGroup("outbox", help="The email outbox.")


@outbox_cli.command("process")
def outbox_process() -> None:
    """Send every due email now: the same job GitHub Actions runs every 5 minutes.

    Retries failed sends whose wait is over, and takes over rows stuck in "sending" after a crash.
    """
    result = outbox.run_scheduled(db.session, force=True)
    click.echo(", ".join(f"{name}: {value}" for name, value in result.items() if name != "skipped"))


email_cli = AppGroup("email", help="Email templates.")


@email_cli.command("preview")
@click.argument("name", type=click.Choice(["all", *PREVIEWS]))
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("email-previews"),
    show_default=True,
    help="Folder for the .html and .txt files (git-ignored).",
)
def email_preview(name: str, out_dir: Path) -> None:
    """Render an email with sample data to an HTML file you can open in a browser. Sends nothing.

    NAME is a template (with variants, e.g. order_update_delayed), or "all".
    """
    for preview in PREVIEWS if name == "all" else [name]:
        path = write_preview(preview, out_dir)
        click.echo(f"{path.resolve()}")
    click.echo("Open one with:  xdg-open <file>")
