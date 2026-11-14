"""Finnhub news API adapter."""
import os
from datetime import datetime, timedelta, timezone

import requests

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/news"
FINNHUB_COMPANY_NEWS_URL = "https://finnhub.io/api/v1/company-news"


class FinnhubConfigurationError(RuntimeError):
    """Raised when a Finnhub API key is not configured."""


def get_news(symbol="GENERAL", limit=40):
    normalized_symbol = (symbol or "GENERAL").strip().upper()
    if not normalized_symbol:
        normalized_symbol = "GENERAL"
    if not 1 <= limit <= 40:
        raise ValueError("The news limit must be between 1 and 40.")

    token = os.getenv("FINNHUB_API_KEY", "").strip()
    if not token:
        raise FinnhubConfigurationError("FINNHUB_API_KEY is not configured.")

    if normalized_symbol == "GENERAL":
        url = FINNHUB_NEWS_URL
        params = {"category": "general", "token": token}
    else:
        today = datetime.now(timezone.utc).date()
        url = FINNHUB_COMPANY_NEWS_URL
        params = {
            "symbol": normalized_symbol,
            "from": (today - timedelta(days=7)).isoformat(),
            "to": today.isoformat(),
            "token": token,
        }

    try:
        response = requests.get(url, params=params, timeout=8)
        response.raise_for_status()
        articles = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(f"Finnhub news request failed: {exc}") from exc

    if not isinstance(articles, list):
        raise RuntimeError("Finnhub returned an invalid news response.")
    return articles[:limit]
