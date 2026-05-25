"""Migrate ``data/*.json`` files into ``data/app.db`` (SQLite).

Idempotent — rows whose primary key already exists in SQLite are skipped.
Source JSON files are backed up as ``data/<name>.json.bak`` before reading
so that ``scripts/rollback_sqlite_to_json.py`` can restore the originals.

Usage (from the ``backend/`` directory):

    python3 -m scripts.migrate_json_to_sqlite
    python3 -m scripts.migrate_json_to_sqlite --dry-run

Exits 0 on success, 1 on any unexpected error (per-row validation errors
are logged but do not abort the migration; see Requirement 2.5).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# Make sibling-module imports work whether run as a module or a script.
HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import init_db, make_engine, make_session_factory  # noqa: E402
from db_models import COLLECTION_TO_MODEL  # noqa: E402


# Mapping of JSON filenames → SQL collection key.
SOURCE_FILES: list[tuple[str, str]] = [
    ("users.json", "users"),
    ("folders.json", "folders"),
    ("todos.json", "todos"),
    ("notifications.json", "notifications"),
    ("attachments.json", "attachments"),
    ("reminder_send_log.json", "reminder_send_log"),
]


def _backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    return bak


def _load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            print(f"  ! {path.name}: top-level value is not a list — skipping")
            return []
        return data
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  ! {path.name}: failed to read ({exc}) — skipping")
        return []


def migrate(data_dir: Path, *, dry_run: bool = False) -> int:
    """Run the migration. Returns the total row count inserted."""
    engine = make_engine(f"sqlite:///{data_dir / 'app.db'}")
    init_db(engine)
    session_factory = make_session_factory(engine)

    total_inserted = 0
    print(f"Source dir : {data_dir}")
    print(f"Target DB  : {data_dir / 'app.db'}")
    print(f"Dry run    : {dry_run}")
    print("-" * 60)

    for filename, collection in SOURCE_FILES:
        src = data_dir / filename
        model = COLLECTION_TO_MODEL[collection]

        if not src.exists():
            print(f"  {collection:20s} (no source file)")
            continue

        if not dry_run:
            bak = _backup(src)
            if bak:
                print(f"  backup     → {bak.name}")

        records = _load_records(src)
        if not records:
            print(f"  {collection:20s} 0 rows (empty source)")
            continue

        inserted = 0
        skipped_existing = 0
        skipped_invalid = 0

        with session_factory() as s:
            existing_ids = {r[0] for r in s.query(model.id).all()}
            for record in records:
                rid = record.get("id")
                if not rid:
                    skipped_invalid += 1
                    continue
                if rid in existing_ids:
                    skipped_existing += 1
                    continue
                try:
                    row = model.from_dict(record)
                    if not dry_run:
                        s.add(row)
                    inserted += 1
                    existing_ids.add(rid)
                except Exception as exc:  # validation / coercion failures
                    print(f"    ! {collection}: row id={rid!r} failed: {exc}")
                    skipped_invalid += 1
            if not dry_run:
                s.commit()

        total_inserted += inserted
        print(
            f"  {collection:20s} inserted={inserted:<5d} "
            f"skipped_existing={skipped_existing:<3d} "
            f"skipped_invalid={skipped_invalid:<3d}"
        )

    print("-" * 60)
    print(f"Total rows inserted: {total_inserted}")
    return total_inserted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=os.path.join(BACKEND_DIR, "data"),
        help="Path to the backend data directory (default: backend/data)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without writing to SQLite or creating backups.",
    )
    args = parser.parse_args()
    try:
        migrate(Path(args.data_dir), dry_run=args.dry_run)
        return 0
    except Exception as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
