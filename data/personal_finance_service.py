"""Persistence and Yahoo Finance quote helpers for personal dashboard features."""
from contextlib import closing
from datetime import datetime, timezone
import sqlite3

import requests

from .auth_service import database_path
from .supply_demand_service import YAHOO_SYMBOL_ALIASES, yahoo_chart_to_candles


def _connect():
    connection = sqlite3.connect(database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_personal_finance_db():
    with closing(_connect()) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                quantity REAL NOT NULL,
                average_cost REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE (user_id, symbol)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                threshold REAL NOT NULL,
                baseline_price REAL,
                created_at TEXT NOT NULL,
                fired_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """
        )
        alert_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(price_alerts)")
        }
        for column, definition in (
            ("zone_timeframe", "TEXT"),
            ("zone_type", "TEXT"),
        ):
            if column not in alert_columns:
                connection.execute(
                    f"ALTER TABLE price_alerts ADD COLUMN {column} {definition}"
                )
        connection.commit()


def fetch_yahoo_quote(symbol, timeframe="5m"):
    """Return the latest available close for a Yahoo chart symbol/timeframe."""
    intervals = {
        "5m": ("5m", "5d"),
        "15m": ("15m", "60d"),
        "1h": ("60m", "60d"),
        "1d": ("1d", "1y"),
    }
    if timeframe not in intervals:
        raise ValueError("Unsupported quote timeframe.")
    interval, candle_range = intervals[timeframe]
    provider_symbol = YAHOO_SYMBOL_ALIASES.get(symbol, symbol)
    response = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{provider_symbol}",
        params={"range": candle_range, "interval": interval},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=12,
    )
    response.raise_for_status()
    candles = yahoo_chart_to_candles(response.json())
    price = candles["c"][-1]
    if price <= 0:
        raise ValueError("Yahoo Finance returned an invalid latest price.")
    return {
        "price": price,
        "currency": candles.get("currency"),
        "timestamp": candles["t"][-1],
        "provider_symbol": provider_symbol,
    }


def list_positions(user_id):
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT id, symbol, quantity, average_cost
            FROM portfolio_positions
            WHERE user_id = ?
            ORDER BY symbol
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_position(user_id, symbol, quantity, average_cost):
    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO portfolio_positions
                (user_id, symbol, quantity, average_cost)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, symbol) DO UPDATE SET
                average_cost = (
                    portfolio_positions.quantity * portfolio_positions.average_cost
                    + excluded.quantity * excluded.average_cost
                ) / (portfolio_positions.quantity + excluded.quantity),
                quantity = portfolio_positions.quantity + excluded.quantity
            """,
            (user_id, symbol, quantity, average_cost),
        )
        connection.commit()
    return next(
        item for item in list_positions(user_id) if item["symbol"] == symbol
    )


def remove_position(user_id, position_id):
    with closing(_connect()) as connection:
        cursor = connection.execute(
            "DELETE FROM portfolio_positions WHERE user_id = ? AND id = ?",
            (user_id, position_id),
        )
        connection.commit()
    return cursor.rowcount > 0


def list_alerts(user_id, active_only=False):
    query = """
        SELECT id, symbol, alert_type, direction, threshold,
           baseline_price, zone_timeframe, zone_type, created_at, fired_at
        FROM price_alerts
        WHERE user_id = ?
    """
    if active_only:
        query += " AND fired_at IS NULL"
    query += " ORDER BY id DESC"
    with closing(_connect()) as connection:
        rows = connection.execute(query, (user_id,)).fetchall()
    return [dict(row) for row in rows]


def add_alert(
    user_id,
    symbol,
    alert_type,
    direction,
    threshold,
    baseline_price,
    zone_timeframe=None,
    zone_type=None,
):
    with closing(_connect()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO price_alerts
                (user_id, symbol, alert_type, direction, threshold,
                 baseline_price, zone_timeframe, zone_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                symbol,
                alert_type,
                direction,
                threshold,
                baseline_price,
                zone_timeframe,
                zone_type,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        connection.commit()
        alert_id = cursor.lastrowid
    return next(item for item in list_alerts(user_id) if item["id"] == alert_id)


def mark_alert_fired(user_id, alert_id):
    with closing(_connect()) as connection:
        cursor = connection.execute(
            """
            UPDATE price_alerts SET fired_at = ?
            WHERE user_id = ? AND id = ? AND fired_at IS NULL
            """,
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), user_id, alert_id),
        )
        connection.commit()
    return cursor.rowcount > 0


def remove_alert(user_id, alert_id):
    with closing(_connect()) as connection:
        cursor = connection.execute(
            "DELETE FROM price_alerts WHERE user_id = ? AND id = ?",
            (user_id, alert_id),
        )
        connection.commit()
    return cursor.rowcount > 0
