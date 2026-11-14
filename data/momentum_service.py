"""Explainable momentum scoring based on live price and fundamentals."""
import math
import time
from threading import Lock

import requests
from flask import current_app

FINNHUB_METRIC_URL = "https://finnhub.io/api/v1/stock/metric"
FUNDAMENTAL_CACHE = {}
FUNDAMENTAL_CACHE_LOCK = Lock()
FUNDAMENTAL_CACHE_TTL = 900
FUNDAMENTAL_FAILURE_CACHE_TTL = 60


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _to_percentage(value):
    if value is None:
        return None
    return value * 100 if abs(value) <= 2 else value


def fetch_fundamental_metrics(symbol, token):
    cache_key = symbol.upper()
    now = time.monotonic()
    with FUNDAMENTAL_CACHE_LOCK:
        cached = FUNDAMENTAL_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return dict(cached[1]) if cached[1] else None

    metrics = None
    try:
        response = requests.get(
            FINNHUB_METRIC_URL,
            params={
                "symbol": cache_key,
                "metric": "all",
                "token": token,
            },
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        raw_metrics = payload.get("metric") if isinstance(payload, dict) else None
        if isinstance(raw_metrics, dict):
            aliases = {
                "revenue_growth": ("revenueGrowthTTMYoy", "revenueGrowth5Y"),
                "earnings_growth": ("epsGrowthTTMYoy", "epsGrowth5Y"),
                "return_on_equity": ("roeTTM", "roeRfy"),
            }
            parsed = {}
            for name, keys in aliases.items():
                value = next(
                    (
                        _number(raw_metrics.get(key))
                        for key in keys
                        if _number(raw_metrics.get(key)) is not None
                    ),
                    None,
                )
                parsed[name] = _to_percentage(value)
            if sum(value is not None for value in parsed.values()) >= 2:
                metrics = parsed
    except (requests.RequestException, ValueError, TypeError) as error:
        current_app.logger.warning(
            "Finnhub fundamental metrics lookup failed for %s (%s).",
            cache_key,
            type(error).__name__,
        )

    ttl = FUNDAMENTAL_CACHE_TTL if metrics else FUNDAMENTAL_FAILURE_CACHE_TTL
    with FUNDAMENTAL_CACHE_LOCK:
        FUNDAMENTAL_CACHE[cache_key] = (time.monotonic() + ttl, metrics)
    return dict(metrics) if metrics else None


def score_momentum(daily_change, metrics):
    change = _number(daily_change)
    if change is None or not metrics:
        return None

    technical_score = round(50 + max(-10, min(10, change)) * 5)
    fundamental_factors = []
    for metric_name in ("revenue_growth", "earnings_growth", "return_on_equity"):
        value = _number(metrics.get(metric_name))
        if value is not None:
            normalized = max(-20, min(20, value))
            fundamental_factors.append(50 + normalized * 2.5)

    if len(fundamental_factors) < 2:
        return None

    fundamental_score = round(
        sum(fundamental_factors) / len(fundamental_factors)
    )
    combined_score = round((technical_score + fundamental_score) / 2)
    if combined_score >= 65:
        signal = "Stronger momentum"
    elif combined_score <= 35:
        signal = "Weaker momentum"
    else:
        signal = "Mixed momentum"

    return {
        "score": combined_score,
        "signal": signal,
        "technical_score": technical_score,
        "fundamental_score": fundamental_score,
    }
