"""Market data adapter with cached Finnhub quotes and a demo-data fallback."""
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Lock
from time import monotonic

import requests

_DEMO_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "demo_data.py"
_DEMO_DATA_SPEC = spec_from_file_location("finpulse_demo_data", _DEMO_DATA_PATH)
if _DEMO_DATA_SPEC is None or _DEMO_DATA_SPEC.loader is None:
    raise ImportError(f"Could not load demo data from {_DEMO_DATA_PATH}")
_DEMO_DATA_MODULE = module_from_spec(_DEMO_DATA_SPEC)
_DEMO_DATA_SPEC.loader.exec_module(_DEMO_DATA_MODULE)
COMPANIES = _DEMO_DATA_MODULE.COMPANIES

FINNHUB_URL = "https://finnhub.io/api/v1/quote"
QUOTE_CACHE_SECONDS = 60
_quote_cache = {
    "rows": None,
    "at": 0.0,
    "updated_at": None,
    "mode": "illustrative_demo",
}
_quote_lock = Lock()


def _get_live_companies():
    """Fetch configured Finnhub quotes; fall back to clearly labeled demo values."""
    token = os.getenv("FINNHUB_API_KEY", "").strip()
    if not token:
        return [dict(company) for company in COMPANIES], "illustrative_demo", None

    now = monotonic()
    with _quote_lock:
        if (
            _quote_cache["rows"] is not None
            and now - _quote_cache["at"] < QUOTE_CACHE_SECONDS
        ):
            return (
                [dict(company) for company in _quote_cache["rows"]],
                _quote_cache["mode"],
                _quote_cache["updated_at"],
            )

        try:
            def fetch_quote(original):
                response = requests.get(
                    FINNHUB_URL,
                    params={"symbol": original["symbol"], "token": token},
                    timeout=5,
                )
                response.raise_for_status()
                quote = response.json()
                price = float(quote.get("c") or 0)
                previous_close = float(quote.get("pc") or 0)
                if price <= 0 or previous_close <= 0:
                    raise ValueError(
                        f"Finnhub returned no current quote for {original['symbol']}."
                    )

                row = dict(original)
                row["price"] = round(price, 4)
                change = quote.get("dp")
                if change is None:
                    change = ((price / previous_close) - 1) * 100
                row["change"] = round(float(change), 2)
                return row

            with ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(fetch_quote, COMPANIES))
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            _quote_cache.update(
                rows=rows,
                at=now,
                updated_at=timestamp,
                mode="live",
            )
            return [dict(company) for company in rows], "live", timestamp
        except (requests.RequestException, ValueError, TypeError) as exc:
            _quote_cache.update(
                rows=None,
                at=0.0,
                updated_at=None,
                mode="illustrative_demo",
            )
            logging.getLogger(__name__).warning(
                "Live market quote fetch failed; using demo data: %s",
                exc,
            )
            return [dict(company) for company in COMPANIES], "illustrative_demo", None


def market_status():
    _, mode, updated_at = _get_live_companies()
    return {"data_mode": mode, "updated_at": updated_at}


def all_companies(sector="All", sort="change"):
    source, _, _ = _get_live_companies()
    sector_name = (sector or "All").strip()
    rows = [
        dict(company)
        for company in source
        if sector_name in ("", "All")
        or sector_name.lower() in str(company.get("sector", "")).lower()
        or str(company.get("sector", "")).lower() in sector_name.lower()
    ]
    fields = {
        "change": "change",
        "price": "price",
        "symbol": "symbol",
        "market_cap": "market_cap",
    }
    key = fields.get((sort or "change").strip().lower(), "change")
    rows.sort(
        key=lambda company: company.get(key, 0) or 0,
        reverse=key != "symbol",
    )
    return rows


def get_company(symbol):
    if symbol is None:
        return None
    normalized = str(symbol).strip().upper()
    if not normalized:
        return None
    return next(
        (dict(company) for company in all_companies() if company.get("symbol") == normalized),
        None,
    )


def summary():
    rows, mode, updated_at = _get_live_companies()
    if not rows:
        return {
            "count": 0,
            "average_change": 0.0,
            "best": None,
            "worst": None,
            "data_mode": mode,
            "updated_at": updated_at,
        }
    best = max(rows, key=lambda company: company["change"])
    worst = min(rows, key=lambda company: company["change"])
    return {
        "count": len(rows),
        "average_change": round(
            sum(company["change"] for company in rows) / len(rows),
            2,
        ),
        "best": best,
        "worst": worst,
        "data_mode": mode,
        "updated_at": updated_at,
    }
