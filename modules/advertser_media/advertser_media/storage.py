"""Per-client SQLite persistence, accessed only after service authorization."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from .config import ModuleConfig, check_file, create_directory, create_file
from .errors import StorageIsolationError
from .models import AuditEvent, ClientProfile

_MARKER = b'{"module":"advertser_media","schema_version":1}\n'
_APPLICATION_ID = 0x414D4544
_TABLES = {
    "module_metadata": "CREATE TABLE module_metadata (module TEXT NOT NULL, client_id TEXT NOT NULL, schema_version INTEGER NOT NULL)",
    "client_profile": "CREATE TABLE client_profile (singleton INTEGER PRIMARY KEY CHECK(singleton=1), client_id TEXT NOT NULL, name TEXT NOT NULL, segment TEXT NOT NULL, target_audience TEXT NOT NULL, objectives TEXT NOT NULL, monthly_fee TEXT, currency TEXT NOT NULL, account_manager TEXT NOT NULL)",
    "audit_events": "CREATE TABLE audit_events (event_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, actor_id TEXT NOT NULL, action TEXT NOT NULL, occurred_at TEXT NOT NULL)",
}


class ClientStore:
    def __init__(self, config: ModuleConfig):
        self.config = config

    def _path(self, client_id: UUID, create: bool) -> Path | None:
        namespace = self.config.namespace
        path = self.config.database_path(client_id)
        self.config.guard(path)
        if not namespace.exists():
            if not create:
                return None
            create_directory(self.config, namespace)
            create_file(self.config, namespace / ".advertser-media-runtime.json", _MARKER)
        marker = namespace / ".advertser-media-runtime.json"
        try:
            check_file(self.config, marker)
            with marker.open("rb") as stream:
                if stream.read(256) != _MARKER:
                    raise StorageIsolationError("Unrecognized module storage marker.")
        except (OSError, ValueError):
            raise StorageIsolationError("Module storage ownership is not established.") from None
        if any(item.name not in {marker.name, "clients"} for item in namespace.iterdir()):
            raise StorageIsolationError("Unexpected file in module namespace.")
        self.config.guard(namespace / "clients")
        if path.parent.exists():
            allowed_names = {path.name, *(path.name + suffix for suffix in ("-journal", "-wal", "-shm"))}
            for item in path.parent.iterdir():
                if item.name not in allowed_names:
                    raise StorageIsolationError("Unexpected file in client storage.")
                check_file(self.config, item)
        elif create:
            create_directory(self.config, path.parent)
        else:
            return None
        if path.exists():
            check_file(self.config, path)
            with path.open("rb") as stream:
                if stream.read(16) != b"SQLite format 3\x00":
                    raise StorageIsolationError("Existing file is not a recognized module database.")
            return path
        if not create:
            return None
        create_file(self.config, path)
        return path

    @contextmanager
    def _connection(self, path: Path, client_id: UUID, *, write: bool, new: bool = False):
        self.config.guard(path)
        check_file(self.config, path)
        connection = None
        try:
            mode = "rw" if write else "ro"
            connection = sqlite3.connect(f"{path.as_uri()}?mode={mode}", uri=True, timeout=5)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA trusted_schema=OFF")
            if not write:
                connection.execute("PRAGMA query_only=ON")
            if not new:
                self._validate_database(connection, client_id)
            yield connection
        except sqlite3.Error:
            raise StorageIsolationError("Module database could not be validated or accessed.") from None
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _validate_database(connection: sqlite3.Connection, client_id: UUID) -> None:
        if (connection.execute("PRAGMA application_id").fetchone()[0] != _APPLICATION_ID
                or connection.execute("PRAGMA user_version").fetchone()[0] != 1):
            raise StorageIsolationError("Database does not belong to this module version.")
        objects = connection.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'"
        ).fetchall()
        if (len(objects) != len(_TABLES) or any(row["type"] != "table" for row in objects)
                or {row["name"]: row["sql"] for row in objects} != _TABLES):
            raise StorageIsolationError("Database schema does not match the module contract.")
        rows = connection.execute("SELECT module, client_id, schema_version FROM module_metadata").fetchall()
        if len(rows) != 1 or tuple(rows[0]) != ("advertser_media", str(client_id), 1):
            raise StorageIsolationError("Database client or module metadata does not match.")
        for table in ("client_profile", "audit_events"):
            if connection.execute(
                f"SELECT 1 FROM {table} WHERE client_id != ? LIMIT 1", (str(client_id),)
            ).fetchone():
                raise StorageIsolationError("Database contains a different client's records.")

    @staticmethod
    def _initialize(connection: sqlite3.Connection, client_id: UUID) -> None:
        connection.execute(f"PRAGMA application_id={_APPLICATION_ID}")
        connection.execute("PRAGMA user_version=1")
        for sql in _TABLES.values():
            connection.execute(sql)
        connection.execute("INSERT INTO module_metadata VALUES (?, ?, ?)",
                           ("advertser_media", str(client_id), 1))

    @staticmethod
    def _profile(row: sqlite3.Row) -> ClientProfile:
        try:
            objectives = json.loads(row["objectives"])
            if not isinstance(objectives, list):
                raise ValueError
            return ClientProfile(
                client_id=UUID(row["client_id"]), name=row["name"], segment=row["segment"],
                target_audience=row["target_audience"], objectives=tuple(objectives),
                monthly_fee=Decimal(row["monthly_fee"]) if row["monthly_fee"] is not None else None,
                currency=row["currency"], account_manager=row["account_manager"],
            )
        except (ValueError, TypeError, ArithmeticError):
            raise StorageIsolationError("Stored client profile is invalid.") from None

    def get(self, client_id: UUID) -> ClientProfile | None:
        path = self._path(client_id, create=False)
        if path is None:
            return None
        with self._connection(path, client_id, write=False) as connection:
            row = connection.execute("SELECT * FROM client_profile WHERE singleton=1").fetchone()
            return self._profile(row) if row else None

    def upsert(self, profile: ClientProfile, actor_id: str) -> ClientProfile:
        self.config.guard(self.config.database_path(profile.client_id))
        existing = self._path(profile.client_id, create=False)
        if existing is not None:
            # Validate ownership read-only before opening any existing file for writing.
            with self._connection(existing, profile.client_id, write=False):
                pass
        path = existing or self._path(profile.client_id, create=True)
        assert path is not None
        with self._connection(path, profile.client_id, write=True, new=existing is None) as connection:
            if existing is None:
                # Establish an empty, owned database atomically. A later failed
                # profile/audit transaction can be retried without deleting files.
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    self._initialize(connection, profile.client_id)
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                self._validate_database(connection, profile.client_id)
                present = connection.execute("SELECT 1 FROM client_profile WHERE singleton=1").fetchone()
                connection.execute(
                    "INSERT OR REPLACE INTO client_profile VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(profile.client_id), profile.name, profile.segment, profile.target_audience,
                     json.dumps(profile.objectives, ensure_ascii=False),
                     str(profile.monthly_fee) if profile.monthly_fee is not None else None,
                     profile.currency, profile.account_manager),
                )
                connection.execute("INSERT INTO audit_events VALUES (?, ?, ?, ?, ?)",
                                   (str(uuid4()), str(profile.client_id), actor_id,
                                    "client.updated" if present else "client.created",
                                    datetime.now(timezone.utc).isoformat()))
        return profile

    def audit(self, client_id: UUID) -> tuple[AuditEvent, ...]:
        path = self._path(client_id, create=False)
        if path is None:
            return ()
        with self._connection(path, client_id, write=False) as connection:
            rows = connection.execute("SELECT * FROM audit_events ORDER BY rowid").fetchall()
            try:
                return tuple(AuditEvent(UUID(row["event_id"]), UUID(row["client_id"]),
                                        row["actor_id"], row["action"], row["occurred_at"])
                             for row in rows)
            except (ValueError, TypeError):
                raise StorageIsolationError("Stored audit event is invalid.") from None
