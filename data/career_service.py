"""Adzuna job search integration with a demo fallback when keys are absent."""
import html
import os
import re
from urllib.parse import urlparse, urlunparse

import requests

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"

# Official employer career-search pages, used where we can identify a company safely.
EMPLOYER_CAREER_LINKS = {
    "apple": "https://jobs.apple.com/en-us/search",
    "amazon": "https://www.amazon.jobs/en/search",
    "google": "https://www.google.com/about/careers/applications/jobs/results",
    "microsoft": "https://jobs.careers.microsoft.com/global/en/search",
    "nvidia": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
    "visa": "https://corporate.visa.com/en/sites/visa-corporate-careers.html",
}


def _https_url(value):
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return urlunparse(parsed._replace(scheme="https"))


def _employer_url(company_name):
    name = (company_name or "").lower()
    for token, url in EMPLOYER_CAREER_LINKS.items():
        if token in name:
            return url
    return ""


def search(keyword="", location="", country=None, page=1, company=""):
    """Return live Adzuna ads; never present fictional roles as current openings."""
    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()
    country_code = (country or os.getenv("ADZUNA_COUNTRY", "in")).strip().lower()
    if len(country_code) != 2 or not country_code.isalpha():
        country_code = "in"
    if not app_id or not app_key:
        return {
            "jobs": [], "live": False, "source": "No live feed connected",
            "count": 0, "page": page, "pages": 1,
        }

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": 20,
        "what": " ".join(part for part in (keyword, company) if part) or "finance analyst",
        "content-type": "application/json",
    }
    if location:
        params["where"] = location
    try:
        response = requests.get(
            f"{ADZUNA_BASE_URL}/{country_code}/search/{page}",
            params=params,
            headers={"Accept": "application/json"},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        jobs = []
        for item in payload.get("results", []):
            company = (item.get("company") or {}).get("display_name") or "Employer not listed"
            loc = (item.get("location") or {}).get("display_name") or "Location not listed"
            jobs.append({
                "title": item.get("title") or "Untitled role",
                "company": company,
                "location": loc,
                "type": item.get("contract_time") or item.get("contract_type") or "Job",
                "skills": [],
                "description": html.unescape(re.sub(r"<[^>]+>", " ", item.get("description") or "")).strip(),
                "url": _https_url(item.get("redirect_url")),
                "company_url": _employer_url(company),
                "created": item.get("created", ""),
                "salary_min": item.get("salary_min"),
                "salary_max": item.get("salary_max"),
                "source": "Adzuna",
            })
        count = int(payload.get("count", len(jobs)))
        return {"jobs": jobs, "live": True, "source": "Adzuna", "count": count, "page": page, "pages": max(1, (count + 19) // 20)}
    except (requests.RequestException, ValueError) as exc:
        # Do not silently label old sample listings as live when the provider fails.
        raise RuntimeError("Live job search is unavailable. Check Adzuna credentials and try again.") from exc
