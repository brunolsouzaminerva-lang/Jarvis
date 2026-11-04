"""Capability declaration only; this module never probes runtime resources."""


def readiness() -> dict[str, str]:
    return {
        "module": "advertser_media",
        "module_name": "ADVERTSER MEDIA — MARKETING INTELLIGENCE",
        "agent_name": "JARVIS MARKETING INTELLIGENCE",
        "client_profiles": "implemented_local",
        "audit": "implemented_local",
        "authentication": "not_configured",
        "central_authentication": "not_configured",
        "meta_ads": "not_configured",
        "google_ads": "not_configured",
        "social_content": "planned",
        "content_approvals": "planned",
        "agent": "planned",
        "user_interface": "planned",
        "scheduler": "planned",
        "external_actions": "not_implemented",
        "external_writes": "disabled",
        "worker": "pending_infrastructure",
    }
