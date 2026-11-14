from flask import Blueprint, jsonify

from .market_service import get_company, market_status

bp = Blueprint("market", __name__, url_prefix="/api/market")


@bp.get("/quote/<symbol>")
def quote(symbol):
    normalized_symbol = symbol.strip().upper()
    company = get_company(normalized_symbol)
    if company is None:
        return jsonify(error=f"No market data found for {normalized_symbol}."), 404

    return jsonify({**company, **market_status()})
