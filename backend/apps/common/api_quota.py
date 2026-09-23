from __future__ import annotations

import logging
import math
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.common.exceptions import QuotaExceeded

logger = logging.getLogger(__name__)

_PERIOD_TTL = {
    "day": int(timedelta(days=2).total_seconds()),
    "week": int(timedelta(days=8).total_seconds()),
}


def _windows(client: str) -> list[tuple[str, str, int, int]]:
    limits = getattr(settings, "API_QUOTAS", {}).get(client) or {}
    today = timezone.localdate()
    iso = today.isocalendar()
    keys = {
        "day": f"quota:{client}:day:{today.isoformat()}",
        "week": f"quota:{client}:week:{iso.year}-W{iso.week:02d}",
    }

    return [
        (period, keys[period], _PERIOD_TTL[period], int(limit))
        for period, limit in limits.items()
        if period in keys and limit is not None
    ]


def _incr(key: str, units: int, ttl: int) -> int:
    cache.add(key, 0, timeout=ttl)
    try:
        return cache.incr(key, units)
    except ValueError:
        cache.set(key, units, timeout=ttl)
        return units


def _decr(key: str, units: int) -> None:
    try:
        if cache.decr(key, units) < 0:
            cache.set(key, 0)
    except ValueError:
        pass


def consume(client: str, units: int = 1) -> None:
    touched: list[str] = []
    for period, key, ttl, limit in _windows(client):
        touched.append(key)
        if _incr(key, units, ttl) > limit:
            for k in touched:
                _decr(k, units)
            logger.warning("API quota exceeded for '%s' (%s limit %d).", client, period, limit)
            raise QuotaExceeded(client, period, limit)


def refund(client: str, units: int = 1) -> None:
    for _period, key, _ttl, _limit in _windows(client):
        _decr(key, units)


def remaining(client: str) -> int | None:
    values = [
        max(limit - int(cache.get(key, 0)), 0)
        for _period, key, _ttl, limit in _windows(client)
    ]

    return min(values) if values else None


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text.encode("utf-8")) / 3))


def cost_units(client: str, input_tokens: int = 0, output_tokens: int = 0) -> int:
    pricing = getattr(settings, "API_PRICING_USD_PER_M_TOKENS", {})[client]
    eur_per_usd = 0.90
    micro_eur = (
        input_tokens * pricing.get("input", 0.0)
        + output_tokens * pricing.get("output", 0.0)
    ) * eur_per_usd

    return math.ceil(micro_eur)


def text_cost(client: str, text: str) -> int:
    return cost_units(client, input_tokens=estimate_tokens(text))


def adjust(client: str, delta: int) -> None:
    if delta < 0:
        refund(client, -delta)
    elif delta > 0:
        for _period, key, ttl, _limit in _windows(client):
            _incr(key, delta, ttl)
