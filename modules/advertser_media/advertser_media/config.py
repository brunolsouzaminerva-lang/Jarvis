"""Explicit storage configuration; construction does not inspect the filesystem."""

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from .errors import StorageIsolationError, ValidationError


@dataclass(frozen=True)
class ModuleConfig:
    data_root: Path
    allowed_clients: frozenset[UUID]
    protected_roots: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.protected_roots, tuple):
            raise ValidationError("protected_roots must be a tuple of absolute Paths.")
        paths = (self.data_root, *self.protected_roots)
        if any(not isinstance(path, Path) or not path.is_absolute()
               or ".." in path.parts for path in paths):
            raise ValidationError("Storage paths must be absolute Paths without traversal.")
        if (not isinstance(self.allowed_clients, frozenset)
                or any(not isinstance(client, UUID) for client in self.allowed_clients)):
            raise ValidationError("allowed_clients must be a frozenset of UUIDs.")

    @property
    def namespace(self) -> Path:
        return self.data_root / "advertser_media"

    def database_path(self, client_id: UUID) -> Path:
        return self.namespace / "clients" / str(client_id) / "marketing.sqlite3"

    def guard(self, path: Path) -> None:
        """Recheck confinement and existing links on each authenticated operation.

        OS ownership/ACLs must also prevent another process replacing these paths
        during an operation; this is not an operating-system sandbox.
        """
        if path != self.namespace and self.namespace not in path.parents:
            raise StorageIsolationError("Path is outside the module namespace.")
        try:
            namespace = self.namespace.resolve(strict=False)
            root = self.data_root.resolve(strict=False)
            protected_roots = tuple(path.resolve(strict=False) for path in self.protected_roots)
        except (OSError, RuntimeError):
            raise StorageIsolationError("Storage paths cannot be resolved safely.") from None
        for protected in protected_roots:
            if (namespace == protected or protected in namespace.parents
                    or namespace in protected.parents
                    or root == protected or protected in root.parents):
                raise StorageIsolationError("Storage overlaps a protected root.")
        for current in (*reversed(path.parents), path):
            try:
                info = current.lstat()
            except FileNotFoundError:
                continue
            if (stat.S_ISLNK(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & 0x400):
                raise StorageIsolationError("Links and reparse points are not allowed in storage paths.")
            if current != path and not stat.S_ISDIR(info.st_mode):
                raise StorageIsolationError("Storage ancestor is not a directory.")


def create_directory(config: ModuleConfig, path: Path) -> None:
    config.guard(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    config.guard(path)
    if not path.is_dir():
        raise StorageIsolationError("Storage directory is invalid.")


def check_file(config: ModuleConfig, path: Path) -> None:
    config.guard(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise StorageIsolationError("Storage file must be regular and have a single link.")


def create_file(config: ModuleConfig, path: Path, contents: bytes = b"") -> None:
    config.guard(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
        stream.write(contents)
    check_file(config, path)
