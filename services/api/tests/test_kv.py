from __future__ import annotations

from saige_api.kv import MemoryStore


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now


def store_with_clock() -> tuple[MemoryStore, FakeClock]:
    clock = FakeClock()
    store = MemoryStore(clock=clock)
    return store, clock


async def test_pop_is_single_use() -> None:
    store, _ = store_with_clock()
    await store.set("state", "value", ttl_seconds=60)
    assert await store.pop("state") == "value"
    assert await store.pop("state") is None


async def test_values_expire() -> None:
    store, clock = store_with_clock()
    await store.set("state", "value", ttl_seconds=10)
    clock.now += 11
    assert await store.pop("state") is None


async def test_incr_counts_within_window_and_resets() -> None:
    store, clock = store_with_clock()
    assert [await store.incr("k", ttl_seconds=60) for _ in range(3)] == [1, 2, 3]
    clock.now += 61
    assert await store.incr("k", ttl_seconds=60) == 1


async def test_memory_is_bounded() -> None:
    store, _ = store_with_clock()
    store.MAX_KEYS = 100
    for i in range(250):
        await store.set(f"k{i}", "v", ttl_seconds=60 + i)
    assert len(store._data) <= 101
