"""Export the SQLite tables back to ``data/*.json`` files.

Sibling of ``migrate_json_to_sqlite.py``. Reads every row from each
known table and writes the equivalent JSON array. Any existing JSON
files are backed up as ``data/<name>.json.bak`` before overwrite.

Usage (from the ``backend/`` directory):

    python3 -m scripts.rollback_sqlite_to_json
    python3 -m scripts.rollback_sqlite_to_json --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import make_engine, make_session_factory  # noqa: E402
from db_models import COLLECTION_TO_MODEL  # noqa: E402


TABLE_TO_FILENAME = {
    "users": "users.json",
    "folders": "folders.json",
    "todos": "todos.json",
    "notifications": "notifications.json",
    "attachments": "attachments.json",
    "reminder_send_log": "reminder_send_log.json",
}


def _backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    return bak


def rollback(data_dir: Path, *, dry_run: bool = False) -> int:
    db_path = data_dir / "app.db"
    if not db_path.exists():
        print(f"No SQLite DB found at {db_path}", file=sys.stderr)
        return 0

    engine = make_engine(f"sqlite:///{db_path}")
    session_factory = make_session_factory(engine)

    total_exported = 0
    print(f"Source DB : {db_path}")
    print(f"Target dir: {data_dir}")
    print(f"Dry run   : {dry_run}")
    print("-" * 60)

    for collection, filename in TABLE_TO_FILENAME.items():
        model = COLLECTION_TO_MODEL[collection]
        with session_factory() as s:
            rows = s.query(model).all()
            records = [r.to_dict() for r in rows]

        out_path = data_dir / filename
        if not dry_run:
            bak = _backup(out_path)
            if bak:
                print(f"  backup    → {bak.name}")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("w", encoding="utf-8") as fh:
                json.dump(records, fh, indent=2, default=str)

        total_exported += len(records)
        print(f"  {collection:20s} exported={len(records):d}")

    print("-" * 60)
    print(f"Total rows exported: {total_exported}")
    return total_exported


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
        help="Report counts without writing any JSON files.",
    )
    args = parser.parse_args()
    try:
        rollback(Path(args.data_dir), dry_run=args.dry_run)
        return 0
    except Exception as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
