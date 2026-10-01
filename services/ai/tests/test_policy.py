from __future__ import annotations

import pytest

from saige_ai.policy import (
    AIProcessingPolicy,
    ProviderNotAllowedError,
    ensure_allowed,
    is_allowed,
)
from saige_ai.providers import Provider, ProviderLocality


class _FakeProvider:
    def __init__(self, locality: ProviderLocality) -> None:
        self._locality = locality

    @property
    def name(self) -> str:
        return "fake"

    @property
    def locality(self) -> ProviderLocality:
        return self._locality


@pytest.mark.parametrize(
    ("policy", "locality", "expected"),
    [
        (AIProcessingPolicy.DISABLED, ProviderLocality.LOCAL, False),
        (AIProcessingPolicy.DISABLED, ProviderLocality.THIRD_PARTY, False),
        (AIProcessingPolicy.LOCAL_ONLY, ProviderLocality.LOCAL, True),
        (AIProcessingPolicy.LOCAL_ONLY, ProviderLocality.THIRD_PARTY, False),
        (AIProcessingPolicy.THIRD_PARTY_ALLOWED, ProviderLocality.LOCAL, True),
        (AIProcessingPolicy.THIRD_PARTY_ALLOWED, ProviderLocality.THIRD_PARTY, True),
    ],
)
def test_policy_matrix(
    policy: AIProcessingPolicy, locality: ProviderLocality, expected: bool
) -> None:
    assert is_allowed(policy, locality) is expected


def test_ensure_allowed_raises_for_third_party_under_local_only() -> None:
    provider = _FakeProvider(ProviderLocality.THIRD_PARTY)
    assert isinstance(provider, Provider)
    with pytest.raises(ProviderNotAllowedError):
        ensure_allowed(AIProcessingPolicy.LOCAL_ONLY, provider)
