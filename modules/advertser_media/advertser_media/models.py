"""Validated local records, without provider credentials or fabricated metrics."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID

from .errors import ValidationError


def _text(value: str, field: str, maximum: int, required: bool = False) -> None:
    if (not isinstance(value, str) or len(value) > maximum
            or (required and not value.strip()) or "\x00" in value):
        raise ValidationError(f"Invalid {field}.")


class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


@dataclass(frozen=True)
class Principal:
    """Identity returned by a trusted verifier, never assembled from UI claims."""

    user_id: str
    roles: frozenset[Role]
    client_ids: frozenset[UUID]

    def __post_init__(self) -> None:
        _text(self.user_id, "user_id", 200, required=True)
        if (not isinstance(self.roles, frozenset)
                or any(not isinstance(role, Role) for role in self.roles)
                or not isinstance(self.client_ids, frozenset)
                or any(not isinstance(client, UUID) for client in self.client_ids)):
            raise ValidationError("Invalid principal memberships or roles.")


@dataclass(frozen=True)
class ClientProfile:
    client_id: UUID
    name: str
    segment: str = ""
    target_audience: str = ""
    objectives: tuple[str, ...] = ()
    monthly_fee: Decimal | None = None
    currency: str = "BRL"
    account_manager: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.client_id, UUID):
            raise ValidationError("client_id must be a UUID.")
        _text(self.name, "name", 200, required=True)
        _text(self.segment, "segment", 200)
        _text(self.target_audience, "target_audience", 4000)
        _text(self.account_manager, "account_manager", 200)
        if not isinstance(self.objectives, tuple) or len(self.objectives) > 20:
            raise ValidationError("Invalid objectives.")
        for objective in self.objectives:
            _text(objective, "objective", 500, required=True)
        if (not isinstance(self.currency, str) or len(self.currency) != 3
                or not self.currency.isascii() or not self.currency.isalpha()
                or self.currency != self.currency.upper()):
            raise ValidationError("currency must be three uppercase ASCII letters.")
        fee = self.monthly_fee
        if fee is not None and (not isinstance(fee, Decimal) or not fee.is_finite()
                                or fee < 0 or fee > Decimal("999999999999.99")
                                or fee.as_tuple().exponent < -2):
            raise ValidationError("monthly_fee must be a finite nonnegative Decimal with at most two decimals.")


@dataclass(frozen=True)
class AuditEvent:
    event_id: UUID
    client_id: UUID
    actor_id: str
    action: str
    occurred_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, UUID) or not isinstance(self.client_id, UUID):
            raise ValidationError("Invalid audit identifiers.")
        _text(self.actor_id, "actor_id", 200, required=True)
        if self.action not in {"client.created", "client.updated"}:
            raise ValidationError("Invalid audit action.")
        _text(self.occurred_at, "occurred_at", 64, required=True)
        try:
            timestamp = datetime.fromisoformat(self.occurred_at)
            if timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
                raise ValueError
        except ValueError:
            raise ValidationError("Audit timestamp must be UTC ISO format.") from None
