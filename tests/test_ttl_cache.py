from rwcwx import ttl_cache


def test_ttl_cache_reuses_until_expiry_and_replaces_old_dates():
    ttl_cache.clear()
    clock = [0.0]
    calls = []

    def fn(v):
        calls.append(v)
        return v

    now = lambda: clock[0]  # noqa: E731
    assert ttl_cache.cached(("year", 1), 60, lambda: fn("a"), now) == "a"
    clock[0] = 30
    assert ttl_cache.cached(("year", 1), 60, lambda: fn("b"), now) == "a"
    clock[0] = 61
    assert ttl_cache.cached(("year", 1), 60, lambda: fn("c"), now) == "c"
    assert ttl_cache.cached(("year", 2), 60, lambda: fn("d"), now) == "d"  # new day: fresh value
    assert ttl_cache.cached(("month", 2), 60, lambda: fn("e"), now) == "e"
    assert len(ttl_cache._store) == 2  # ("year", 1) was dropped
    assert calls == ["a", "c", "d", "e"]
    ttl_cache.clear()
