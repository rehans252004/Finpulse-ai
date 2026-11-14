"""Daily reference FX rates and supported currencies from Frankfurter."""
import re
from threading import Lock
from time import monotonic

import requests

BASE_URL = "https://api.frankfurter.dev/v2"
CURRENCY_CACHE_SECONDS = 24 * 60 * 60
RATE_CACHE_SECONDS = 60 * 60
_cache_lock = Lock()
_currency_cache = {"items": None, "at": 0.0}
_rate_cache = {}


def get_currencies():
    now = monotonic()
    with _cache_lock:
        if _currency_cache["items"] is not None and now - _currency_cache["at"] < CURRENCY_CACHE_SECONDS:
            return _currency_cache["items"]
        try:
            response = requests.get(f"{BASE_URL}/currencies", timeout=8)
            response.raise_for_status()
            raw = response.json()
            currencies = [
                {
                    "code": item["iso_code"],
                    "name": item["name"],
                    "symbol": item.get("symbol", item["iso_code"]),
                }
                for item in raw
                if re.fullmatch(r"[A-Z]{3}", item.get("iso_code", "")) and item.get("name")
            ]
            currencies.sort(key=lambda item: item["code"])
            if not currencies:
                raise ValueError("No currencies were returned by the FX provider.")
            _currency_cache.update(items=currencies, at=now)
            return currencies
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            raise RuntimeError("Could not load supported currencies. Please try again.") from exc


def get_rate(base, quote):
    base, quote = base.upper(), quote.upper()
    if not re.fullmatch(r"[A-Z]{3}", base) or not re.fullmatch(r"[A-Z]{3}", quote):
        raise ValueError("Choose valid three-letter currency codes.")
    if base == quote:
        return {"base": base, "quote": quote, "rate": 1.0, "date": None, "source": "Frankfurter reference rates"}

    now = monotonic()
    cache_key = (base, quote)
    with _cache_lock:
        cached = _rate_cache.get(cache_key)
        if cached and now - cached[0] < RATE_CACHE_SECONDS:
            return cached[1]
        try:
            response = requests.get(f"{BASE_URL}/rate/{base.lower()}/{quote.lower()}", timeout=8)
            response.raise_for_status()
            item = response.json()
            result = {
                "base": item["base"],
                "quote": item["quote"],
                "rate": float(item["rate"]),
                "date": item["date"],
                "source": "Frankfurter reference rates",
            }
            _rate_cache[cache_key] = (now, result)
            return result
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            raise RuntimeError("Could not load this exchange rate. Check the currencies and try again.") from exc
