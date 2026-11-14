"""Identify candidate supply and demand zones from OHLC candles."""
from datetime import datetime, timezone
import math


YAHOO_SYMBOL_ALIASES = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "USDINR": "USDINR=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    "GOLD": "GC=F",
}


def yahoo_chart_to_candles(payload):
    """Normalize Yahoo Finance's chart response to aligned OHLC candle arrays."""
    chart = payload.get("chart") if isinstance(payload, dict) else None
    if not isinstance(chart, dict):
        raise ValueError("Yahoo Finance returned an invalid chart response.")
    if chart.get("error"):
        raise ValueError("Yahoo Finance could not find candles for this symbol.")

    results = chart.get("result")
    if not isinstance(results, list) or not results:
        raise ValueError("Yahoo Finance returned no candles for this symbol.")

    result = results[0]
    if not isinstance(result, dict):
        raise ValueError("Yahoo Finance returned incomplete candle data.")
    timestamps = result.get("timestamp")
    indicators = result.get("indicators")
    quote_groups = indicators.get("quote") if isinstance(indicators, dict) else None
    if not isinstance(timestamps, list) or not isinstance(quote_groups, list) or not quote_groups:
        raise ValueError("Yahoo Finance returned incomplete candle data.")
    quotes = quote_groups[0]
    if not isinstance(quotes, dict):
        raise ValueError("Yahoo Finance returned incomplete candle data.")

    meta = result.get("meta")
    currency = meta.get("currency") if isinstance(meta, dict) else None
    normalized = {"s": "ok", "currency": currency}
    fields = {
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
    }
    for field in ("o", "h", "l", "c"):
        normalized[field] = []
    normalized["t"] = []

    for index, timestamp in enumerate(timestamps):
        try:
            candle = {
                source: float(quotes[source][index])
                for source in fields.values()
            }
            candle_timestamp = int(timestamp)
        except (IndexError, KeyError, TypeError, ValueError, OverflowError):
            continue
        if not all(math.isfinite(value) for value in candle.values()):
            continue
        if candle["low"] > candle["high"]:
            continue
        for field, source in fields.items():
            normalized[field].append(candle[source])
        normalized["t"].append(candle_timestamp)

    if len(normalized["t"]) < 5:
        raise ValueError("Yahoo Finance returned too few valid candles.")
    return normalized


def find_supply_demand_zones(payload, limit=3):
    """Return active swing-pivot zones from normalized candles."""
    keys = ("o", "h", "l", "c", "t")
    if not isinstance(payload, dict) or payload.get("s") != "ok":
        raise ValueError("Candle data is unavailable for this symbol.")

    lengths = [len(payload.get(key, [])) for key in keys]
    candle_count = min(lengths)
    if candle_count < 5:
        raise ValueError("At least five candles are required to find zones.")

    candles = []
    for index in range(candle_count):
        try:
            candle = {
                "open": float(payload["o"][index]),
                "high": float(payload["h"][index]),
                "low": float(payload["l"][index]),
                "close": float(payload["c"][index]),
                "timestamp": int(payload["t"][index]),
            }
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Candle data contains invalid values.") from error
        if not all(math.isfinite(value) for value in candle.values()):
            raise ValueError("Candle data contains invalid values.")
        if candle["low"] > candle["high"]:
            raise ValueError("Candle data contains invalid price ranges.")
        candles.append(candle)

    current_price = candles[-1]["close"]
    if current_price <= 0:
        raise ValueError("Candle data contains an invalid latest close.")

    zones = {"supply": [], "demand": []}
    for index in range(2, len(candles) - 2):
        candle = candles[index]
        previous = candles[index - 2:index]
        following = candles[index + 1:index + 3]
        highs = [item["high"] for item in previous + following]
        lows = [item["low"] for item in previous + following]
        candle_range = candle["high"] - candle["low"]
        if candle_range <= 0:
            continue

        if (
            candle["high"] >= max(highs)
            and candle["high"] > min(highs)
            and candle["close"] <= candle["high"]
        ):
            lower = max(candle["open"], candle["close"])
            if lower >= candle["high"]:
                lower = candle["low"] + candle_range * 0.65
            upper = candle["high"]
            if not any(item["close"] > upper for item in candles[index + 1:]):
                zones["supply"].append(
                    _zone(candles, index, lower, upper, current_price)
                )

        if (
            candle["low"] <= min(lows)
            and candle["low"] < max(lows)
            and candle["close"] >= candle["low"]
        ):
            lower = candle["low"]
            upper = min(candle["open"], candle["close"])
            if upper <= candle["low"]:
                upper = candle["low"] + candle_range * 0.35
            if not any(item["close"] < lower for item in candles[index + 1:]):
                zones["demand"].append(
                    _zone(candles, index, lower, upper, current_price)
                )

    for zone_type, candidates in zones.items():
        candidates.sort(
            key=lambda zone: (
                zone["distance_percent"],
                -zone["formed_timestamp"],
            )
        )
        zones[zone_type] = candidates[:limit]

    return {
        "current_price": round(current_price, 4),
        "currency": payload.get("currency"),
        "zones": zones,
        "last_updated": datetime.fromtimestamp(
            candles[-1]["timestamp"], timezone.utc
        ).isoformat(),
    }


def build_supply_demand_outlook(current_price, zones):
    """Describe a directional bias only when price is testing one zone side."""
    demand_zones = zones.get("demand", [])
    supply_zones = zones.get("supply", [])
    inside_demand = [
        zone for zone in demand_zones
        if zone["low"] <= current_price <= zone["high"]
    ]
    inside_supply = [
        zone for zone in supply_zones
        if zone["low"] <= current_price <= zone["high"]
    ]

    if inside_demand and inside_supply:
        return {
            "bias": "neutral",
            "label": "Neutral · overlapping zones",
            "reason": (
                "Price is inside demand and supply zones at the same time, "
                "so the zone signals conflict."
            ),
            "confirmation": "Wait for price to leave the overlap and retest a zone.",
            "invalidation": None,
            "zone": None,
        }

    if inside_demand:
        zone = min(
            inside_demand,
            key=lambda item: (item["high"] - item["low"], item["low"]),
        )
        return {
            "bias": "bullish",
            "label": "Bullish lean · testing demand",
            "reason": (
                "Price is inside a demand zone, where buyers may respond; "
                "a reaction is not guaranteed."
            ),
            "confirmation": (
                f"Look for a candle close back above {zone['high']:g} "
                "before treating the zone as holding."
            ),
            "invalidation": (
                f"A candle close below {zone['low']:g} would weaken this "
                "demand-zone idea."
            ),
            "zone": {"type": "demand", "low": zone["low"], "high": zone["high"]},
        }

    if inside_supply:
        zone = min(
            inside_supply,
            key=lambda item: (item["high"] - item["low"], item["low"]),
        )
        return {
            "bias": "bearish",
            "label": "Bearish lean · testing supply",
            "reason": (
                "Price is inside a supply zone, where sellers may respond; "
                "a reaction is not guaranteed."
            ),
            "confirmation": (
                f"Look for a candle close back below {zone['low']:g} "
                "before treating the zone as holding."
            ),
            "invalidation": (
                f"A candle close above {zone['high']:g} would weaken this "
                "supply-zone idea."
            ),
            "zone": {"type": "supply", "low": zone["low"], "high": zone["high"]},
        }

    candidates = [
        (zone_type, zone)
        for zone_type, collection in (
            ("demand", demand_zones),
            ("supply", supply_zones),
        )
        for zone in collection
    ]
    if not candidates:
        return {
            "bias": "neutral",
            "label": "Neutral · no active zone",
            "reason": "No active demand or supply zone is available for this timeframe.",
            "confirmation": "Check again when valid zone data is available.",
            "invalidation": None,
            "zone": None,
        }

    zone_type, nearest = min(
        candidates,
        key=lambda item: abs(
            (item[1]["low"] + item[1]["high"]) / 2 - current_price
        ),
    )
    return {
        "bias": "neutral",
        "label": "Neutral · waiting for a zone test",
        "reason": (
            "Price is outside the active zones, so there is no current zone "
            "reaction to support a directional lean."
        ),
        "confirmation": "Watch how price behaves if it reaches the nearest zone.",
        "invalidation": None,
        "zone": {
            "type": zone_type,
            "low": nearest["low"],
            "high": nearest["high"],
            "distance_percent": round(
                abs((nearest["low"] + nearest["high"]) / 2 - current_price)
                / current_price * 100,
                2,
            ),
        },
    }


def _zone(candles, index, lower, upper, current_price):
    lower, upper = sorted((lower, upper))
    touches = sum(
        candle["high"] >= lower and candle["low"] <= upper
        for candle in candles[index + 1:]
    )
    if lower <= current_price <= upper:
        relation = "inside"
    elif current_price < lower:
        relation = "above"
    else:
        relation = "below"
    midpoint = (lower + upper) / 2
    return {
        "low": round(lower, 4),
        "high": round(upper, 4),
        "formed_at": datetime.fromtimestamp(
            candles[index]["timestamp"], timezone.utc
        ).isoformat(),
        "formed_timestamp": candles[index]["timestamp"],
        "touches": touches,
        "relation": relation,
        "distance_percent": round(
            abs(midpoint - current_price) / current_price * 100, 2
        ),
    }
