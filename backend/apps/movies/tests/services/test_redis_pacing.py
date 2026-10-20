from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from apps.movies.services import redis_pacing
from apps.movies.services.redis_pacing import (
    _PACING_SCRIPT,
    _get_raw_client,
    _get_script,
    wait_for_pacing,
)

MODULE = "apps.movies.services.redis_pacing"
KEY = "embedding:pacing:next_slot"


@pytest.fixture(autouse=True)
def clean_script_cache(monkeypatch):
    monkeypatch.setattr(redis_pacing, "_script_cache", {})


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(f"{MODULE}.time.sleep", recorded.append)
    return recorded


def fake_redis(result="0"):
    script = MagicMock(return_value=result)
    client = MagicMock()
    client.register_script.return_value = script
    return client, script


class TestWaitForPacing:
    @pytest.mark.parametrize("interval", [0, 0.0, -1, -0.5])
    def test_non_positive_interval_returns_immediately(self, sleeps, interval):
        with patch(f"{MODULE}._get_raw_client") as get_client:
            wait_for_pacing(KEY, interval)

        get_client.assert_not_called()
        assert sleeps == []

    def test_sleeps_for_the_wait_returned_by_the_script(self, sleeps):
        client, script = fake_redis("0.4")

        with patch(f"{MODULE}._get_raw_client", return_value=client):
            wait_for_pacing(KEY, 0.85)

        assert sleeps == [0.4]

    def test_script_receives_the_key_interval_and_ttl(self, sleeps):
        client, script = fake_redis("0")

        with patch(f"{MODULE}._get_raw_client", return_value=client):
            wait_for_pacing("some:key", 0.85)

        script.assert_called_once_with(keys=["some:key"], args=[0.85, 30])

    @pytest.mark.parametrize("result", ["0", "0.0", "0.000000", b"0"])
    def test_no_sleep_when_the_slot_is_free(self, sleeps, result):
        client, _ = fake_redis(result)

        with patch(f"{MODULE}._get_raw_client", return_value=client):
            wait_for_pacing(KEY, 0.85)

        assert sleeps == []

    @pytest.mark.parametrize(("result", "expected"), [("1.25", 1.25), (b"0.5", 0.5)])
    def test_wait_may_come_back_as_text_or_bytes(self, sleeps, result, expected):
        client, _ = fake_redis(result)

        with patch(f"{MODULE}._get_raw_client", return_value=client):
            wait_for_pacing(KEY, 0.85)

        assert sleeps == [expected]

    def test_the_script_is_registered_once_per_client(self, sleeps):
        client, script = fake_redis("0")

        with patch(f"{MODULE}._get_raw_client", return_value=client):
            wait_for_pacing(KEY, 0.85)
            wait_for_pacing(KEY, 0.85)

        client.register_script.assert_called_once_with(_PACING_SCRIPT)
        assert script.call_count == 2


class TestFallback:
    def _assert_fell_back(self, sleeps, caplog, interval=0.85):
        assert sleeps == [interval]
        assert "falling back" in caplog.text
        assert KEY in caplog.text
        assert caplog.records[-1].exc_info is not None

    def test_failure_to_get_a_client_falls_back_to_a_fixed_sleep(self, sleeps, caplog):
        with patch(f"{MODULE}._get_raw_client", side_effect=ConnectionError("down")):
            with caplog.at_level(logging.WARNING):
                wait_for_pacing(KEY, 0.85)

        self._assert_fell_back(sleeps, caplog)

    def test_failure_to_register_the_script_falls_back(self, sleeps, caplog):
        client = MagicMock()
        client.register_script.side_effect = RuntimeError("no scripting")

        with patch(f"{MODULE}._get_raw_client", return_value=client):
            with caplog.at_level(logging.WARNING):
                wait_for_pacing(KEY, 0.85)

        self._assert_fell_back(sleeps, caplog)

    def test_failure_to_run_the_script_falls_back(self, sleeps, caplog):
        client, script = fake_redis()
        script.side_effect = TimeoutError("slow")

        with patch(f"{MODULE}._get_raw_client", return_value=client):
            with caplog.at_level(logging.WARNING):
                wait_for_pacing(KEY, 0.5)

        self._assert_fell_back(sleeps, caplog, interval=0.5)

    def test_unparsable_script_result_falls_back(self, sleeps, caplog):
        client, _ = fake_redis("not-a-number")

        with patch(f"{MODULE}._get_raw_client", return_value=client):
            with caplog.at_level(logging.WARNING):
                wait_for_pacing(KEY, 0.85)

        self._assert_fell_back(sleeps, caplog)

    def test_a_cache_backend_without_redis_falls_back(self, sleeps, caplog):
        # the test settings use LocMemCache, which has no raw redis client
        with caplog.at_level(logging.WARNING):
            wait_for_pacing(KEY, 0.3)

        self._assert_fell_back(sleeps, caplog, interval=0.3)


class TestGetScript:
    def test_same_client_gets_the_same_registered_script(self):
        client, script = fake_redis()

        first = _get_script(client)
        second = _get_script(client)

        assert first is second is script
        client.register_script.assert_called_once_with(_PACING_SCRIPT)

    def test_each_client_registers_its_own_script(self):
        client_a, script_a = fake_redis()
        client_b, script_b = fake_redis()

        assert _get_script(client_a) is script_a
        assert _get_script(client_b) is script_b
        client_a.register_script.assert_called_once()
        client_b.register_script.assert_called_once()


class TestGetRawClient:
    def test_asks_the_cache_backend_for_a_write_client(self):
        with patch(f"{MODULE}.cache") as cache:
            result = _get_raw_client()

        cache._cache.get_client.assert_called_once_with(write=True)
        assert result is cache._cache.get_client.return_value


class TestPacingScript:
    def test_script_uses_redis_time_and_expires_the_key(self):
        assert "redis.call('TIME')" in _PACING_SCRIPT
        assert "KEYS[1]" in _PACING_SCRIPT
        assert "ARGV[1]" in _PACING_SCRIPT and "ARGV[2]" in _PACING_SCRIPT
        assert "'EX'" in _PACING_SCRIPT
