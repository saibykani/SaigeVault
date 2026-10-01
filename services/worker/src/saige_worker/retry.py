"""Retry policy: capped exponential backoff with full jitter.

Jobs that exhaust `max_attempts` are moved to the dead-letter state
(JobStatus.DEAD_LETTERED) for inspection instead of being retried forever.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 5
    base_delay_seconds: float = 5.0
    max_delay_seconds: float = 15 * 60.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay_seconds <= 0 or self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("invalid delay bounds")

    def should_retry(self, attempt: int) -> bool:
        """`attempt` is the 1-based number of the attempt that just failed."""
        return attempt < self.max_attempts

    def backoff_ceiling(self, attempt: int) -> float:
        exponent = max(attempt - 1, 0)
        return min(self.max_delay_seconds, self.base_delay_seconds * 2.0**exponent)

    def next_delay(self, attempt: int, rng: random.Random | None = None) -> float:
        # Full jitter spreads retries out after a provider outage. Not used
        # for anything security-sensitive, so a PRNG is appropriate.
        generator = rng or random.Random()  # noqa: S311
        return generator.uniform(0, self.backoff_ceiling(attempt))
