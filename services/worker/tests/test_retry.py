from __future__ import annotations

import random

import pytest

from saige_worker.retry import RetryPolicy


def test_backoff_doubles_and_caps() -> None:
    policy = RetryPolicy(max_attempts=10, base_delay_seconds=5, max_delay_seconds=60)
    assert [policy.backoff_ceiling(a) for a in range(1, 7)] == [5, 10, 20, 40, 60, 60]


def test_jittered_delay_within_ceiling() -> None:
    policy = RetryPolicy()
    rng = random.Random(42)
    for attempt in range(1, 8):
        delay = policy.next_delay(attempt, rng)
        assert 0 <= delay <= policy.backoff_ceiling(attempt)


def test_should_retry_until_max_attempts() -> None:
    policy = RetryPolicy(max_attempts=3)
    assert policy.should_retry(1)
    assert policy.should_retry(2)
    assert not policy.should_retry(3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"base_delay_seconds": 0},
        {"base_delay_seconds": 10, "max_delay_seconds": 5},
    ],
)
def test_invalid_policies_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match=r"."):
        RetryPolicy(**kwargs)  # type: ignore[arg-type]
