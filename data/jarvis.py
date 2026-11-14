
"""
FinPulse AI + Jarvis — Single-file application

Features:
- Flask web server
- Indian stock market historical data via Alpha Vantage
- Real job listings via Adzuna
- Jarvis AI chat via OpenAI Responses API
- Company comparison and finance command routing
- API endpoints for your website

Run:
    python3 jarvis.py

Install:
    python3 -m pip install flask requests python-dotenv openai
"""

import os
import re
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ---------------- CONFIGURATION ----------------

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs"

COMPANIES = {
    "RELIANCE.BSE": "Reliance Industries",
    "TCS.BSE": "Tata Consultancy Services",
    "INFY.BSE": "Infosys",
    "HDFCBANK.BSE": "HDFC Bank",
    "ICICIBANK.BSE": "ICICI Bank",
}

SUPPORTED_COMPANIES = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "amazon": "AMZN",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "meta": "META",
    "reliance": "RELIANCE.BSE",
    "infosys": "INFY.BSE",
    "tcs": "TCS.BSE",
}

AI_CLIENT = None
AI_MODEL = os.getenv("JARVIS_MODEL", "gpt-5.1")


def result(intent, message, action=None):
    return {
        "assistant": "Jarvis",
        "intent": intent,
        "message": message,
        "action": action or {},
    }


# ---------------- STOCK MARKET DATA ----------------

def get_market_data(symbol="RELIANCE.BSE"):
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Missing ALPHA_VANTAGE_API_KEY in your .env file."
        )

    symbol = symbol.strip().upper()

    if not re.fullmatch(r"[A-Z0-9.^_-]{1,30}", symbol):
        raise ValueError("Invalid stock symbol.")

    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": api_key,
    }

    response = requests.get(
        ALPHA_VANTAGE_URL,
        params=params,
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()

    if "Error Message" in payload:
        raise ValueError(payload["Error Message"])

    if "Note" in payload or "Information" in payload:
        raise RuntimeError(
            "Market API notice or request limit: "
            + str(payload.get("Note") or payload.get("Information"))
        )

    series = payload.get("Time Series (Daily)")

    if not series:
        raise RuntimeError(
            "No price data returned. Check the symbol, API key, "
            "and your provider's data access."
        )

    dates = sorted(series.keys(), reverse=True)
    latest_date = dates[0]
    latest = series[latest_date]

    previous = series[dates[1]] if len(dates) > 1 else None

    close = float(latest["4. close"])
    previous_close = (
        float(previous["4. close"]) if previous else None
    )

    change = (
        close - previous_close
        if previous_close is not None
        else None
    )

    change_percent = (
        change / previous_close * 100
        if previous_close not in (None, 0)
        else None
    )

    history = []
    for date in dates[:30]:
        row = series[date]
        history.append({
            "date": date,
            "open": float(row["1. open"]),
            "high": float(row["2. high"]),
            "low": float(row["3. low"]),
            "close": float(row["4. close"]),
            "volume": int(row["5. volume"]),
        })

    return {
        "symbol": symbol,
        "name": COMPANIES.get(symbol, symbol),
        "currency": "INR",
        "latest_date": latest_date,
        "latest_close": close,
        "previous_close": previous_close,
        "change": change,
        "change_percent": change_percent,
        "history": history,
        "source": "Alpha Vantage",
        "data_type": "historical daily prices, not guaranteed real-time",
    }


# ---------------- JOBS AND INTERNSHIPS ----------------

def search_jobs(
    keyword="financial analyst",
    location="Bengaluru",
    page=1,
    limit=20,
):
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    country = os.getenv("ADZUNA_COUNTRY", "in").lower()

    if not app_id or not app_key:
        raise RuntimeError(
            "Missing ADZUNA_APP_ID or ADZUNA_APP_KEY in .env."
        )

    keyword = str(keyword).strip()[:100]
    location = str(location).strip()[:100]

    if not keyword:
        raise ValueError("Please provide a job keyword.")

    page = max(1, min(int(page), 10))
    limit = max(1, min(int(limit), 50))

    url = f"{ADZUNA_URL}/{country}/search/{page}"

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": keyword,
        "where": location,
        "results_per_page": limit,
        "content-type": "application/json",
    }

    response = requests.get(url, params=params, timeout=25)
    response.raise_for_status()
    payload = response.json()

    jobs = []

    for item in payload.get("results", []):
        company = item.get("company") or {}
        job_location = item.get("location") or {}
        category = item.get("category") or {}

        jobs.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "company": company.get("display_name", "Not specified"),
            "location": job_location.get("display_name", location),
            "category": category.get("label"),
            "description": item.get("description", ""),
            "posted": item.get("created"),
            "salary_min": item.get("salary_min"),
            "salary_max": item.get("salary_max"),
            "url": item.get("redirect_url"),
            "source": "Adzuna",
        })

    return {
        "keyword": keyword,
        "location": location,
        "count": len(jobs),
        "total_results": payload.get("count", len(jobs)),
        "results": jobs,
        "source": "Adzuna",
    }


# ---------------- JARVIS COMMAND ROUTER ----------------

def interpret_command(command):
    if not isinstance(command, str):
        return result("unknown", "Please enter a text command.")

    text = re.sub(r"\s+", " ", command.casefold()).strip()

    if not text:
        return result("unknown", "Please enter a command.")

    if text in {"hi", "hello", "hey", "hey jarvis"}:
        return result(
            "greeting",
            "Hello! I'm Jarvis, your FinPulse AI assistant.",
            {"page": "dashboard"},
        )

    if text in {"help", "show commands", "what can you do"}:
        return result(
            "help",
            "Try: compare Apple and Microsoft, show the heatmap, "
            "find finance internships in Bengaluru, open analytics, "
            "or explain financial modeling.",
            {"page": "dashboard"},
        )

    # Company comparison
    if any(x in text for x in ("compare", "comparison", "versus", " vs ")):
        symbols = list(dict.fromkeys(
            symbol
            for name, symbol in SUPPORTED_COMPANIES.items()
            if re.search(rf"\b{re.escape(name)}\b", text)
        ))[:2]

        if len(symbols) == 2:
            return result(
                "compare_companies",
                f"Preparing comparison: {symbols[0]} vs {symbols[1]}.",
                {"page": "analytics", "symbols": symbols},
            )

        return result(
            "compare_companies",
            "Please name two supported companies.",
            {"page": "analytics", "symbols": symbols},
        )

    # Market data request
    if any(x in text for x in (
        "stock price", "stock data", "market price", "share price",
        "stock quote", "market data",
    )):
        symbol = "RELIANCE.BSE"

        for name, ticker in SUPPORTED_COMPANIES.items():
            if re.search(rf"\b{re.escape(name)}\b", text):
                symbol = ticker
                break

        return result(
            "market_data",
            f"Fetching available market data for {symbol}.",
            {"handler": "get_market_data", "symbol": symbol},
        )

    # Heatmap
    if "heatmap" in text or "heat map" in text:
        return result(
            "open_heatmap",
            "Opening the sector heatmap.",
            {"page": "heatmap"},
        )

    # Career search
    career_terms = (
        "career", "job", "jobs", "internship", "internships",
        "vacancy", "vacancies", "hiring",
    )

    if any(word in text for word in career_terms):
        location_match = re.search(
            r"\b(?:in|near|around)\s+"
            r"([a-z][a-z .-]{1,45}?)"
            r"(?=\s+(?:for|jobs?|internships?|career|please)\b|$)",
            text,
        )
        location = (
            location_match.group(1).strip(" .-")
            if location_match else "Bengaluru"
        )

        if "finance" in text or "financial" in text:
            keyword = "financial analyst"
        elif "data analyst" in text or "analytics" in text:
            keyword = "data analyst"
        elif "software" in text or "developer" in text:
            keyword = "software developer"
        elif "intern" in text:
            keyword = "internship"
        else:
            keyword = "data analyst"

        return result(
            "open_careers",
            f"Searching career listings for {keyword}.",
            {
                "handler": "search_jobs",
                "page": "careers",
                "keyword": keyword,
                "location": location,
            },
        )

    # Other pages
    page_rules = [
        (("market news", "financial news"), "news", "Opening market news."),
        (("watchlist", "watch list"), "watchlist", "Opening watchlist."),
        (("generate report", "download report", "financial report"),
         "reports", "Opening the reports section."),
        (("analytics", "volatility"),
         "correlation", "Opening financial correlation."),
        (("correlation", "correlations"),
         "correlation", "Opening market correlation."),
        (("market explorer", "open market", "stocks"),
         "market", "Opening the market explorer."),
        (("dashboard", "open home"), "dashboard", "Opening dashboard."),
    ]

    for phrases, page, message in page_rules:
        if any(phrase in text for phrase in phrases):
            return result(
                "navigate",
                message,
                {"page": page},
            )

    return result(
        "chat",
        "Sending your question to Jarvis.",
        {"handler": "ai_chat", "message": command.strip()},
    )


# ---------------- OPENAI AI CHAT ----------------

def ask_jarvis(message):
    global AI_CLIENT

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY in .env.")

    if AI_CLIENT is None:
        from openai import OpenAI
        AI_CLIENT = OpenAI()

    instructions = """
    You are Jarvis, the AI assistant for FinPulse AI.
    Explain finance, markets, analytics, coding, and careers clearly.
    Do not invent prices, jobs, or news. Explain uncertainty.
    Do not claim to place trades or execute actions.
    Provide educational financial information, not guaranteed outcomes.
    """

    response = AI_CLIENT.responses.create(
        model=AI_MODEL,
        instructions=instructions,
        input=message[:12000],
        tools=[{"type": "web_search"}],
    )

    return response.output_text or "I could not generate a response."


# ---------------- FLASK API ROUTES ----------------

@app.get("/")
def home():
    return jsonify({
        "app": "FinPulse AI + Jarvis",
        "status": "running",
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
        "endpoints": [
            "/api/health",
            "/api/market/symbols",
            "/api/market?symbol=RELIANCE.BSE",
            "/api/careers?keyword=financial%20analyst&location=Bengaluru",
        ],
    })


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "market_api_configured": bool(
            os.getenv("ALPHA_VANTAGE_API_KEY")
        ),
        "careers_api_configured": bool(
            os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY")
        ),
        "ai_api_configured": bool(os.getenv("OPENAI_API_KEY")),
    })


@app.get("/api/market/symbols")
def market_symbols():
    return jsonify({
        "symbols": [
            {"symbol": symbol, "name": name}
            for symbol, name in COMPANIES.items()
        ]
    })


@app.get("/api/market")
def market_endpoint():
    symbol = request.args.get("symbol", "RELIANCE.BSE")

    try:
        return jsonify(get_market_data(symbol))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({
            "error": "Market data request failed.",
            "detail": str(exc),
        }), 502


@app.get("/api/careers")
def careers_endpoint():
    try:
        data = search_jobs(
            keyword=request.args.get("keyword", "financial analyst"),
            location=request.args.get("location", "Bengaluru"),
            page=request.args.get("page", 1),
            limit=request.args.get("limit", 20),
        )
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({
            "error": "Job search failed.",
            "detail": str(exc),
        }), 502


@app.post("/api/assistant")
def assistant_endpoint():
    body = request.get_json(silent=True) or {}
    command = body.get("command", "")

    if not isinstance(command, str) or not command.strip():
        return jsonify({"error": "Please provide a command."}), 400

    if len(command) > 12000:
        return jsonify({"error": "Command is too long."}), 400

    routed = interpret_command(command)
    action = routed.get("action", {})

    # Execute data requests on the server rather than only navigating.
    if action.get("handler") == "get_market_data":
        try:
            data = get_market_data(action["symbol"])
            return jsonify({**routed, "data": data})
        except Exception as exc:
            return jsonify({
                **routed,
                "error": "Could not retrieve market data.",
                "detail": str(exc),
            }), 502

    if action.get("handler") == "search_jobs":
        try:
            data = search_jobs(
                keyword=action["keyword"],
                location=action["location"],
            )
            return jsonify({**routed, "data": data})
        except Exception as exc:
            return jsonify({
                **routed,
                "error": "Could not retrieve job listings.",
                "detail": str(exc),
            }), 502

    if routed["intent"] == "chat":
        try:
            answer = ask_jarvis(command)
            return jsonify({
                "assistant": "Jarvis",
                "intent": "chat",
                "message": answer,
                "action": {},
            })
        except Exception as exc:
            return jsonify({
                "error": "Jarvis AI request failed.",
                "detail": type(exc).__name__,
            }), 502

    return jsonify(routed)


# ---------------- START SERVER ----------------

if __name__ == "__main__":
    print("FinPulse AI + Jarvis is starting...")
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(host="127.0.0.1", port=5000, debug=False)
