# catalog_cache.py
# Cache + search utilities for smscenter prices catalog
# Updates every PRICES_CACHE_TTL_SECONDS (30 minutes as chosen)

import time
from typing import Dict, List, Optional, Tuple

import vak_api
from config import VAK_API_KEY, PRICES_CACHE_TTL_SECONDS, PROFIT_RATE


# In-memory cache
_last_fetch_ts: float = 0.0
_flat: List[dict] = []               # [{country, service, count, cost}, ...]
_by_country: Dict[str, List[dict]] = {}  # country -> list of entries


def _now() -> float:
    return time.time()


def _round_price_one_decimal(x: float) -> float:
    # rounding strategy: 1 decimal
    return round(x + 1e-9, 1)


def sell_price(provider_cost: float) -> float:
    """
    Apply profit rate (50%) and round to 1 decimal.
    """
    return _round_price_one_decimal(provider_cost * (1.0 + PROFIT_RATE))


def refresh_if_needed(force: bool = False) -> None:
    global _last_fetch_ts, _flat, _by_country

    if not force and (_now() - _last_fetch_ts) < PRICES_CACHE_TTL_SECONDS and _flat:
        return

    prices_json = vak_api.get_prices(VAK_API_KEY)
    flat = vak_api.normalize_prices(prices_json)

    # Keep only entries with positive availability and cost > 0
    flat = [e for e in flat if e.get("count", 0) > 0 and e.get("cost", 0) > 0]

    by_country: Dict[str, List[dict]] = {}
    for e in flat:
        c = e["country"]
        by_country.setdefault(c, []).append(e)

    # Sort services per country by availability desc then cost asc
    for c, lst in by_country.items():
        lst.sort(key=lambda x: (-int(x.get("count", 0)), float(x.get("cost", 0))))

    _flat = flat
    _by_country = by_country
    _last_fetch_ts = _now()


def list_countries() -> List[str]:
    refresh_if_needed()
    return sorted(_by_country.keys())


def search_countries(query: str, limit: int = 10) -> List[str]:
    refresh_if_needed()
    q = (query or "").strip().lower()
    if not q:
        return list_countries()[:limit]

    # simple contains match
    matches = [c for c in _by_country.keys() if q in c.lower()]
    matches.sort()
    return matches[:limit]


def top_countries(limit: int = 10) -> List[str]:
    """
    Countries with highest total availability.
    """
    refresh_if_needed()
    scores: List[Tuple[str, int]] = []
    for c, lst in _by_country.items():
        total = sum(int(x.get("count", 0)) for x in lst)
        scores.append((c, total))
    scores.sort(key=lambda t: -t[1])
    return [c for c, _ in scores[:limit]]


def search_services(country: str, query: str, limit: int = 10) -> List[dict]:
    """
    Return list of entries: {country, service, count, cost, sell}
    """
    refresh_if_needed()
    c = (country or "").strip()
    if c not in _by_country:
        return []

    q = (query or "").strip().lower()
    entries = _by_country[c]

    if not q:
        out = entries[:limit]
    else:
        # simple contains match on service code
        out = [e for e in entries if q in e["service"].lower()][:limit]

    # add sell price
    enriched = []
    for e in out:
        enriched.append(
            {
                "country": e["country"],
                "service": e["service"],
                "count": e["count"],
                "cost": e["cost"],
                "sell": sell_price(float(e["cost"])),
            }
        )
    return enriched


def get_service_entry(country: str, service_code: str) -> Optional[dict]:
    refresh_if_needed()
    c = (country or "").strip()
    s = (service_code or "").strip()
    if c not in _by_country:
        return None

    for e in _by_country[c]:
        if e["service"] == s:
            return {
                "country": e["country"],
                "service": e["service"],
                "count": e["count"],
                "cost": e["cost"],
                "sell": sell_price(float(e["cost"])),
            }
    return None