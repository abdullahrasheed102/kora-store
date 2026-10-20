"""Store policies from backend/seed/policies.json, and `flask policies sync`.

Policies live in the database (one source of truth for the website and the AI agent) and admins
can edit them. When the file gets a new policy text, production must get it too, but it can't be
reseeded (that would delete real orders). So each policy in the file has a `version`:

    flask policies sync  updates a policy only if the file's version is HIGHER than the version
                         stored with it, then stores the new version.

Like migrations, but for content. Running it again changes nothing (idempotent), and an admin's
edit survives every deploy until someone deliberately ships a higher version of that policy.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Policy

POLICIES_PATH = Path(__file__).resolve().parent.parent / "seed" / "policies.json"


def load_policy_seed(path: Path = POLICIES_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def policy_from_seed(row: dict[str, Any]) -> Policy:
    return Policy(
        key=row["key"],
        title=row["title"],
        summary=row.get("summary"),
        body=row["body"],
        seed_version=row.get("version", 1),
    )


@dataclass
class PolicySyncReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        parts = [f"{len(self.added)} added", f"{len(self.updated)} updated", f"{len(self.unchanged)} unchanged"]
        detail = "".join(f"\n  {verb}: {', '.join(keys)}" for verb, keys in (("added", self.added), ("updated", self.updated)) if keys)
        return "Policies: " + ", ".join(parts) + "." + detail


def sync_policies(session: Session, rows: list[dict[str, Any]]) -> PolicySyncReport:
    """Bring policies up to the versions in the seed file. Never deletes, never touches anything else."""
    existing = {policy.key: policy for policy in session.scalars(select(Policy))}
    report = PolicySyncReport()
    for row in rows:
        policy = existing.get(row["key"])
        version = row.get("version", 1)
        if policy is None:
            session.add(policy_from_seed(row))
            report.added.append(row["key"])
        elif version > policy.seed_version:
            policy.title, policy.summary, policy.body = row["title"], row.get("summary"), row["body"]
            policy.seed_version = version
            report.updated.append(row["key"])
        else:
            report.unchanged.append(row["key"])  # same version: keep the database text (maybe admin-edited)
    session.commit()
    return report
