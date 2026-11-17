"""Forecast upstream HTTP retries, IPv4 preference, and single-flight cache."""
import socket
import threading
from unittest.mock import Mock, patch

import pytest
import requests

from rwcwx.forecast import http as fc_http
from rwcwx.forecast import openmeteo
from rwcwx.forecast.cache import UpstreamCache


@pytest.fixture(autouse=True)
def _reset_http():
    fc_http.reset_session()
    yield
    fc_http.reset_session()


def _ok(payload):
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json = Mock(return_value=payload)
    return resp


def test_get_json_retries_after_read_timeout():
    calls = []

    def side_effect(*args, **kwargs):
        calls.append(kwargs.get("timeout"))
        if len(calls) == 1:
            raise requests.exceptions.ReadTimeout("read")
        return _ok({"hourly": {"time": ["2026-11-17T00:00"]}})

    with patch.object(requests.Session, "get", side_effect=side_effect):
        data = fc_http.get_json("https://example.invalid/v1/forecast")
    assert data["hourly"]["time"] == ["2026-11-17T00:00"]
    assert len(calls) == 2
    assert calls[0] == (fc_http.CONNECT_TIMEOUT, fc_http.READ_TIMEOUT)


def test_get_json_gives_up_after_two_timeouts():
    with patch.object(requests.Session, "get", side_effect=requests.exceptions.ReadTimeout("read")):
        with pytest.raises(requests.exceptions.ReadTimeout):
            fc_http.get_json("https://example.invalid/v1/forecast")


def test_openmeteo_get_json_uses_shared_helper():
    with patch("rwcwx.forecast.openmeteo.http_get_json", return_value={"ok": 1}) as fn:
        assert openmeteo.get_json("https://api.open-meteo.com/v1/forecast") == {"ok": 1}
        fn.assert_called_once()
        kwargs = fn.call_args.kwargs
        assert kwargs["timeout"] == openmeteo.TIMEOUT
        assert kwargs["accept"] == "application/json"


def test_prefer_ipv4_sets_urllib3_family():
    import urllib3.util.connection as u3c
    fc_http._ipv4_applied = False
    fc_http.prefer_ipv4()
    assert u3c.allowed_gai_family() == socket.AF_INET
    fc_http.prefer_ipv4()  # idempotent
    assert u3c.allowed_gai_family() == socket.AF_INET


def test_cache_single_flight_calls_fn_once():
    store = UpstreamCache("test", "Test")
    hold = threading.Event()
    released = threading.Event()
    calls = []

    def fn():
        calls.append(threading.current_thread().name)
        released.set()
        hold.wait(2)
        return {"v": 1}

    t = threading.Thread(target=lambda: store.safe("k", 60, fn), name="b")
    # First caller starts the fetch; the second waits and reuses the result.
    first = threading.Thread(target=lambda: store.safe("k", 60, fn), name="a")
    first.start()
    assert released.wait(2)
    t.start()
    # Give the second thread a moment to block on the flight lock, then finish the fetch.
    threading.Event().wait(0.05)
    hold.set()
    first.join(2)
    t.join(2)
    assert calls == ["a"]
    assert store.status("k")["stale"] is False
    store.clear()


def test_fresh_disk_is_adopted_without_fetch_across_cache_instances(tmp_path, monkeypatch):
    monkeypatch.setenv("RWCWX_FORECAST_CACHE_DIR", str(tmp_path))
    a = UpstreamCache("sf", "SF")
    clock = [10.0]
    wall = [1_700_000_000.0]
    a.safe("k", 600, lambda: {"n": 1}, now=lambda: clock[0], wall=lambda: wall[0])
    # New process / new worker: empty memory, same disk dir.
    b = UpstreamCache("sf", "SF")
    calls = []
    val = b.safe("k", 600, lambda: calls.append("no") or {"n": 2},
                 now=lambda: clock[0] + 5, wall=lambda: wall[0] + 5)
    assert val == {"n": 1}
    assert calls == []
    assert b.status("k")["stale"] is False
    a.clear()
    b.clear()
