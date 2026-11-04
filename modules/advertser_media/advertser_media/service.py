"""Authenticated local facade. No HTTP server, workers, or external actions."""

from typing import Protocol
from uuid import UUID

from .config import ModuleConfig
from .errors import (AuthenticationFailed, AuthenticationNotConfigured, PermissionDenied,
                     UnknownClient, ValidationError)
from .models import AuditEvent, ClientProfile, Principal, Role
from .storage import ClientStore
from .status import readiness

_PERMISSIONS = {
    "clients.read": frozenset({Role.ADMIN, Role.MANAGER, Role.VIEWER}),
    "clients.write": frozenset({Role.ADMIN, Role.MANAGER}),
    "audit.read": frozenset({Role.ADMIN, Role.MANAGER}),
}


class IdentityVerifier(Protocol):
    """Future trusted core adapter must validate credential integrity and expiry.

    This package supplies no production verifier, login, signing key or fallback.
    """

    def verify(self, credential: str) -> Principal: ...


class MarketingService:
    def __init__(self, config: ModuleConfig, identity_verifier: IdentityVerifier | None = None):
        self.config = config
        self.identity_verifier = identity_verifier
        self._store = ClientStore(config)

    def readiness(self) -> dict[str, str]:
        """Static capability declaration, without probing paths or integrations."""
        status = readiness()
        if self.identity_verifier is not None:
            status["authentication"] = "verifier_injected"
        return status

    def _authenticate(self, credential: str | None) -> Principal:
        if self.identity_verifier is None:
            raise AuthenticationNotConfigured("Central authentication is not configured.")
        if not isinstance(credential, str) or not credential.strip() or len(credential) > 8192:
            raise AuthenticationFailed("A valid credential is required.")
        try:
            principal = self.identity_verifier.verify(credential)
            if not isinstance(principal, Principal):
                raise TypeError
        except Exception:
            raise AuthenticationFailed("Credential verification failed.") from None
        return principal

    def _check_permission(self, principal: Principal, client_id: UUID, permission: str) -> None:
        if not isinstance(client_id, UUID):
            raise ValidationError("client_id must be a UUID.")
        if client_id not in self.config.allowed_clients:
            raise UnknownClient("Client is not configured for this module.")
        if client_id not in principal.client_ids:
            raise PermissionDenied("Client access is not authorized.")
        if not principal.roles.intersection(_PERMISSIONS.get(permission, frozenset())):
            raise PermissionDenied("Required permission is not granted.")

    def _authorize(self, credential: str | None, client_id: UUID, permission: str) -> Principal:
        principal = self._authenticate(credential)
        self._check_permission(principal, client_id, permission)
        return principal

    def upsert_client(self, credential: str | None, profile: ClientProfile) -> ClientProfile:
        # Authentication must remain the first operation, even for invalid input.
        principal = self._authenticate(credential)
        if not isinstance(profile, ClientProfile):
            raise ValidationError("profile must be a ClientProfile.")
        self._check_permission(principal, profile.client_id, "clients.write")
        return self._store.upsert(profile, principal.user_id)

    def get_client(self, credential: str | None, client_id: UUID) -> ClientProfile | None:
        self._authorize(credential, client_id, "clients.read")
        return self._store.get(client_id)

    def list_audit(self, credential: str | None, client_id: UUID) -> tuple[AuditEvent, ...]:
        self._authorize(credential, client_id, "audit.read")
        return self._store.audit(client_id)
