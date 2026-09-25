from __future__ import annotations

import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)

_PACING_SCRIPT = """
local key = KEYS[1]
local min_interval = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

local time_parts = redis.call('TIME')
local now = tonumber(time_parts[1]) + (tonumber(time_parts[2]) / 1000000)

local next_slot = tonumber(redis.call('GET', key))
if next_slot == nil or next_slot < now then
    next_slot = now
end

redis.call('SET', key, tostring(next_slot + min_interval), 'EX', ttl)

local wait = next_slot - now
if wait < 0 then
    wait = 0
end

return tostring(wait)
"""

_KEY_TTL_SECONDS = 30
_script_cache = {}


def _get_raw_client():
    return cache._cache.get_client(write=True)


def _get_script(client):
    cached = _script_cache.get(id(client))
    if cached is None:
        cached = client.register_script(_PACING_SCRIPT)
        _script_cache[id(client)] = cached
    return cached


def wait_for_pacing(key: str, min_interval: float) -> None:
    if min_interval <= 0:
        return

    try:
        client = _get_raw_client()
        script = _get_script(client)
        wait_seconds = float(script(keys=[key], args=[min_interval, _KEY_TTL_SECONDS]))
    except Exception:
        logger.warning(
            "Redis pacing script failed for key '%s'; falling back to a "
            "fixed %.2fs sleep.", key, min_interval, exc_info=True,
        )
        wait_seconds = min_interval

    if wait_seconds > 0:
        time.sleep(wait_seconds)
