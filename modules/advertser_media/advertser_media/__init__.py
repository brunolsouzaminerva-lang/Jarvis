"""ADVERTSER MEDIA: isolated, import-safe local foundation for Jarvis."""

from .config import ModuleConfig
from .errors import (AuthenticationFailed, AuthenticationNotConfigured, MarketingError,
                     PermissionDenied, StorageIsolationError, UnknownClient, ValidationError)
from .models import AuditEvent, ClientProfile, Principal, Role
from .service import IdentityVerifier, MarketingService
from .status import readiness

__all__ = [
    "AuditEvent", "AuthenticationFailed", "AuthenticationNotConfigured", "ClientProfile",
    "IdentityVerifier", "MarketingError", "MarketingService", "ModuleConfig", "PermissionDenied",
    "Principal", "Role", "StorageIsolationError", "UnknownClient", "ValidationError", "readiness",
]
