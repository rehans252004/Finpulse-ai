"""Twilio Verify integration for phone-number verification."""
import os

import requests


class SmsConfigurationError(ValueError):
    """Raised when Twilio Verify is not configured."""


class SmsDeliveryError(RuntimeError):
    """Raised when Twilio cannot send or confirm a verification."""


def phone_verification_configured():
    return all(
        os.getenv(name, "").strip()
        for name in (
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_VERIFY_SERVICE_SID",
        )
    )


def _twilio_settings():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    service_sid = os.getenv("TWILIO_VERIFY_SERVICE_SID", "").strip()
    if not account_sid or not auth_token or not service_sid:
        raise SmsConfigurationError(
            "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and "
            "TWILIO_VERIFY_SERVICE_SID in .env."
        )
    return account_sid, auth_token, service_sid


def _request(path, data):
    account_sid, auth_token, service_sid = _twilio_settings()
    url = (
        "https://verify.twilio.com/v2/Services/"
        f"{service_sid}/{path}"
    )
    try:
        response = requests.post(
            url,
            data=data,
            auth=(account_sid, auth_token),
            timeout=(5, 15),
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise SmsDeliveryError(
            "Twilio could not process the phone verification. Check the "
            "Twilio configuration and try again."
        ) from error
    try:
        payload = response.json()
    except ValueError as error:
        raise SmsDeliveryError(
            "Twilio returned an invalid response for phone verification."
        ) from error
    if not isinstance(payload, dict):
        raise SmsDeliveryError(
            "Twilio returned an invalid response for phone verification."
        )
    return payload


def send_phone_verification(phone_e164):
    response = _request(
        "Verifications",
        {"To": phone_e164, "Channel": "sms"},
    )
    if response.get("status") != "pending":
        raise SmsDeliveryError(
            "Twilio did not start the phone verification. Check the number "
            "and Twilio Verify service."
        )


def check_phone_verification(phone_e164, code):
    response = _request(
        "VerificationCheck",
        {"To": phone_e164, "Code": code},
    )
    return response.get("status") == "approved"
