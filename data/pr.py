from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_cors import CORS
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import hmac
import os
import io
import math
import re
import secrets
import smtplib
import time
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
from threading import Lock
import requests
import pandas as pd
from werkzeug.security import check_password_hash

from .auth_service import (
    complete_pending_phone_change,
    complete_pending_signup,
    create_user,
    create_pending_phone_change,
    create_pending_signup,
    get_user_by_email,
    get_user_by_identifier,
    get_user_by_id,
    get_pending_phone_change,
    get_pending_signup,
    initialize_auth_db,
    is_valid_email,
    is_valid_phone,
    normalize_email,
    normalize_phone,
    update_user_password,
    update_user_profile,
)
from .forex import bp as forex_bp
from .market import bp as market_bp
from .news import bp as news_bp
from .reports import bp as reports_bp
from .assistant_service import interpret_command
from .career_service import search as search_careers
from .email_service import EmailConfigurationError, send_welcome_email
from .momentum_service import fetch_fundamental_metrics, score_momentum
from .supply_demand_service import (
    YAHOO_SYMBOL_ALIASES,
    build_supply_demand_outlook,
    find_supply_demand_zones,
    yahoo_chart_to_candles,
)
from .personal_finance_service import (
    add_alert,
    add_position,
    fetch_yahoo_quote,
    initialize_personal_finance_db,
    list_alerts,
    list_positions,
    mark_alert_fired,
    remove_alert,
    remove_position,
)
from .sms_service import (
    SmsConfigurationError,
    SmsDeliveryError,
    check_phone_verification,
    phone_verification_configured,
    send_phone_verification,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

for env_path in (
    os.path.join(PROJECT_ROOT, ".env"),
    os.path.join(PROJECT_ROOT, "fin.env"),
):
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path, override=False)

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
app = Flask(
    __name__,
    template_folder=FRONTEND_DIR,
    static_folder=FRONTEND_DIR,
    static_url_path="/static",
)
INSTANCE_DIR = os.path.join(PROJECT_ROOT, "instance")
os.makedirs(INSTANCE_DIR, mode=0o700, exist_ok=True)
os.chmod(INSTANCE_DIR, 0o700)


def load_secret_key():
    configured_key = os.getenv("FLASK_SECRET_KEY", "").strip()
    if configured_key:
        return configured_key

    secret_path = os.path.join(INSTANCE_DIR, "flask_secret.key")
    try:
        descriptor = os.open(
            secret_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        os.chmod(secret_path, 0o600)
        with open(secret_path, "r", encoding="utf-8") as secret_file:
            return secret_file.read().strip()

    secret_key = secrets.token_hex(32)
    with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
        secret_file.write(secret_key)
    return secret_key


app.config.update(
    SECRET_KEY=load_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("FLASK_COOKIE_SECURE", "").lower()
    in {"1", "true", "yes"},
)
CORS(app)
app.register_blueprint(forex_bp)
app.register_blueprint(market_bp)
app.register_blueprint(news_bp)
app.register_blueprint(reports_bp)
initialize_auth_db()
initialize_personal_finance_db()


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


def valid_csrf_token():
    submitted_token = request.form.get("csrf_token", "")
    expected_token = session.get("csrf_token", "")
    return bool(
        submitted_token
        and expected_token
        and hmac.compare_digest(submitted_token, expected_token)
    )


@app.before_request
def require_authentication():
    if request.endpoint == "static":
        filename = (request.view_args or {}).get("filename", "")
        if filename.lower().endswith((".html", ".htm")):
            return redirect(url_for("signin"))
        return None

    if request.endpoint in {
        "signin",
        "signup",
        "verify_phone",
        "signout",
    }:
        return None

    user_id = session.get("user_id")
    user = get_user_by_id(user_id) if user_id else None
    if user is None:
        session.pop("user_id", None)
        if request.path.startswith("/api/"):
            return jsonify(error="Please sign in to access this resource."), 401
        return redirect(url_for("signin"))

    g.current_user = user


def finish_authentication(user_id):
    session.clear()
    session["user_id"] = user_id
    session["csrf_token"] = secrets.token_urlsafe(32)
    return redirect(url_for("welcome"))


def welcome_user(user_id, email, phone_verified=True):
    try:
        send_welcome_email(email, url_for("signin", _external=True))
        email_status = (
            "A welcome email was sent to your email address. "
            "If you don't see it, check your spam folder."
        )
        category = "success"
    except (EmailConfigurationError, OSError, smtplib.SMTPException) as error:
        app.logger.warning("Welcome email delivery failed for %s: %s", email, error)
        email_status = (
            "Your account was created, but the welcome email could not be sent. "
            "Check the email settings in the app configuration."
        )
        category = "warning"

    response = finish_authentication(user_id)
    flash(email_status, category)
    if not phone_verified:
        flash(
            "Your phone was saved but is unverified. Email sign-in is ready; "
            "verify your phone from Profile to enable phone sign-in.",
            "info",
        )
    return response


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        if not valid_csrf_token():
            abort(400, description="Your form expired. Please try again.")

        email = normalize_email(request.form.get("email", ""))
        full_name = request.form.get("full_name", "").strip()
        phone = normalize_phone(request.form.get("phone", ""))
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        error = None

        if not full_name or len(full_name) > 80:
            error = "Enter your name using 1–80 characters."
        elif not is_valid_email(email):
            error = "Enter a valid email address."
        elif not is_valid_phone(phone):
            error = "Enter a phone number in international format, such as +14155552671."
        elif len(password) < 8:
            error = "Password must be at least 8 characters long."
        elif len(password) > 128:
            error = "Password must be 128 characters or fewer."
        elif password != confirm_password:
            error = "The passwords do not match."

        if error:
            return render_template("auth/signup.html", error=error), 400

        if phone_verification_configured():
            pending_id = create_pending_signup(email, phone, full_name, password)
            if pending_id is None:
                return render_template(
                    "auth/signup.html",
                    error=(
                        "That email or phone number is already registered. "
                        "Sign in instead."
                    ),
                ), 409
            try:
                send_phone_verification(phone)
            except (SmsConfigurationError, SmsDeliveryError) as error:
                app.logger.warning(
                    "Phone verification could not be started: %s",
                    error,
                )
                return render_template("auth/signup.html", error=str(error)), 503

            session["pending_signup_id"] = pending_id
            return redirect(url_for("verify_phone"))

        user_id = create_user(email, password, full_name, phone)
        if user_id is None:
            return render_template(
                "auth/signup.html",
                error=(
                    "That email or phone number is already registered. "
                    "Sign in instead."
                ),
            ), 409
        app.logger.info(
            "Created account with unverified phone because Twilio is not configured."
        )
        return welcome_user(user_id, email, phone_verified=False)

    return render_template("auth/signup.html")


@app.route("/verify-phone", methods=["GET", "POST"])
def verify_phone():
    pending_id = session.get("pending_signup_id")
    pending = get_pending_signup(pending_id) if pending_id else None
    if pending is None:
        session.pop("pending_signup_id", None)
        flash("Your signup verification expired. Please create your account again.", "warning")
        return redirect(url_for("signup"))

    error = None
    if request.method == "POST":
        if not valid_csrf_token():
            abort(400, description="Your form expired. Please try again.")
        code = request.form.get("code", "").strip()
        if not re.fullmatch(r"\d{4,10}", code):
            error = "Enter the verification code sent to your phone."
        else:
            try:
                approved = check_phone_verification(pending["phone_e164"], code)
            except (SmsConfigurationError, SmsDeliveryError) as verification_error:
                app.logger.warning(
                    "Phone verification check failed: %s",
                    verification_error,
                )
                error = str(verification_error)
            else:
                if not approved:
                    error = "That verification code is incorrect or expired."
                else:
                    user_id = complete_pending_signup(pending["id"])
                    if user_id is None:
                        session.pop("pending_signup_id", None)
                        error = (
                            "That email or phone number was registered while you "
                            "were verifying. Please sign in instead."
                        )
                    else:
                        return welcome_user(
                            user_id,
                            pending["email"],
                            phone_verified=True,
                        )

    return render_template(
        "auth/verify_phone.html",
        phone=pending["phone_e164"],
        error=error,
    ), 400 if error else 200


@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        if not valid_csrf_token():
            abort(400, description="Your form expired. Please try again.")

        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        if not identifier or len(identifier) > 254 or not password or len(password) > 128:
            return render_template(
                "auth/signin.html",
                error="Email/phone or password is incorrect.",
            ), 401

        user = get_user_by_identifier(identifier)
        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template(
                "auth/signin.html",
                error="Email/phone or password is incorrect.",
            ), 401
        return finish_authentication(user["id"])

    return render_template("auth/signin.html")


@app.get("/welcome")
def welcome():
    return render_template("auth/welcome.html", email=g.current_user["email"])


@app.post("/signout")
def signout():
    if not valid_csrf_token():
        abort(400, description="Your form expired. Please try again.")
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("signin"))


@app.post("/api/profile")
def update_profile():
    if not valid_csrf_token():
        return jsonify(error="Your form expired. Refresh the page and try again."), 400
    full_name = request.form.get("full_name", "").strip()
    if not full_name or len(full_name) > 80:
        return jsonify(error="Enter your name using 1–80 characters."), 400
    update_user_profile(g.current_user["id"], full_name)
    return jsonify(message="Your profile name was updated.")


@app.post("/api/profile/phone")
def start_profile_phone_verification():
    if not valid_csrf_token():
        return jsonify(error="Your form expired. Refresh the page and try again."), 400
    phone = normalize_phone(request.form.get("phone", ""))
    if not is_valid_phone(phone):
        return jsonify(
            error="Enter a phone number in international format, such as +14155552671."
        ), 400
    if not create_pending_phone_change(g.current_user["id"], phone):
        return jsonify(error="That phone number is already linked to another account."), 409
    try:
        send_phone_verification(phone)
    except (SmsConfigurationError, SmsDeliveryError) as error:
        app.logger.warning("Phone verification could not be started: %s", error)
        return jsonify(error=str(error)), 503
    return jsonify(message="A verification code was sent to your phone.")


@app.post("/api/profile/phone/verify")
def verify_profile_phone():
    if not valid_csrf_token():
        return jsonify(error="Your form expired. Refresh the page and try again."), 400
    pending = get_pending_phone_change(g.current_user["id"])
    if pending is None:
        return jsonify(error="Your phone verification expired. Request a new code."), 400
    code = request.form.get("code", "").strip()
    if not re.fullmatch(r"\d{4,10}", code):
        return jsonify(error="Enter the verification code sent to your phone."), 400
    try:
        approved = check_phone_verification(pending["phone_e164"], code)
    except (SmsConfigurationError, SmsDeliveryError) as error:
        app.logger.warning("Phone verification check failed: %s", error)
        return jsonify(error=str(error)), 503
    if not approved:
        return jsonify(error="That verification code is incorrect or expired."), 400
    if not complete_pending_phone_change(g.current_user["id"]):
        return jsonify(error="That phone number is already linked to another account."), 409
    return jsonify(
        message="Your backup phone number is verified and saved.",
        phone=pending["phone_e164"],
    )


@app.post("/api/profile/password")
def change_profile_password():
    if not valid_csrf_token():
        return jsonify(error="Your form expired. Refresh the page and try again."), 400
    user = get_user_by_email(g.current_user["email"])
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    if user is None or not check_password_hash(
        user["password_hash"],
        current_password,
    ):
        return jsonify(error="Your current password is incorrect."), 400
    if len(new_password) < 8 or len(new_password) > 128:
        return jsonify(error="New password must be 8–128 characters long."), 400
    if new_password != confirm_password:
        return jsonify(error="The new passwords do not match."), 400
    update_user_password(g.current_user["id"], new_password)
    return jsonify(message="Your password was changed.")

# --------------------------------------------------
# MARKET DATA
# Expand the catalog to 300+ companies and allow a live quote refresh for
# commonly traded symbols when an external market feed is reachable.
# --------------------------------------------------

SECTOR_ORDER = [
    "Technology", "Banking", "Energy", "Healthcare", "Automotive",
    "Consumer", "Industrials", "Utilities", "Telecom", "Real Estate",
    "Materials", "Semiconductors"
]

SECTOR_SYMBOLS = {
    "Technology": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "CRM", "ORCL",
        "AMD", "INTC", "QCOM", "CSCO", "ADBE", "SAP", "IBM", "SHOP", "PLTR",
        "SNOW", "NOW", "PINS", "UBER", "MCHP", "TXN", "KLAC", "ADI", "MU",
        "TEAM", "DBX", "WDAY", "DOCU", "TWTR", "PYPL", "NET", "DDOG", "FSLR",
        "MRVL", "NXPI", "TTD", "ZS", "CDNS", "OKTA", "CFLT", "ZM"
    ],
    "Banking": [
        "JPM", "BAC", "GS", "C", "MS", "WFC", "USB", "PNC", "AXP", "COF",
        "SCHW", "BLK", "CME", "TFC", "NTRS", "RF", "STT", "MCO", "SPGI",
        "ICE", "BK", "MMC", "FITB", "KEY", "HBAN", "ALLY", "CFG", "SYF",
        "CMA", "BMO", "TD", "RBC", "HDB", "UBS", "DB"
    ],
    "Energy": [
        "XOM", "CVX", "COP", "SLB", "EOG", "HAL", "OXY", "MPC", "DVN", "EQT",
        "PXD", "WMB", "CHK", "NEM", "GLC", "HES", "MRO", "APA", "CXO", "RIG",
        "NOV", "BKR", "PTEN", "SM", "KMI", "FANG", "CNQ", "CTRA", "PBR", "SHEL",
        "BP", "TOT", "VLO", "WTI", "CPE"
    ],
    "Healthcare": [
        "LLY", "UNH", "JNJ", "PFE", "ABT", "TMO", "DHR", "MRK", "CVS", "CI",
        "MDT", "ISRG", "BSX", "AZN", "GILD", "REGN", "VRTX", "DXCM", "IDXX",
        "ALGN", "BMY", "ABBV", "ELV", "BIIB", "SNY", "AMGN", "HCA", "LH", "IQV",
        "QGEN", "ILMN", "BAX", "A", "RMD", "NVO"
    ],
    "Automotive": [
        "TSLA", "F", "GM", "STLA", "HMC", "TM", "FORD", "RACE", "NKE", "LKQ",
        "AAL", "PAA", "DOW", "MGA", "LEA", "AAP", "TTM", "RIVN", "KMX",
        "GME", "MRCY", "BWA", "ALV", "LCID", "NIO", "XPEV", "LI", "BIDU"
    ],
    "Consumer": [
        "COST", "PEP", "WMT", "PG", "KO", "PM", "NKE", "HD", "MCD", "SBUX",
        "TGT", "LOW", "CVS", "KHC", "KMB", "CL", "EL", "CAG", "GIS", "MNST",
        "K", "HSY", "ADM", "CPB", "MELI", "AMZN", "BABA", "PDD", "LULU", "TJX",
        "RL", "TTWO", "BUD"
    ],
    "Industrials": [
        "CAT", "GE", "HON", "UPS", "RTX", "BA", "DE", "EMR", "ITW", "NOC",
        "LMT", "MMM", "UNP", "CSX", "FDX", "DAL", "CARR", "CP", "JCI", "PWR",
        "AME", "ODFL", "PCAR", "RSG", "WM", "CMI", "VRSK", "LUV", "NSC", "JBL",
        "FLS", "AOS", "GWW", "ROK", "NDSN", "APTV"
    ],
    "Utilities": [
        "NEE", "DUK", "SO", "AEP", "EXC", "NGG", "D", "ED", "PPL", "EIX",
        "SRE", "AES", "CMS", "FE", "EVRG", "NWE", "CNP", "ETR", "XEL", "LNT",
        "PNW", "WEC", "NRG", "OGE", "AVA", "EGP", "GXP"
    ],
    "Telecom": [
        "T", "VZ", "TMUS", "CMCSA", "CHTR", "DIS", "NFLX", "EA", "ATVI",
        "PARA", "ROKU", "SONY", "SPOT", "NTES", "BAND", "SID", "VOD"
    ],
    "Real Estate": [
        "PLD", "AMT", "CPT", "DLR", "EQIX", "PSA", "O", "WELL", "SPG", "UDR",
        "REG", "AVB", "EQR", "MAA", "BXP", "VTR", "EXR", "INVH", "ESS", "KIM",
        "SLG", "ARE", "HST", "GLPI", "PEAK", "LXP", "CUBE", "ARCP"
    ],
    "Materials": [
        "LIN", "APD", "FCX", "NEM", "AA", "NUE", "CSTM", "PPG", "ECL", "SHW",
        "MOS", "DOW", "BHP", "RIO", "VALE", "NTR", "MLM", "CF", "ALB", "ATI",
        "TRN", "MT", "SCCO", "LTHM", "OMC"
    ],
    "Semiconductors": [
        "NVDA", "AMD", "INTC", "QCOM", "AVGO", "MU", "MCHP", "TXN", "ADI", "KLAC",
        "NXPI", "MRVL", "ON", "LRCX", "SMCI", "CREE", "BRKS", "MPWR", "SWKS",
        "SNPS", "TER", "ASML", "ARM", "STM", "NXP"
    ]
}

COMPANY_OVERRIDES = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft", "NVDA": "NVIDIA",
    "AMZN": "Amazon", "GOOGL": "Alphabet Inc.", "META": "Meta Platforms",
    "AVGO": "Broadcom", "CRM": "Salesforce", "ORCL": "Oracle",
    "AMD": "Advanced Micro Devices", "INTC": "Intel", "QCOM": "Qualcomm",
    "CSCO": "Cisco", "ADBE": "Adobe", "SAP": "SAP SE", "IBM": "IBM",
    "SHOP": "Shopify", "PLTR": "Palantir", "SNOW": "Snowflake",
    "NOW": "ServiceNow", "PINS": "Pinterest", "UBER": "Uber",
    "MCHP": "Microchip", "TXN": "Texas Instruments", "KLAC": "KLA",
    "ADI": "Analog Devices", "MU": "Micron", "TEAM": "Atlassian",
    "DBX": "Dropbox", "WDAY": "Workday", "DOCU": "DocuSign",
    "TWTR": "Twitter", "PYPL": "PayPal", "NET": "Cloudflare",
    "DDOG": "Datadog", "FSLR": "First Solar", "MRVL": "Marvell",
    "NXPI": "NXP Semiconductors", "TTD": "The Trade Desk", "ZS": "Zscaler",
    "CDNS": "Cadence", "OKTA": "Okta", "CFLT": "Confluent", "ZM": "Zoom",
    "JPM": "JPMorgan Chase", "BAC": "Bank of America", "GS": "Goldman Sachs",
    "C": "Citigroup", "MS": "Morgan Stanley", "WFC": "Wells Fargo",
    "USB": "U.S. Bancorp", "PNC": "PNC Financial", "AXP": "American Express",
    "COF": "Capital One", "SCHW": "Charles Schwab", "BLK": "BlackRock",
    "CME": "CME Group", "TFC": "Truist", "NTRS": "Northern Trust",
    "RF": "Regions Financial", "STT": "State Street", "MCO": "Moody's",
    "SPGI": "S&P Global", "ICE": "Intercontinental Exchange", "BK": "Bank of New York Mellon",
    "MMC": "Marsh & McLennan", "FITB": "Fifth Third Bank", "KEY": "KeyCorp",
    "HBAN": "Huntington Bancshares", "ALLY": "Ally Financial", "CFG": "Citizens Financial",
    "SYF": "Synchrony Financial", "CMA": "Comerica", "BMO": "Bank of Montreal",
    "TD": "Toronto-Dominion Bank", "RBC": "Royal Bank of Canada", "HDB": "HSBC",
    "UBS": "UBS Group", "DB": "Deutsche Bank", "XOM": "ExxonMobil",
    "CVX": "Chevron", "COP": "ConocoPhillips", "SLB": "Schlumberger",
    "EOG": "EOG Resources", "HAL": "Halliburton", "OXY": "Occidental",
    "MPC": "Marathon Petroleum", "DVN": "Devon Energy", "EQT": "EQT",
    "PXD": "Pioneer Natural Resources", "WMB": "Williams Companies",
    "CHK": "Chesapeake Energy", "NEM": "Newmont", "GLC": "GlenCore",
    "HES": "Hess", "MRO": "Marathon Oil", "APA": "APA Corporation",
    "CXO": "Concho Resources", "RIG": "Transocean", "NOV": "NOV Inc.",
    "BKR": "Baker Hughes", "PTEN": "Patterson-UTI", "SM": "SM Energy",
    "KMI": "Kinder Morgan", "FANG": "Diamondback Energy", "CNQ": "Canadian Natural",
    "CTRA": "Coterra Energy", "PBR": "Petrobras", "SHEL": "Shell",
    "BP": "BP PLC", "TOT": "TotalEnergies", "VLO": "Valero",
    "WTI": "W&T Offshore", "CPE": "Callon Petroleum", "LLY": "Eli Lilly",
    "UNH": "UnitedHealth", "JNJ": "Johnson & Johnson", "PFE": "Pfizer",
    "ABT": "Abbott", "TMO": "Thermo Fisher", "DHR": "Danaher",
    "MRK": "Merck", "CVS": "CVS Health", "CI": "Cigna",
    "MDT": "Medtronic", "ISRG": "Intuitive Surgical", "BSX": "Boston Scientific",
    "AZN": "AstraZeneca", "GILD": "Gilead", "REGN": "Regeneron",
    "VRTX": "Vertex Pharmaceuticals", "DXCM": "DexCom", "IDXX": "IDEXX",
    "ALGN": "Align Technology", "BMY": "Bristol Myers", "ABBV": "AbbVie",
    "ELV": "Elevance Health", "BIIB": "Biogen", "SNY": "Sanofi",
    "AMGN": "Amgen", "HCA": "HCA Healthcare", "LH": "LabCorp",
    "IQV": "IQVIA", "QGEN": "Qiagen", "ILMN": "Illumina",
    "BAX": "Baxter", "A": "Agilent", "RMD": "ResMed", "NVO": "Novo Nordisk",
    "TSLA": "Tesla", "F": "Ford", "GM": "General Motors",
    "STLA": "Stellantis", "HMC": "Honda", "TM": "Toyota",
    "FORD": "Ford Motor", "RACE": "Ferrari", "NKE": "Nike",
    "LKQ": "LKQ", "AAL": "American Airlines", "PAA": "PAA",
    "DOW": "Dow", "MGA": "Magna", "LEA": "Lear", "AAP": "Advance Auto Parts",
    "TTM": "Tata Motors", "RIVN": "Rivian", "KMX": "CarMax",
    "GME": "GameStop", "MRCY": "Mercury Systems", "BWA": "BorgWarner",
    "ALV": "Autoliv", "LCID": "Lucid", "NIO": "NIO", "XPEV": "XPeng",
    "LI": "Li Auto", "BIDU": "Baidu", "COST": "Costco",
    "PEP": "PepsiCo", "WMT": "Walmart", "PG": "Procter & Gamble",
    "KO": "Coca-Cola", "PM": "Philip Morris", "HD": "Home Depot",
    "MCD": "McDonald's", "SBUX": "Starbucks", "TGT": "Target",
    "LOW": "Lowe's", "CVS": "CVS Health", "KHC": "Kraft Heinz",
    "KMB": "Kimberly-Clark", "CL": "Colgate", "EL": "Estee Lauder",
    "CAG": "Conagra", "GIS": "General Mills", "MNST": "Monster Beverage",
    "K": "Kellogg's", "HSY": "Hershey's", "ADM": "Archer Daniels Midland",
    "CPB": "Campbell Soup", "MELI": "MercadoLibre", "BABA": "Alibaba",
    "PDD": "Pinduoduo", "LULU": "Lululemon", "TJX": "TJX Companies",
    "RL": "Ralph Lauren", "TTWO": "Take-Two", "BUD": "Anheuser-Busch",
    "CAT": "Caterpillar", "GE": "General Electric", "HON": "Honeywell",
    "UPS": "United Parcel Service", "RTX": "RTX", "BA": "Boeing",
    "DE": "Deere", "EMR": "Emerson", "ITW": "Illinois Tool Works",
    "NOC": "Northrop Grumman", "LMT": "Lockheed Martin", "MMM": "3M",
    "UNP": "Union Pacific", "CSX": "CSX", "FDX": "FedEx",
    "DAL": "Delta Air Lines", "CARR": "Carrier Global", "CP": "Canadian Pacific",
    "JCI": "Johnson Controls", "PWR": "Quanta Services", "AME": "Ametek",
    "ODFL": "Old Dominion", "PCAR": "Paccar", "RSG": "Republic Services",
    "WM": "Waste Management", "CMI": "Cummins", "VRSK": "Verisk",
    "LUV": "Southwest Airlines", "NSC": "Norfolk Southern", "JBL": "Jabil",
    "FLS": "Flowserve", "AOS": "A.O. Smith", "GWW": "WW Grainger",
    "ROK": "Rockwell Automation", "NDSN": "Nordson", "APTV": "Aptiv",
    "NEE": "NextEra Energy", "DUK": "Duke Energy", "SO": "Southern Company",
    "AEP": "American Electric Power", "EXC": "Exelon", "NGG": "National Grid",
    "D": "Dominion Energy", "ED": "Consolidated Edison", "PPL": "PPL",
    "EIX": "Edison International", "SRE": "Sempra", "AES": "AES Corp",
    "CMS": "CMS Energy", "FE": "FirstEnergy", "EVRG": "Evergy",
    "NWE": "NorthWestern Energy", "CNP": "CenterPoint Energy", "ETR": "Entergy",
    "XEL": "Xcel Energy", "LNT": "Alliant Energy", "PNW": "Pinnacle West",
    "WEC": "WEC Energy", "NRG": "NRG Energy", "OGE": "OGE Energy",
    "AVA": "Avista", "EGP": "EastGroup", "GXP": "Great Plains Energy",
    "T": "AT&T", "VZ": "Verizon", "TMUS": "T-Mobile", "CMCSA": "Comcast",
    "CHTR": "Charter Communications", "DIS": "Disney", "NFLX": "Netflix",
    "EA": "Electronic Arts", "ATVI": "Activision Blizzard",
    "PARA": "Paramount", "ROKU": "Roku", "SONY": "Sony",
    "SPOT": "Spotify", "NTES": "NetEase", "BAND": "Bandwidth",
    "VOD": "Vodafone", "PLD": "Prologis", "AMT": "American Tower",
    "CPT": "Camden Property Trust", "DLR": "Digital Realty", "EQIX": "Equinix",
    "PSA": "Public Storage", "O": "Realty Income", "WELL": "Welltower",
    "SPG": "Simon Property Group", "UDR": "UDR Inc.", "REG": "Regency Centers",
    "AVB": "AvalonBay", "EQR": "Equity Residential", "MAA": "Mid-America Apartment",
    "BXP": "Boston Properties", "VTR": "Ventas", "EXR": "Extra Space Storage",
    "INVH": "Invitation Homes", "ESS": "Essex Property Trust", "KIM": "Kimco Realty",
    "SLG": "SL Green", "ARE": "Alexandria Real Estate", "HST": "Host Hotels",
    "GLPI": "Gaming and Leisure", "PEAK": "Healthpeak", "LXP": "Lexington Realty",
    "CUBE": "CubeSmart", "ARCP": "Arcapita", "LIN": "Linde",
    "APD": "Air Products", "FCX": "Freeport-McMoRan", "NEM": "Newmont",
    "AA": "Alcoa", "NUE": "Nucor", "CSTM": "Constellium", "PPG": "PPG Industries",
    "ECL": "Ecolab", "SHW": "Sherwin-Williams", "MOS": "Mosaic",
    "DOW": "Dow Inc.", "BHP": "BHP", "RIO": "Rio Tinto",
    "VALE": "Vale", "NTR": "Nutrien", "MLM": "Martin Marietta",
    "CF": "CF Industries", "ALB": "Albemarle", "ATI": "ATI Inc.",
    "TRN": "Trinseo", "MT": "ArcelorMittal", "SCCO": "Southern Copper",
    "LTHM": "Livent", "OMC": "Omnicom"
}


def build_market_data():
    records = []
    for sector in SECTOR_ORDER:
        for idx, symbol in enumerate(SECTOR_SYMBOLS.get(sector, []), start=1):
            company = COMPANY_OVERRIDES.get(symbol, f"{sector} Group {idx}")
            price = 35 + idx * 3.5 + (len(symbol) * 1.1) + (len(sector) * 0.8)
            change = round(((idx % 11) - 5) * 0.75 + (0.5 if idx % 4 == 0 else -0.15), 2)
            records.append({
                "symbol": symbol,
                "company": company,
                "sector": sector,
                "price": round(price, 2),
                "change": change,
            })

    generated_count = len(records)
    while generated_count < 350:
        sector = SECTOR_ORDER[generated_count % len(SECTOR_ORDER)]
        symbol = f"{sector[:3].upper()}{generated_count:03d}"
        records.append({
            "symbol": symbol,
            "company": f"{sector} Holdings {generated_count + 1}",
            "sector": sector,
            "price": round(42 + generated_count * 1.05, 2),
            "change": round(((generated_count % 13) - 6) * 0.7, 2),
        })
        generated_count += 1

    unique_records = {}
    for record in records:
        unique_records.setdefault(record["symbol"], record)
    return list(unique_records.values())


MARKET_DATA = build_market_data()

QUOTE_CACHE = {}
QUOTE_CACHE_LOCK = Lock()
QUOTE_CACHE_TTL = 60
QUOTE_FAILURE_CACHE_TTL = 20
FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"


def fetch_live_quote(symbol):
    cache_key = symbol.upper()
    now = time.monotonic()
    with QUOTE_CACHE_LOCK:
        cached = QUOTE_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return dict(cached[1]) if cached[1] else None

    token = os.getenv("FINNHUB_API_KEY", "").strip()
    quote = None
    if token:
        try:
            response = requests.get(
                FINNHUB_QUOTE_URL,
                params={"symbol": cache_key, "token": token},
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            price = float(payload.get("c") or 0)
            previous_close = float(payload.get("pc") or 0)
            if price > 0 and previous_close > 0:
                change = payload.get("dp")
                if change is None:
                    change = ((price / previous_close) - 1) * 100
                quote = {
                    "symbol": cache_key,
                    "price": round(price, 2),
                    "change": round(float(change), 2),
                    "updated_at": payload.get("t"),
                }
        except (requests.RequestException, ValueError, TypeError) as error:
            app.logger.warning("Finnhub quote lookup failed for %s: %s", cache_key, error)

    ttl = QUOTE_CACHE_TTL if quote else QUOTE_FAILURE_CACHE_TTL
    with QUOTE_CACHE_LOCK:
        QUOTE_CACHE[cache_key] = (time.monotonic() + ttl, quote)

    return dict(quote) if quote else None


def enrich_live_market(data, max_live_symbols=None):
    symbols = [item["symbol"] for item in data if item.get("symbol")]
    if max_live_symbols is not None:
        symbols = symbols[:max_live_symbols]

    live_map = {}
    symbols = [symbol for symbol in symbols if symbol.isalpha() and len(symbol) <= 5]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(fetch_live_quote, symbol): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            quote = future.result()
            if quote:
                live_map[quote["symbol"]] = quote

    updated = []
    for item in data:
        record = dict(item)
        quote = live_map.get(record["symbol"].upper())
        if quote:
            record["price"] = quote["price"]
            record["change"] = quote["change"]
            record["price_source"] = "Finnhub"
            record["quote_updated_at"] = quote["updated_at"]
        else:
            record["price_source"] = "Illustrative data"
            record["quote_updated_at"] = None
        updated.append(record)
    return updated

CAREERS = [
    {
        "title": "Finance Analyst Intern",
        "company": "Example Financial Services",
        "location": "Bengaluru",
        "skills": ["Excel", "Financial Modeling", "Communication"]
    },
    {
        "title": "Data Analyst Intern",
        "company": "Example Analytics",
        "location": "Bengaluru",
        "skills": ["Python", "SQL", "Power BI"]
    },
    {
        "title": "Market Research Intern",
        "company": "Example Research Group",
        "location": "Remote",
        "skills": ["Research", "Excel", "Statistics"]
    },
    {
        "title": "Business Intelligence Intern",
        "company": "Example Technology",
        "location": "Bengaluru",
        "skills": ["SQL", "Power BI", "Data Visualization"]
    },
]


# --------------------------------------------------
# PAGE
# --------------------------------------------------

@app.route("/")
def home():
    return render_template(
        "index.html",
        email=g.current_user["email"],
        user=g.current_user,
    )


# --------------------------------------------------
# MARKET DATA
# --------------------------------------------------

@app.route("/api/market")
def market():
    sector = request.args.get("sector", "All").strip().lower()
    limit = request.args.get("limit", default=0, type=int)

    data = enrich_live_market(MARKET_DATA, max_live_symbols=8)
    live_quote_count = sum(item["price_source"] == "Finnhub" for item in data)
    token = os.getenv("FINNHUB_API_KEY", "").strip()
    live_rows = [
        item for item in data
        if token and item["price_source"] == "Finnhub"
    ]
    with ThreadPoolExecutor(max_workers=4) as executor:
        metric_futures = {
            executor.submit(
                fetch_fundamental_metrics,
                item["symbol"],
                token,
            ): item
            for item in live_rows
        }
        for future in as_completed(metric_futures):
            item = metric_futures[future]
            metrics = future.result()
            score = score_momentum(item["change"], metrics)
            item["momentum"] = score
            if score:
                score["factors"] = metrics

    for item in data:
        item.setdefault("momentum", None)

    if sector != "all":
        data = [
            item for item in data
            if item["sector"].lower() == sector
        ]

    if limit and limit > 0:
        data = data[:limit]

    return jsonify({
        "demo": live_quote_count == 0,
        "data_mode": "live_partial" if live_quote_count else "illustrative_demo",
        "live_quote_count": live_quote_count,
        "momentum_scored_count": sum(
            item["momentum"] is not None for item in data
        ),
        "message": (
            f"{live_quote_count} live Finnhub quotes are available; rows marked "
            "Illustrative data are sample values."
            if live_quote_count
            else "Live quotes are unavailable; prices are illustrative sample data."
        ),
        "data": data
    })


@app.route("/api/sectors")
def sectors():
    names = sorted({item["sector"] for item in MARKET_DATA})

    return jsonify(names)


@app.route("/api/compare")
def compare():
    symbols = request.args.get("symbols", "")

    requested = {
        symbol.strip().upper()
        for symbol in symbols.split(",")
        if symbol.strip()
    }

    if not requested:
        return jsonify({"demo": True, "data": []})

    filtered = [
        item for item in MARKET_DATA
        if item["symbol"] in requested
    ]
    results = [
        item for item in enrich_live_market(filtered)
        if item["symbol"] in requested
    ]

    return jsonify({
        "demo": True,
        "data": results
    })


# --------------------------------------------------
# ANALYTICS
# --------------------------------------------------

@app.route("/api/analytics")
def analytics():
    df = pd.DataFrame(MARKET_DATA)

    best = df.loc[df["change"].idxmax()].to_dict()
    worst = df.loc[df["change"].idxmin()].to_dict()

    sector_average = (
        df.groupby("sector")["change"]
        .mean()
        .round(2)
        .to_dict()
    )

    return jsonify({
        "demo": True,
        "message": "Illustrative sample analytics, not live market performance.",
        "best_performer": best,
        "worst_performer": worst,
        "sector_average_change": sector_average,
        "average_change": round(float(df["change"].mean()), 2)
    })


@app.route("/api/supply-demand")
def supply_demand():
    symbol = request.args.get("symbol", "AAPL").strip().upper()
    timeframe = request.args.get("timeframe", "5m").strip().lower()
    yahoo_timeframes = {
        "5m": ("5m", "5d"),
        "15m": ("15m", "60d"),
        "1h": ("60m", "60d"),
        "1d": ("1d", "1y"),
    }
    if timeframe not in yahoo_timeframes:
        return jsonify(error="Unsupported timeframe. Choose 5m, 15m, 1h, or 1d."), 400

    available_symbols = {item["symbol"] for item in MARKET_DATA}
    available_symbols.update(YAHOO_SYMBOL_ALIASES)
    if symbol not in available_symbols:
        return jsonify(error=f"Unknown company symbol: {symbol}."), 400

    yahoo_symbol = YAHOO_SYMBOL_ALIASES.get(symbol, symbol)
    def analyze_candles(selected_timeframe):
        selected_interval, selected_range = yahoo_timeframes[selected_timeframe]
        candle_response = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}",
            params={
                "range": selected_range,
                "interval": selected_interval,
                "events": "history",
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=12,
        )
        candle_response.raise_for_status()
        return find_supply_demand_zones(
            yahoo_chart_to_candles(candle_response.json())
        )

    try:
        analysis = analyze_candles(timeframe)
        multi_timeframe = {}
        multi_timeframe_errors = {}
        if timeframe == "5m" and request.args.get("compare", "0") != "0":
            compare_timeframes = ("15m", "1h")
            with ThreadPoolExecutor(max_workers=2) as executor:
                comparison_futures = {
                    interval: executor.submit(analyze_candles, interval)
                    for interval in compare_timeframes
                }
                for compare_timeframe, future in comparison_futures.items():
                    try:
                        comparison = future.result()
                    except (requests.RequestException, ValueError, TypeError) as error:
                        app.logger.warning(
                            "Higher-timeframe zone lookup failed for %s at %s: %s",
                            yahoo_symbol,
                            compare_timeframe,
                            error,
                        )
                        multi_timeframe_errors[compare_timeframe] = (
                            f"{compare_timeframe} comparison data is unavailable."
                        )
                        continue
                    try:
                        multi_timeframe[compare_timeframe] = {
                            zone_type: [
                                any(
                                    min(base_zone["high"], compare_zone["high"])
                                    >= max(base_zone["low"], compare_zone["low"])
                                    for compare_zone in comparison["zones"][zone_type]
                                )
                                for base_zone in analysis["zones"][zone_type]
                            ]
                            for zone_type in ("demand", "supply")
                        }
                    except (KeyError, TypeError) as error:
                        app.logger.warning(
                            "Could not compare %s supply and demand zones for %s: %s",
                            compare_timeframe,
                            yahoo_symbol,
                            error,
                        )
                        multi_timeframe_errors[compare_timeframe] = (
                            f"{compare_timeframe} comparison data was incomplete."
                        )
    except requests.HTTPError as error:
        status_code = (
            error.response.status_code
            if error.response is not None
            else None
        )
        if status_code in (401, 403):
            message = (
                "Yahoo Finance denied access to the requested candle data. Please try "
                "again later or check whether the provider is available "
                "from your network."
            )
        elif status_code == 429:
            message = (
                "Yahoo Finance rate limit reached. Wait briefly, then select Find "
                "zones to retry."
            )
        else:
            message = (
                "Yahoo Finance could not provide historical candles for "
                "this symbol."
            )
        app.logger.warning(
            "Supply and demand history request failed for %s with HTTP %s",
            yahoo_symbol,
            status_code or "unknown",
        )
        return jsonify(error=message), 503
    except (requests.RequestException, ValueError, TypeError) as error:
        app.logger.warning(
            "Supply and demand history lookup failed for %s: %s",
            yahoo_symbol,
            error,
        )
        return jsonify(
            error=(
                "Yahoo Finance historical candles could not be analyzed for "
                "this symbol. Please try again later."
            )
        ), 502

    return jsonify({
        "symbol": symbol,
        "provider_symbol": yahoo_symbol,
        "timeframe": timeframe,
        "outlook": build_supply_demand_outlook(
            analysis["current_price"],
            analysis["zones"],
        ),
        "multi_timeframe": multi_timeframe,
        "multi_timeframe_errors": multi_timeframe_errors,
        "source": f"Yahoo Finance {timeframe} candles",
        "warning": (
            f"Candidate zones are inferred from {timeframe} swing pivots, not "
            "institutional order-flow data. They are educational indicators, "
            "not guaranteed forecasts or investment advice."
        ),
        **analysis,
    })


def _valid_feature_csrf():
    submitted = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token", "")
    return bool(submitted and expected and hmac.compare_digest(submitted, expected))


def _feature_symbols():
    return {item["symbol"] for item in MARKET_DATA} | set(YAHOO_SYMBOL_ALIASES)


@app.route("/api/portfolio", methods=["GET", "POST"])
def portfolio():
    user_id = g.current_user["id"]
    if request.method == "POST":
        if not _valid_feature_csrf():
            return jsonify(error="Your session expired. Refresh the page and try again."), 400
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify(error="Enter portfolio details in the expected format."), 400
        symbol = str(payload.get("symbol", "")).strip().upper()
        quantity = payload.get("quantity")
        average_cost = payload.get("average_cost")
        if symbol not in {item["symbol"] for item in MARKET_DATA}:
            return jsonify(error="Choose a tracked stock for your portfolio."), 400
        existing_positions = list_positions(user_id)
        if (
            len(existing_positions) >= 25
            and all(item["symbol"] != symbol for item in existing_positions)
        ):
            return jsonify(error="A portfolio can contain up to 25 tracked stocks."), 400
        try:
            quantity = float(quantity)
            average_cost = float(average_cost)
        except (TypeError, ValueError):
            return jsonify(error="Enter a valid quantity and average cost."), 400
        if (
            not math.isfinite(quantity)
            or not math.isfinite(average_cost)
            or quantity <= 0
            or average_cost <= 0
            or quantity > 1_000_000_000
            or average_cost > 1_000_000_000
        ):
            return jsonify(error="Quantity and average cost must be positive valid numbers."), 400
        try:
            quote = fetch_yahoo_quote(symbol)
        except (requests.RequestException, ValueError, TypeError) as error:
            app.logger.warning("Portfolio quote lookup failed for %s: %s", symbol, error)
            return jsonify(error=f"A current Yahoo Finance quote is unavailable for {symbol}."), 503
        if quote["currency"] != "USD":
            return jsonify(error="Portfolio tracking currently supports USD-quoted stocks only."), 400
        return jsonify(position=add_position(user_id, symbol, quantity, average_cost)), 201

    positions = list_positions(user_id)
    with ThreadPoolExecutor(max_workers=4) as executor:
        quote_futures = {
            executor.submit(fetch_yahoo_quote, position["symbol"]): position
            for position in positions
        }
        for future in as_completed(quote_futures):
            position = quote_futures[future]
            try:
                quote = future.result()
                if quote["currency"] != "USD":
                    raise ValueError("This holding is not quoted in USD.")
                position["current_price"] = quote["price"]
                position["market_value"] = round(
                    position["quantity"] * quote["price"], 2
                )
                position["gain_loss"] = round(
                    position["quantity"]
                    * (quote["price"] - position["average_cost"]),
                    2,
                )
                position["gain_loss_percent"] = round(
                    (quote["price"] / position["average_cost"] - 1) * 100,
                    2,
                )
                position["quote_time"] = quote["timestamp"]
            except (requests.RequestException, ValueError, TypeError) as error:
                app.logger.warning(
                    "Portfolio quote lookup failed for %s: %s",
                    position["symbol"],
                    error,
                )
                position["quote_error"] = (
                    f"Current quote unavailable for {position['symbol']}."
                )

    complete = all("quote_error" not in position for position in positions)
    total_cost = round(
        sum(position["quantity"] * position["average_cost"] for position in positions),
        2,
    )
    total_value = (
        round(sum(position["market_value"] for position in positions), 2)
        if complete else None
    )
    if complete and total_value:
        for position in positions:
            position["allocation_percent"] = round(
                position["market_value"] / total_value * 100,
                2,
            )
    return jsonify({
        "positions": positions,
        "total_cost": total_cost,
        "total_value": total_value,
        "gain_loss": (
            round(sum(position["gain_loss"] for position in positions), 2)
            if complete else None
        ),
        "gain_loss_percent": (
            round(sum(position["gain_loss"] for position in positions) / total_cost * 100, 2)
            if complete and total_cost else None
        ),
        "quotes_complete": complete,
    })


@app.route("/api/portfolio/<int:position_id>", methods=["DELETE"])
def delete_portfolio_position(position_id):
    if not _valid_feature_csrf():
        return jsonify(error="Your session expired. Refresh the page and try again."), 400
    if not remove_position(g.current_user["id"], position_id):
        return jsonify(error="Portfolio position not found."), 404
    return jsonify(success=True)


@app.route("/api/price-alerts", methods=["GET", "POST"])
def price_alerts():
    user_id = g.current_user["id"]
    if request.method == "POST":
        if not _valid_feature_csrf():
            return jsonify(error="Your session expired. Refresh the page and try again."), 400
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify(error="Enter alert details in the expected format."), 400
        symbol = str(payload.get("symbol", "")).strip().upper()
        alert_type = payload.get("alert_type")
        direction = payload.get("direction")
        threshold = payload.get("threshold")
        if symbol not in _feature_symbols():
            return jsonify(error="Choose a supported stock, forex pair, or gold futures symbol."), 400
        if len(list_alerts(user_id, active_only=True)) >= 10:
            return jsonify(error="You can have up to 10 active price alerts at a time."), 400
        if (
            not isinstance(alert_type, str)
            or alert_type not in {"price", "percent"}
            or not isinstance(direction, str)
            or direction not in {"above", "below"}
        ):
            return jsonify(error="Choose a valid alert type and direction."), 400
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            return jsonify(error="Enter a valid alert threshold."), 400
        if not math.isfinite(threshold) or threshold <= 0 or threshold > 1_000_000_000:
            return jsonify(error="Alert threshold must be a positive valid number."), 400
        if alert_type == "percent" and threshold > 1000:
            return jsonify(error="Percentage movement must be 1,000% or less."), 400
        try:
            quote = fetch_yahoo_quote(symbol)
        except (requests.RequestException, ValueError, TypeError) as error:
            app.logger.warning("Price alert quote lookup failed for %s: %s", symbol, error)
            return jsonify(error=f"A current Yahoo Finance quote is unavailable for {symbol}."), 503
        alert = add_alert(
            user_id,
            symbol,
            alert_type,
            direction,
            threshold,
            quote["price"],
        )
        return jsonify(alert=alert, baseline_price=quote["price"]), 201

    return jsonify(alerts=list_alerts(user_id))


@app.post("/api/price-alerts/zone")
def create_zone_alert():
    if not _valid_feature_csrf():
        return jsonify(error="Your session expired. Refresh the page and try again."), 400
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(error="Enter zone alert details in the expected format."), 400
    symbol = str(payload.get("symbol", "")).strip().upper()
    timeframe = payload.get("timeframe")
    zone_type = payload.get("zone_type")
    if symbol not in _feature_symbols():
        return jsonify(error="Choose a supported stock, forex pair, or gold futures symbol."), 400
    if not isinstance(timeframe, str) or timeframe not in {"5m", "15m", "1h", "1d"}:
        return jsonify(error="Choose a supported zone timeframe."), 400
    if not isinstance(zone_type, str) or zone_type not in {"demand", "supply"}:
        return jsonify(error="Choose a demand or supply zone."), 400
    if len(list_alerts(g.current_user["id"], active_only=True)) >= 10:
        return jsonify(error="You can have up to 10 active price alerts at a time."), 400
    try:
        zone_low = float(payload.get("zone_low"))
        zone_high = float(payload.get("zone_high"))
    except (TypeError, ValueError):
        return jsonify(error="Enter valid zone boundaries."), 400
    if (
        not math.isfinite(zone_low)
        or not math.isfinite(zone_high)
        or zone_low <= 0
        or zone_high <= zone_low
        or zone_high > 1_000_000_000
    ):
        return jsonify(error="Zone boundaries must be positive, with the low below the high."), 400
    alert = add_alert(
        g.current_user["id"],
        symbol,
        "zone",
        "inside",
        zone_high,
        zone_low,
        zone_timeframe=timeframe,
        zone_type=zone_type,
    )
    return jsonify(alert=alert), 201


@app.post("/api/price-alerts/check")
def check_price_alerts():
    if not _valid_feature_csrf():
        return jsonify(error="Your session expired. Refresh the page and try again."), 400
    user_id = g.current_user["id"]
    alerts = list_alerts(user_id, active_only=True)
    quote_keys = {
        (
            alert["symbol"],
            alert["zone_timeframe"] if alert["alert_type"] == "zone" else "5m",
        )
        for alert in alerts
    }
    quotes = {}
    errors = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        quote_futures = {
            executor.submit(fetch_yahoo_quote, symbol, timeframe): (symbol, timeframe)
            for symbol, timeframe in quote_keys
        }
        for future in as_completed(quote_futures):
            symbol, timeframe = quote_futures[future]
            try:
                quotes[(symbol, timeframe)] = future.result()["price"]
            except (requests.RequestException, ValueError, TypeError) as error:
                app.logger.warning(
                    "Price alert check failed for %s (%s): %s",
                    symbol,
                    timeframe,
                    error,
                )
                errors.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "error": f"Could not check {symbol} ({timeframe}).",
                })

    triggered = []
    live_alerts = []
    for alert in alerts:
        quote_timeframe = (
            alert["zone_timeframe"] if alert["alert_type"] == "zone" else "5m"
        )
        current_price = quotes.get((alert["symbol"], quote_timeframe))
        if current_price is None:
            continue
        if alert["alert_type"] == "zone":
            inside_zone = alert["baseline_price"] <= current_price <= alert["threshold"]
            hit = inside_zone
        elif alert["alert_type"] == "price":
            inside_zone = False
            hit = (
                current_price >= alert["threshold"]
                if alert["direction"] == "above"
                else current_price <= alert["threshold"]
            )
        else:
            inside_zone = False
            change = (
                (current_price / alert["baseline_price"] - 1) * 100
                if alert["baseline_price"] else 0
            )
            hit = (
                change >= alert["threshold"]
                if alert["direction"] == "above"
                else change <= -alert["threshold"]
            )
        distance_to_zone = None
        if alert["alert_type"] == "zone":
            progress = 100 if inside_zone else 0
            distance_to_zone = (
                alert["baseline_price"] - current_price
                if current_price < alert["baseline_price"]
                else current_price - alert["threshold"]
                if current_price > alert["threshold"]
                else 0
            )
        elif alert["alert_type"] == "percent":
            current_move = (
                (current_price / alert["baseline_price"] - 1) * 100
                if alert["baseline_price"] else 0
            )
            target_move = (
                alert["threshold"]
                if alert["direction"] == "above"
                else -alert["threshold"]
            )
            progress = 100 if hit else (
                max(0, min(100, current_move / target_move * 100))
                if target_move else 0
            )
        else:
            baseline_price = alert["baseline_price"] or current_price
            current_move = current_price - baseline_price
            target_move = alert["threshold"] - baseline_price
            progress = 100 if hit else (
                max(0, min(100, current_move / target_move * 100))
                if target_move else 0
            )
        live_alerts.append({
            "id": alert["id"],
            "current_price": current_price,
            "inside_zone": inside_zone,
            "distance_to_zone": distance_to_zone,
            "distance_to_zone_percent": round(
                distance_to_zone / current_price * 100,
                2,
            ) if distance_to_zone is not None and current_price else None,
            "current_move_percent": round(
                (current_price / alert["baseline_price"] - 1) * 100,
                2,
            ) if alert["baseline_price"] else 0,
            "progress_percent": round(progress, 1),
        })
        if hit and mark_alert_fired(user_id, alert["id"]):
            triggered.append({
                **alert,
                "current_price": current_price,
            })
    return jsonify(
        triggered=triggered,
        live_alerts=live_alerts,
        errors=errors,
        checked_symbols=len(quote_keys) - len(errors),
    )


@app.delete("/api/price-alerts/<int:alert_id>")
def delete_price_alert(alert_id):
    if not _valid_feature_csrf():
        return jsonify(error="Your session expired. Refresh the page and try again."), 400
    if not remove_alert(g.current_user["id"], alert_id):
        return jsonify(error="Price alert not found."), 404
    return jsonify(success=True)


# --------------------------------------------------
# CAREER SEARCH
# --------------------------------------------------

@app.route("/api/careers")
def careers():
    keyword = (request.args.get("q") or request.args.get("keyword") or "").strip()[:120]
    location = request.args.get("location", "").strip()[:120]
    company = request.args.get("company", "").strip()[:100]
    page = request.args.get("page", default=1, type=int) or 1
    page = max(1, min(page, 100))

    try:
        result = search_careers(keyword, location, page=page, company=company)
    except RuntimeError as exc:
        return jsonify(success=False, error=str(exc)), 503

    return jsonify(success=True, **result)


@app.route("/api/assistant", methods=["POST"])
def assistant():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify(error="Request body must be a JSON object."), 400
    text = body.get("message", "")
    if not isinstance(text, str):
        return jsonify(error="Message must be a string."), 400
    raw_history = body.get("history", [])
    if not isinstance(raw_history, list):
        return jsonify(error="Conversation history must be a list."), 400

    history = []
    for item in raw_history[-20:]:
        if (
            not isinstance(item, dict)
            or item.get("role") not in {"user", "assistant"}
            or not isinstance(item.get("content"), str)
        ):
            return jsonify(error="Conversation history contains an invalid message."), 400
        message = {"role": item["role"], "content": item["content"][:500]}
        context = item.get("context")
        if isinstance(context, dict):
            safe_context = {}
            focus_symbols = context.get("focus_symbols")
            if isinstance(focus_symbols, list):
                safe_context["focus_symbols"] = [
                    symbol.upper()
                    for symbol in focus_symbols[:8]
                    if isinstance(symbol, str)
                    and re.fullmatch(r"[A-Za-z0-9._-]{1,15}", symbol)
                ]
            focus_sector = context.get("focus_sector")
            if isinstance(focus_sector, str) and focus_sector in SECTOR_ORDER:
                safe_context["focus_sector"] = focus_sector
            if safe_context:
                message["context"] = safe_context
        history.append(message)

    market_data = None
    normalized_text = text.casefold()
    needs_live_market_data = any(term in normalized_text for term in (
        "compare", "comparison", "versus", " vs ",
        "top mover", "biggest movers", "largest movers",
    ))
    if needs_live_market_data:
        market_data = enrich_live_market(MARKET_DATA, max_live_symbols=8)
    elif (
        any(
            isinstance(item.get("context"), dict)
            and item["context"].get("focus_sector") in SECTOR_ORDER
            for item in history
        )
        and any(term in normalized_text for term in ("company", "companies", "stocks"))
    ):
        market_data = MARKET_DATA

    return jsonify(interpret_command(text[:500], history, market_data))


# --------------------------------------------------
# PDF REPORT
# --------------------------------------------------

@app.route("/api/report", methods=["GET", "POST"])
def report():
    df = pd.DataFrame(MARKET_DATA)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    _, height = A4
    y = height - 60

    pdf.setTitle("FinPulse AI Analytics Report")

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(50, y, "FinPulse AI")

    y -= 28

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, y, "Market Analytics Report")

    y -= 24

    pdf.setFont("Helvetica", 9)
    pdf.drawString(
        50, y,
        "DEMO REPORT - Prices and changes are illustrative, not live."
    )

    y -= 35

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, "Symbol")
    pdf.drawString(115, y, "Company")
    pdf.drawString(290, y, "Sector")
    pdf.drawString(405, y, "Sample Price")
    pdf.drawString(500, y, "Change %")

    y -= 18
    pdf.setFont("Helvetica", 9)

    for row in MARKET_DATA:
        if y < 70:
            pdf.showPage()
            y = height - 60
            pdf.setFont("Helvetica", 9)

        pdf.drawString(50, y, row["symbol"])
        pdf.drawString(115, y, row["company"][:25])
        pdf.drawString(290, y, row["sector"])
        pdf.drawRightString(455, y, f'{row["price"]:.2f}')
        pdf.drawRightString(545, y, f'{row["change"]:.2f}%')

        y -= 18

    y -= 15

    if y < 100:
        pdf.showPage()
        y = height - 60

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Summary")

    y -= 20

    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        50, y,
        f"Average sample percentage change: {df['change'].mean():.2f}%"
    )

    y -= 18

    pdf.drawString(
        50, y,
        "This report is for educational demonstration only."
    )

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="FinPulse_AI_Report.pdf"
    )


@app.get("/api/report/csv")
def report_csv():
    csv_data = pd.DataFrame(MARKET_DATA).to_csv(index=False).encode("utf-8-sig")
    buffer = io.BytesIO(csv_data)
    return send_file(
        buffer,
        mimetype="text/csv",
        as_attachment=True,
        download_name="FinPulse_AI_Market_Report.csv"
    )


@app.get("/api/report/xlsx")
def report_xlsx():
    buffer = io.BytesIO()
    pd.DataFrame(MARKET_DATA).to_excel(
        buffer,
        index=False,
        sheet_name="Market Data"
    )
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="FinPulse_AI_Market_Report.xlsx"
    )


# --------------------------------------------------
# RUN SERVER
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
