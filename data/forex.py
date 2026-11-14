from flask import Blueprint, jsonify, request

from .forex_service import get_currencies, get_rate

bp = Blueprint("forex", __name__, url_prefix="/api/forex")


@bp.get("/currencies")
def currencies():
    try:
        return jsonify(currencies=get_currencies(), source="Frankfurter reference rates")
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 502

@bp.get("/rate")
def rate():
    base = request.args.get("base", "USD")
    quote = request.args.get("quote", "INR")
    try:
        return jsonify(get_rate(base, quote))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 502
