import re
from datetime import datetime, timezone


COMPANY_SYMBOLS = {
    "tata consultancy services": "TCS",
    "bharti airtel": "BHARTIARTL",
    "hdfc bank": "HDFCBANK",
    "icici bank": "ICICIBANK",
    "reliance": "RELIANCE",
    "infosys": "INFY",
    "wipro": "WIPRO",
    "nvidia": "NVDA",
    "microsoft": "MSFT",
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "amazon": "AMZN",
    "apple": "AAPL",
    "tesla": "TSLA",
    "meta": "META",
    "tcs": "TCS",
    "sbi": "SBIN",
    "itc": "ITC",
    "aapl": "AAPL",
    "msft": "MSFT",
    "googl": "GOOGL",
    "nvda": "NVDA",
    "amzn": "AMZN",
    "tsla": "TSLA",
    "infy": "INFY",
    "hdfcbank": "HDFCBANK",
    "icicibank": "ICICIBANK",
    "jpmorgan": "JPM",
    "jpm": "JPM",
    "bank of america": "BAC",
    "exxon": "XOM",
}

PAGE_ALIASES = {
    "overview": ("overview", "dashboard", "home", "main page"),
    "market": ("market", "stocks", "stock explorer", "market explorer"),
    "heatmap": ("heatmap", "heat map"),
    "correlation": (
        "correlation",
        "correlations",
        "relative movement",
        "co-movement",
        "market correlation",
    ),
    "supplyDemand": (
        "supply demand",
        "supply and demand",
        "supply & demand",
        "demand zone",
        "supply zone",
    ),
    "careers": ("careers", "career", "jobs", "internships"),
    "news": ("news", "headlines"),
}

SECTORS = {
    "technology": "Technology",
    "tech": "Technology",
    "banking": "Banking",
    "energy": "Energy",
    "healthcare": "Healthcare",
    "automotive": "Automotive",
    "consumer": "Consumer",
    "industrials": "Industrials",
    "utilities": "Utilities",
    "telecom": "Telecom",
    "real estate": "Real Estate",
    "materials": "Materials",
    "semiconductors": "Semiconductors",
}

CAREER_LOCATIONS = (
    "bengaluru", "bangalore", "mumbai", "pune", "chennai", "hyderabad",
    "delhi", "noida", "gurugram", "gurgaon", "kolkata", "india", "remote",
)


def _company_symbols(text: str) -> list:
    matches = []
    for name, symbol in COMPANY_SYMBOLS.items():
        match = re.search(rf"\b{re.escape(name)}\b", text)
        if match:
            matches.append((match.start(), -len(name), symbol))

    found = []
    for _, _, symbol in sorted(matches):
        if symbol not in found:
            found.append(symbol)
    return found


def interpret_command(command: str, history=None, market_data=None) -> dict:
    """Turn a Jarvis request into a safe, in-app FinPulse action."""
    text = re.sub(r"\s+", " ", command.casefold()).strip()
    history = [
        item for item in (history or [])
        if isinstance(item, dict)
        and item.get("role") in {"user", "assistant"}
        and isinstance(item.get("content"), str)
    ][-10:]

    def response(intent, message, action_type=None, context=None, **details):
        action = {"type": action_type, **details} if action_type else {}
        result = {
            "assistant": "Jarvis",
            "intent": intent,
            "message": message,
            "action": action,
        }
        if context:
            result["context"] = context
        return result

    def prior_symbols():
        for item in reversed(history):
            if item["role"] != "assistant":
                continue
            context = item.get("context")
            if isinstance(context, dict):
                symbols = context.get("focus_symbols", [])
                if isinstance(symbols, list):
                    valid_symbols = [
                        symbol for symbol in symbols
                        if isinstance(symbol, str)
                        and re.fullmatch(r"[A-Z0-9._-]{1,15}", symbol)
                    ]
                    if valid_symbols:
                        return valid_symbols[:8]
            symbols = _company_symbols(item["content"].casefold())
            if symbols:
                return symbols[:8]
        return []

    def prior_sector():
        for item in reversed(history):
            if item["role"] != "assistant":
                continue
            context = item.get("context")
            if isinstance(context, dict):
                sector = context.get("focus_sector")
                if sector in set(SECTORS.values()):
                    return sector
            previous_text = item["content"].casefold()
            for sector in sorted(set(SECTORS.values()), key=len, reverse=True):
                if re.search(rf"\b{re.escape(sector.casefold())}\b", previous_text):
                    return sector
        return None

    def is_fresh_quote(row):
        timestamp = row.get("quote_updated_at")
        if not isinstance(timestamp, (int, float)):
            return False
        age_seconds = datetime.now(timezone.utc).timestamp() - timestamp
        return 0 <= age_seconds <= 24 * 60 * 60

    def explain_followup():
        previous = next(
            (
                item["content"]
                for item in reversed(history)
                if item["role"] == "assistant"
            ),
            "",
        ).casefold()
        if not previous:
            return response(
                "clarify",
                "I don’t have an earlier answer in this conversation to explain. "
                "What would you like me to clarify?",
            )
        if "comparison" in previous or "comparing" in previous:
            return response(
                "explain_comparison",
                "That comparison describes how the companies’ latest available "
                "prices and daily percentage changes differed. A larger daily "
                "move only means a bigger change over that period; it does not "
                "show a long-term trend or predict what happens next. "
                "This is informational, not investment advice.",
                context={"focus_symbols": prior_symbols()},
            )
        if "sector" in previous and prior_sector():
            return response(
                "explain_sector",
                f"The {prior_sector()} sector groups companies in that area of "
                "the market. The sector filter shows the companies FinPulse "
                "tracks in that category; it does not rank them or predict "
                "their performance.",
                context={"focus_sector": prior_sector()},
            )
        if "mover" in previous or "gainer" in previous or "decliner" in previous:
            return response(
                "explain_movers",
                "A top mover is a company whose quoted price changed more than "
                "others in the available data for the day. The percentage is a "
                "one-day snapshot, not a forecast or a longer-term trend.",
                context={"focus_symbols": prior_symbols()},
            )
        return response(
            "clarify",
            "I can explain that. Which part of my previous answer would you "
            "like me to clarify?",
            context={"focus_symbols": prior_symbols()},
        )

    if not text:
        return response("unknown", "Please say or type a command.")

    if any(phrase in text for phrase in (
        "what does that mean", "what does it mean", "what do you mean",
        "explain that", "explain it", "what does this mean",
    )):
        return explain_followup()

    if any(phrase in text for phrase in (
        "recent trend", "price trend", "trend for", "how has it been doing",
        "how has it performed",
    )):
        symbols = _company_symbols(text)
        if not symbols:
            symbols = prior_symbols()[:1]
        if not symbols:
            return response(
                "clarify",
                "Which company’s trend are you asking about?",
            )
        return response(
            "missing_historical_data",
            f"I don’t have historical price data loaded for {symbols[0]}, so "
            "I can’t describe its recent trend without guessing. I can use "
            "the latest available quote or compare it with another tracked company.",
            context={"focus_symbols": symbols[:1]},
        )

    if any(phrase in text for phrase in (
        "help", "what can you do", "your commands", "show commands",
        "what can i ask",
    )):
        return response(
            "help",
            "I can navigate every FinPulse section, refresh dashboard and "
            "news data, filter market sectors, compare companies, search "
            "careers, and download reports. Try “open news for Apple” or "
            "“find data analyst jobs in Mumbai.”",
        )

    if text in {"stop", "stop assistant", "cancel", "cancel command", "never mind"}:
        return response("cancel", "Okay, I cancelled that command.")

    if any(term in text for term in ("generate report", "download report", "export", "report", "pdf", "csv", "xlsx", "excel")):
        report_format = "pdf"
        if "csv" in text:
            report_format = "csv"
        elif "xlsx" in text or "excel" in text:
            report_format = "xlsx"
        return response(
            "report",
            f"Starting your {report_format.upper()} report download.",
            "report",
            format=report_format,
        )

    if any(term in text for term in ("compare", "comparison", "versus", " vs ")):
        symbols = _company_symbols(text)[:2]
        if len(symbols) == 1 and re.search(r"\b(it|that|them|those)\b", text):
            previous_symbols = [
                symbol for symbol in prior_symbols()
                if symbol not in symbols
            ]
            if previous_symbols:
                symbols.append(previous_symbols[0])
        if len(symbols) == 2:
            rows = {
                row.get("symbol", "").upper(): row
                for row in (market_data or [])
                if isinstance(row, dict)
            }
            first = rows.get(symbols[0])
            second = rows.get(symbols[1])
            if first and second:
                stale_rows = [
                    row for row in (first, second)
                    if row.get("price_source") == "Finnhub"
                    and not is_fresh_quote(row)
                ]
                if stale_rows:
                    stale_symbols = ", ".join(
                        row.get("symbol", "A quote") for row in stale_rows
                    )
                    message = (
                        f"I can’t give a current comparison because the "
                        f"Finnhub quote for {stale_symbols} is missing a recent "
                        "timestamp or is more than 24 hours old. Please refresh "
                        "the market data and try again."
                    )
                else:
                    def describe(row):
                        company = row.get("company") or row["symbol"]
                        change = float(row.get("change", 0))
                        sign = "+" if change > 0 else ""
                        price = float(row.get("price", 0))
                        return (
                            f"{company} ({row['symbol']}): "
                            f"${price:,.2f}, {sign}{change:.2f}%"
                        )

                    message = (
                        "Latest available quote comparison (daily change): "
                        f"{describe(first)}; {describe(second)}. "
                    )
                    if any(
                        row.get("price_source") != "Finnhub"
                        for row in (first, second)
                    ):
                        message += (
                            "At least one value is illustrative sample data, "
                            "not a live quote."
                        )
                    else:
                        message += "Finnhub quotes may be delayed."
            else:
                message = (
                    f"I couldn’t find current tracked data for both "
                    f"{symbols[0]} and {symbols[1]} to compare them."
                )
        else:
            message = "Name two supported companies, for example “compare Apple and Microsoft.”"
        return response(
            "compare_companies",
            message,
            "compare" if len(symbols) == 2 else None,
            symbols=symbols,
            context={"focus_symbols": symbols} if symbols else None,
        )

    if any(term in text for term in ("top mover", "top movers", "biggest movers", "largest movers")):
        rows = [
            row for row in (market_data or [])
            if isinstance(row, dict)
            and row.get("price_source") == "Finnhub"
            and is_fresh_quote(row)
        ]
        if not rows:
            has_live_data = any(
                isinstance(row, dict) and row.get("price_source") == "Finnhub"
                for row in (market_data or [])
            )
            message = (
                "The latest live quote data is missing a timestamp or is more "
                "than 24 hours old, so I can’t reliably identify today’s top "
                "movers. Refresh market data and try again."
                if has_live_data
                else "Live quotes aren’t available right now, so I can’t "
                "identify today’s top movers without guessing. The dashboard "
                "labels sample values as illustrative."
            )
            return response("market_movers", message)

        gainers = sorted(rows, key=lambda row: float(row.get("change", 0)), reverse=True)[:3]
        decliners = sorted(rows, key=lambda row: float(row.get("change", 0)))[:3]

        def summarize(rows_to_show):
            return ", ".join(
                f"{row.get('company') or row['symbol']} ({row['symbol']}) "
                f"{float(row.get('change', 0)):+.2f}%"
                for row in rows_to_show
            )

        focus_symbols = [row["symbol"] for row in gainers[:1]]
        message = (
            f"Among the {len(rows)} fresh live quotes available—not the full "
            f"market—the strongest movers are {summarize(gainers)}. "
            f"The weakest are {summarize(decliners)}. Quotes may be delayed. "
        )
        if focus_symbols:
            focus_name = gainers[0].get("company") or focus_symbols[0]
            message += (
                f"{focus_name} is among the gainers. Would you like its recent "
                "trend or a comparison with another company?"
            )
        return response(
            "market_movers",
            message,
            context={"focus_symbols": focus_symbols},
        )

    if "refresh" in text or "reload" in text or "update" in text:
        if any(term in text for term in ("news", "headline")):
            symbol = _news_symbol(text)
            return response(
                "refresh_news",
                f"Refreshing {symbol} news.",
                "refresh_news",
                symbol=symbol,
            )
        if any(term in text for term in ("career", "job", "internship")):
            keyword, location = _career_search(text)
            return response(
                "search_careers",
                f"Searching for {keyword} opportunities in {location}.",
                "search_careers",
                keyword=keyword,
                location=location,
            )
        return response(
            "refresh_dashboard",
            "Refreshing the FinPulse dashboard data.",
            "refresh_dashboard",
        )

    if "news" in text or "headline" in text:
        symbol = _news_symbol(text)
        return response(
            "show_news",
            f"Opening {symbol} news.",
            "show_news",
            symbol=symbol,
        )

    if re.fullmatch(
        r"(?:(?:open|show|show me|go to|navigate to)\s+)?"
        r"(?:the\s+)?(?:career|careers|jobs?|internships?)"
        r"(?:\s+(?:page|section))?",
        text,
    ):
        return response(
            "navigate",
            "Opening career intelligence.",
            "navigate",
            page="careers",
        )

    if any(term in text for term in (
        "career", "job", "jobs", "internship", "internships",
        "vacancy", "vacancies", "hiring",
    )):
        keyword, location = _career_search(text)
        return response(
            "search_careers",
            f"Searching for {keyword} opportunities in {location}.",
            "search_careers",
            keyword=keyword,
            location=location,
        )

    if (
        prior_sector()
        and any(term in text for term in ("company", "companies", "stocks"))
        and re.search(r"\b(it|there|that|those)\b", text)
    ):
        sector = prior_sector()
        companies = [
            row for row in (market_data or [])
            if isinstance(row, dict) and row.get("sector") == sector
        ]
        if not companies:
            return response(
                "missing_sector_data",
                f"I can’t retrieve the tracked company list for {sector} right "
                "now. Please try again in a moment.",
                context={"focus_sector": sector},
            )
        examples = ", ".join(
            f"{row.get('company') or row['symbol']} ({row['symbol']})"
            for row in companies[:5]
        )
        return response(
            "sector_companies",
            f"FinPulse tracks companies in {sector}, including {examples}. "
            "That is a list of tracked companies, not a performance ranking.",
            "market",
            sector=sector,
            context={"focus_sector": sector},
        )

    if "heatmap" in text or "heat map" in text:
        return response(
            "navigate",
            "Opening the market heatmap.",
            "navigate",
            page="heatmap",
        )

    if any(phrase in text for phrase in (
        "supply demand",
        "supply and demand",
        "supply & demand",
        "demand zone",
        "supply zone",
        "correlation",
    )):
        symbols = _company_symbols(text)
        return response(
            "supply_demand",
            "Loading supply and demand zones.",
            "supply_demand",
            symbols=symbols[:8],
        )

    for sector_name in sorted(SECTORS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(sector_name)}\b", text) and (
            "sector" in text
            or "filter" in text
            or "show" in text
            or text.strip() == sector_name
        ):
            sector = SECTORS[sector_name]
            return response(
                "filter_sector",
                f"Showing {sector} companies in the market explorer.",
                "market",
                sector=sector,
                context={"focus_sector": sector},
            )

    if any(term in text for term in ("market", "stock", "share price", "nifty", "sensex")):
        symbols = _company_symbols(text)
        symbol = symbols[0] if symbols else None
        message = f"Opening the market explorer for {symbol}." if symbol else "Opening the market explorer."
        return response(
            "open_market",
            message,
            "market",
            symbol=symbol,
        )

    if "best performer" in text or "top performer" in text:
        return response(
            "show_performance",
            "The best performer is shown on your dashboard.",
            "navigate",
            page="overview",
        )
    if "worst performer" in text:
        return response(
            "show_performance",
            "The lowest performer is shown on your dashboard.",
            "navigate",
            page="overview",
        )

    if "volatility" in text:
        return response(
            "explain",
            "Volatility describes how much a price varies over time. Higher "
            "volatility means larger price fluctuations; it does not by "
            "itself predict the direction of a price.",
        )

    for page, aliases in PAGE_ALIASES.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", text) for alias in aliases):
            return response(
                "navigate",
                f"Opening {page.replace('_', ' ')}.",
                "navigate",
                page=page,
            )

    return response(
        "unknown",
        "I couldn't match that request. Ask me to open a FinPulse section, "
        "refresh data, filter a sector, search jobs or news, compare "
        "companies, or download a report.",
    )


def _news_symbol(text: str) -> str:
    if "forex" in text or "currency" in text:
        return "FOREX"
    if any(term in text for term in ("indian market", "india news", "nifty", "sensex")):
        return "INDIA"
    symbols = _company_symbols(text)
    return symbols[0] if symbols else "GENERAL"


def _career_search(text: str) -> tuple:
    location = "Bengaluru"
    for candidate in CAREER_LOCATIONS:
        if re.search(rf"\b(?:in|near|around)\s+{re.escape(candidate)}\b", text):
            location = candidate.title()
            break
    if location == "Bangalore":
        location = "Bengaluru"
    elif location == "Gurgaon":
        location = "Gurugram"

    keyword = "analyst"
    keyword_rules = (
        (("data science",), "data science"),
        (("data analyst",), "data analyst"),
        (("business analyst",), "business analyst"),
        (("risk analyst",), "risk analyst"),
        (("software engineer", "software developer", "developer"), "software developer"),
        (("product manager",), "product manager"),
        (("marketing",), "marketing"),
        (("finance", "financial"), "financial analyst"),
    )
    for terms, value in keyword_rules:
        if any(term in text for term in terms):
            keyword = value
            break
    else:
        if "intern" in text:
            keyword = "internship"

    return keyword, location
