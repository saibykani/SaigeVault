"""Privacy gate: decides whether a provider may receive document content.

Every call site that sends document content to a provider must pass through
`ensure_allowed`. This keeps the AI processing policy enforceable in one place.
"""

from __future__ import annotations

from enum import StrEnum

from saige_ai.providers import Provider, ProviderLocality


class AIProcessingPolicy(StrEnum):
    DISABLED = "disabled"
    LOCAL_ONLY = "local_only"
    THIRD_PARTY_ALLOWED = "third_party_allowed"


class ProviderNotAllowedError(PermissionError):
    """Raised when the configured policy forbids using a provider."""


class ProviderNotConfiguredError(LookupError):
    """Raised when a capability is requested but no provider is configured."""


def is_allowed(policy: AIProcessingPolicy, locality: ProviderLocality) -> bool:
    if policy is AIProcessingPolicy.DISABLED:
        return False
    if policy is AIProcessingPolicy.LOCAL_ONLY:
        return locality is ProviderLocality.LOCAL
    return True


def ensure_allowed(policy: AIProcessingPolicy, provider: Provider) -> None:
    if not is_allowed(policy, provider.locality):
        raise ProviderNotAllowedError(
            f"AI processing policy '{policy.value}' does not permit provider "
            f"'{provider.name}' ({provider.locality.value})"
        )
