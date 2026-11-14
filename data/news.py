from flask import Blueprint, jsonify, request

from .news_service import FinnhubConfigurationError, get_news

bp = Blueprint("news", __name__)


@bp.get("/api/news")
def news():
    symbol = request.args.get("symbol", "GENERAL")
    try:
        limit = int(request.args.get("limit", "40"))
        return jsonify(get_news(symbol, limit))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except FinnhubConfigurationError as exc:
        return jsonify(error=str(exc)), 503
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 502
