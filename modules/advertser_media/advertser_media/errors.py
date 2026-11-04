"""Public failures; messages never include credentials or profile contents."""


class MarketingError(Exception):
    """Base error for the isolated marketing foundation."""


class ValidationError(MarketingError, ValueError):
    pass


class AuthenticationNotConfigured(MarketingError):
    pass


class AuthenticationFailed(MarketingError):
    pass


class PermissionDenied(MarketingError):
    pass


class UnknownClient(MarketingError):
    pass


class StorageIsolationError(MarketingError):
    pass
