"""Persistence layer adapters.

Historically the app used :class:`JSONStore` against ``data/*.json`` files.
Per the SQLite migration spec, :class:`SQLStore` is a drop-in adapter
with the same public API but backed by SQLAlchemy. Services keep the
``JSONStore``-shaped interface; the live wiring in ``main.py`` /
``dependencies.py`` chooses which implementation to instantiate.

``JSONStore`` is retained (deprecated) so existing tests + the rollback
script can still round-trip data through the JSON shape.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JSONStore:
    """DEPRECATED: file-based store, retained for tests + rollback path.

    Use :class:`SQLStore` for new code. Reads/writes JSON arrays with
    atomic writes (temp file + os.replace) to prevent file corruption.
    Creates the file with an empty array if it does not exist.
    """

    def __init__(self, file_path: str):
        """Initialize store with path to JSON file."""
        self.file_path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Create the JSON file with an empty array if it does not exist."""
        path = Path(self.file_path)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            self._write_atomic([])

    def _write_atomic(self, data: list[dict]) -> None:
        """Write data atomically using a temp file and os.replace.

        Writes to a temporary file in the same directory, then atomically
        replaces the target file. This prevents corruption if the process
        crashes mid-write.

        Raises:
            IOError: If the write operation fails.
        """
        dir_path = os.path.dirname(os.path.abspath(self.file_path))
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(data, tmp_file, indent=2, default=str)
            os.replace(tmp_path, self.file_path)
        except Exception:
            # Clean up temp file if replace failed
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def read_all(self) -> list[dict]:
        """Read all records from the JSON file.

        Creates the file with an empty array if it does not exist.

        Returns:
            A list of all records in the store.

        Raises:
            IOError: If the file cannot be read.
        """
        try:
            if not os.path.exists(self.file_path):
                self._write_atomic([])
                return []
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, IOError) as e:
            raise IOError(f"Failed to read store file: {self.file_path}") from e

    def write_all(self, data: list[dict]) -> None:
        """Atomically write all records to the JSON file.

        Args:
            data: The complete list of records to persist.

        Raises:
            IOError: If the write operation fails.
        """
        try:
            self._write_atomic(data)
        except Exception as e:
            raise IOError(f"Failed to write store file: {self.file_path}") from e

    def find_by_id(self, record_id: str) -> dict | None:
        """Find a single record by its id field.

        Args:
            record_id: The id value to search for.

        Returns:
            The matching record dict, or None if not found.
        """
        records = self.read_all()
        for record in records:
            if record.get("id") == record_id:
                return record
        return None

    def find_by_field(self, field: str, value: str) -> dict | None:
        """Find a single record by an arbitrary field match.

        Args:
            field: The field name to search on.
            value: The value to match.

        Returns:
            The first matching record dict, or None if not found.
        """
        records = self.read_all()
        for record in records:
            if record.get(field) == value:
                return record
        return None

    def add(self, record: dict) -> dict:
        """Append a record to the store and persist.

        Args:
            record: The record dict to add.

        Returns:
            The added record.

        Raises:
            IOError: If the write operation fails.
        """
        records = self.read_all()
        records.append(record)
        self.write_all(records)
        return record

    def update(self, record_id: str, updates: dict) -> dict | None:
        """Update fields on a record by id and persist.

        Args:
            record_id: The id of the record to update.
            updates: A dict of field names and new values to apply.

        Returns:
            The updated record dict, or None if the record was not found.

        Raises:
            IOError: If the write operation fails.
        """
        records = self.read_all()
        for i, record in enumerate(records):
            if record.get("id") == record_id:
                records[i].update(updates)
                self.write_all(records)
                return records[i]
        return None

    def delete(self, record_id: str) -> bool:
        """Remove a record by id and persist.

        Args:
            record_id: The id of the record to remove.

        Returns:
            True if the record was found and removed, False otherwise.

        Raises:
            IOError: If the write operation fails.
        """
        records = self.read_all()
        original_length = len(records)
        records = [r for r in records if r.get("id") != record_id]
        if len(records) == original_length:
            return False
        self.write_all(records)
        return True


# ---------------------------------------------------------------------------
# SQLite-backed adapter (Requirement 3.2: same public API as JSONStore)
# ---------------------------------------------------------------------------


def _collection_name_from_path(file_path: str) -> str:
    """Derive a SQL table-key from a legacy ``data/foo.json`` path."""
    base = os.path.basename(file_path)
    if base.endswith(".json"):
        base = base[:-5]
    return base


class SQLStore:
    """SQLAlchemy-backed store with the same surface as :class:`JSONStore`.

    Each instance is bound to ONE collection (table). The collection name
    is derived from the legacy JSON file basename so existing callers can
    swap ``JSONStore(path)`` for ``SQLStore(session_factory, path)``
    without re-thinking their wiring.

    All methods commit immediately so failures surface fast (matching the
    "no silent fallback" requirement). Multi-row operations are wrapped
    in a single transaction.
    """

    def __init__(self, session_factory, file_path: str):
        # Lazy import to avoid pulling SQLAlchemy at import time of store.py
        from db_models import COLLECTION_TO_MODEL

        self._session_factory = session_factory
        self.file_path = file_path  # retained for parity / debugging
        collection = _collection_name_from_path(file_path)
        if collection not in COLLECTION_TO_MODEL:
            raise ValueError(
                f"SQLStore: unknown collection '{collection}'. "
                f"Known: {sorted(COLLECTION_TO_MODEL.keys())}"
            )
        self._model = COLLECTION_TO_MODEL[collection]

    # ---- internal -------------------------------------------------------

    def _session(self):
        return self._session_factory()

    # ---- API parity with JSONStore --------------------------------------

    def read_all(self) -> list[dict]:
        with self._session() as s:
            rows = s.query(self._model).all()
            return [r.to_dict() for r in rows]

    def write_all(self, data: list[dict]) -> None:
        """Replace the entire collection contents transactionally."""
        with self._session() as s:
            try:
                s.query(self._model).delete()
                for record in data:
                    if not isinstance(record, dict) or "id" not in record:
                        continue
                    s.add(self._model.from_dict(record))
                s.commit()
            except Exception:
                s.rollback()
                raise

    def find_by_id(self, record_id: str) -> dict | None:
        with self._session() as s:
            row = s.get(self._model, record_id)
            return row.to_dict() if row else None

    def find_by_field(self, field: str, value: Any) -> dict | None:
        if not hasattr(self._model, field):
            # Fall back to dict scan for fields stored only in extra_json.
            for record in self.read_all():
                if record.get(field) == value:
                    return record
            return None
        column = getattr(self._model, field)
        with self._session() as s:
            row = s.query(self._model).filter(column == value).first()
            return row.to_dict() if row else None

    def add(self, record: dict) -> dict:
        if "id" not in record:
            raise ValueError("SQLStore.add: record missing 'id'")
        with self._session() as s:
            try:
                s.add(self._model.from_dict(record))
                s.commit()
            except Exception:
                s.rollback()
                raise
        return record

    def update(self, record_id: str, updates: dict) -> dict | None:
        with self._session() as s:
            row = s.get(self._model, record_id)
            if row is None:
                return None
            try:
                row.update_from_dict(updates)
                s.commit()
                return row.to_dict()
            except Exception:
                s.rollback()
                raise

    def delete(self, record_id: str) -> bool:
        with self._session() as s:
            row = s.get(self._model, record_id)
            if row is None:
                return False
            try:
                s.delete(row)
                s.commit()
                return True
            except Exception:
                s.rollback()
                raise
