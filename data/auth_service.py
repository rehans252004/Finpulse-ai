"""SQLite-backed user storage for FinPulse authentication."""
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def database_path():
    configured_path = os.environ.get("FINPULSE_DATABASE")
    path = configured_path or os.path.join(
        PROJECT_ROOT,
        "instance",
        "finpulse.sqlite3",
    )
    os.makedirs(os.path.dirname(os.path.abspath(path)), mode=0o700, exist_ok=True)
    return path


def _connect():
    connection = sqlite3.connect(database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_auth_db():
    path = database_path()
    with closing(_connect()) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                full_name TEXT NOT NULL DEFAULT '',
                phone_e164 TEXT,
                phone_verified INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(users)")
        }
        for column, definition in (
            ("full_name", "TEXT NOT NULL DEFAULT ''"),
            ("phone_e164", "TEXT"),
            ("phone_verified", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE users ADD COLUMN {column} {definition}"
                )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS users_phone_e164_unique
            ON users (phone_e164)
            WHERE phone_e164 IS NOT NULL
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_signups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                phone_e164 TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_phone_changes (
                user_id INTEGER PRIMARY KEY,
                phone_e164 TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """
        )
        connection.commit()
    os.chmod(path, 0o600)


def normalize_email(email):
    return email.strip().lower()


def is_valid_email(email):
    return (
        len(email) <= 254
        and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is not None
    )


def normalize_phone(phone):
    return re.sub(r"[\s().-]", "", phone.strip())


def is_valid_phone(phone):
    return re.fullmatch(r"\+[1-9]\d{7,14}", normalize_phone(phone)) is not None


def create_user(
    email,
    password,
    full_name="",
    phone_e164=None,
    phone_verified=False,
):
    password_hash = generate_password_hash(
        password,
        method="pbkdf2:sha256:600000",
    )
    try:
        with closing(_connect()) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (
                        email, password_hash, created_at, full_name,
                        phone_e164, phone_verified
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalize_email(email),
                        password_hash,
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        full_name.strip(),
                        phone_e164,
                        int(phone_verified),
                    ),
                )
                return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def create_pending_signup(email, phone_e164, full_name, password):
    password_hash = generate_password_hash(
        password,
        method="pbkdf2:sha256:600000",
    )
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=10)).isoformat(timespec="seconds")
    try:
        with closing(_connect()) as connection:
            with connection:
                existing_user = connection.execute(
                    """
                    SELECT 1 FROM users
                    WHERE email = ? COLLATE NOCASE OR phone_e164 = ?
                    """,
                    (normalize_email(email), phone_e164),
                ).fetchone()
                if existing_user:
                    return None

                connection.execute(
                    "DELETE FROM pending_signups WHERE expires_at <= ?",
                    (now.isoformat(timespec="seconds"),),
                )
                cursor = connection.execute(
                    """
                    INSERT INTO pending_signups (
                        email, phone_e164, full_name, password_hash, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(email) DO UPDATE SET
                        phone_e164 = excluded.phone_e164,
                        full_name = excluded.full_name,
                        password_hash = excluded.password_hash,
                        expires_at = excluded.expires_at
                    """,
                    (
                        normalize_email(email),
                        phone_e164,
                        full_name.strip(),
                        password_hash,
                        expires_at,
                    ),
                )
                return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_pending_signup(pending_id):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(_connect()) as connection:
        return connection.execute(
            """
            SELECT id, email, phone_e164, full_name, password_hash, expires_at
            FROM pending_signups
            WHERE id = ? AND expires_at > ?
            """,
            (pending_id, now),
        ).fetchone()


def complete_pending_signup(pending_id):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with closing(_connect()) as connection:
            with connection:
                pending = connection.execute(
                    """
                    SELECT email, phone_e164, full_name, password_hash
                    FROM pending_signups
                    WHERE id = ? AND expires_at > ?
                    """,
                    (pending_id, now),
                ).fetchone()
                if pending is None:
                    return None

                cursor = connection.execute(
                    """
                    INSERT INTO users (
                        email, password_hash, created_at, full_name,
                        phone_e164, phone_verified
                    )
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (
                        pending["email"],
                        pending["password_hash"],
                        now,
                        pending["full_name"],
                        pending["phone_e164"],
                    ),
                )
                user_id = cursor.lastrowid
                connection.execute(
                    "DELETE FROM pending_signups WHERE id = ?",
                    (pending_id,),
                )
                return user_id
    except sqlite3.IntegrityError:
        return None


def create_pending_phone_change(user_id, phone_e164):
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=10)).isoformat(timespec="seconds")
    with closing(_connect()) as connection:
        with connection:
            existing_user = connection.execute(
                """
                SELECT 1 FROM users
                WHERE phone_e164 = ? AND id != ?
                """,
                (phone_e164, user_id),
            ).fetchone()
            if existing_user:
                return False
            connection.execute(
                """
                INSERT INTO pending_phone_changes (user_id, phone_e164, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    phone_e164 = excluded.phone_e164,
                    expires_at = excluded.expires_at
                """,
                (user_id, phone_e164, expires_at),
            )
    return True


def get_pending_phone_change(user_id):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(_connect()) as connection:
        return connection.execute(
            """
            SELECT phone_e164
            FROM pending_phone_changes
            WHERE user_id = ? AND expires_at > ?
            """,
            (user_id, now),
        ).fetchone()


def complete_pending_phone_change(user_id):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with closing(_connect()) as connection:
            with connection:
                pending = connection.execute(
                    """
                    SELECT phone_e164
                    FROM pending_phone_changes
                    WHERE user_id = ? AND expires_at > ?
                    """,
                    (user_id, now),
                ).fetchone()
                if pending is None:
                    return False
                connection.execute(
                    """
                    UPDATE users
                    SET phone_e164 = ?, phone_verified = 1
                    WHERE id = ?
                    """,
                    (pending["phone_e164"], user_id),
                )
                connection.execute(
                    "DELETE FROM pending_phone_changes WHERE user_id = ?",
                    (user_id,),
                )
    except sqlite3.IntegrityError:
        return False
    return True


def get_user_by_identifier(identifier):
    value = identifier.strip()
    if "@" in value:
        return get_user_by_email(value)
    phone = normalize_phone(value)
    with closing(_connect()) as connection:
        return connection.execute(
            """
            SELECT id, email, password_hash, full_name, phone_e164,
                   phone_verified, created_at
            FROM users
            WHERE phone_e164 = ? AND phone_verified = 1
            """,
            (phone,),
        ).fetchone()


def get_user_by_email(email):
    with closing(_connect()) as connection:
        return connection.execute(
            """
            SELECT id, email, password_hash, full_name, phone_e164,
                   phone_verified, created_at
            FROM users
            WHERE email = ? COLLATE NOCASE
            """,
            (normalize_email(email),),
        ).fetchone()


def get_user_by_id(user_id):
    with closing(_connect()) as connection:
        return connection.execute(
            """
            SELECT id, email, full_name, phone_e164, phone_verified, created_at
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()


def update_user_profile(user_id, full_name):
    with closing(_connect()) as connection:
        with connection:
            connection.execute(
                "UPDATE users SET full_name = ? WHERE id = ?",
                (full_name.strip(), user_id),
            )


def update_user_password(user_id, password):
    password_hash = generate_password_hash(
        password,
        method="pbkdf2:sha256:600000",
    )
    with closing(_connect()) as connection:
        with connection:
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, user_id),
            )
