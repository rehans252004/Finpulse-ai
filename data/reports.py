import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from flask import Blueprint, jsonify

from .market_service import COMPANIES

bp = Blueprint("reports", __name__, url_prefix="/api/reports")

FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"


def fetch_quote(company, token):
    response = requests.get(
        FINNHUB_QUOTE_URL,
        params={"symbol": company["symbol"], "token": token},
        timeout=8,
    )
    response.raise_for_status()
    quote = response.json()

    if not quote.get("c"):
        return None

    return {
        "symbol": company["symbol"],
        "name": company["name"],
        "sector": company["sector"],
        "price": quote["c"],
        "change": quote.get("dp", 0),
        "high": quote.get("h"),
        "low": quote.get("l"),
        "open": quote.get("o"),
        "previous_close": quote.get("pc"),
        "timestamp": quote.get("t"),
    }


@bp.get("/live")
def live_market_data():
    token = os.getenv("FINNHUB_API_KEY", "").strip()
    if not token:
        return jsonify(error="FINNHUB_API_KEY is not configured."), 503

    quotes = []
    failed_symbols = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(fetch_quote, company, token): company
            for company in COMPANIES
        }
        for future in as_completed(futures):
            company = futures[future]
            try:
                quote = future.result()
                if quote:
                    quotes.append(quote)
                else:
                    failed_symbols.append(company["symbol"])
            except (requests.RequestException, ValueError) as exc:
                bp.logger.warning(
                    "Finnhub quote failed for %s: %s",
                    company["symbol"],
                    exc,
                )
                failed_symbols.append(company["symbol"])

    if not quotes:
        return jsonify(error="Finnhub returned no live quotes."), 502

    quotes.sort(key=lambda item: item["symbol"])
    return jsonify(
        source="Finnhub",
        data_mode="live",
        quotes=quotes,
        failed_symbols=sorted(failed_symbols),
    )