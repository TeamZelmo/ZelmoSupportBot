"""SQLite database layer.

Convention: ``customer_id`` everywhere means the customer's *Telegram ID*
(``customers.telegram_id``). ``sender_id`` / partner ids are Telegram IDs too.
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import config

logger = logging.getLogger(__name__)

STATUS_AVAILABLE = "available"
STATUS_BUSY = "busy"
STATUS_OFFLINE = "offline"
VALID_STATUSES = (STATUS_AVAILABLE, STATUS_BUSY, STATUS_OFFLINE)

DIRECTION_CUSTOMER = "customer"
DIRECTION_PARTNER = "partner"

CHAT_PENDING = "pending"
CHAT_ACTIVE = "active"
CHAT_CLOSED = "closed"

_CUSTOMER_UPDATABLE = ("first_name", "username", "assigned_partner_id")

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    first_name TEXT,
    username TEXT,
    assigned_partner_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'offline'
        CHECK (status IN ('available', 'busy', 'offline')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(telegram_id),
    telegram_message_id INTEGER,
    sender_id INTEGER NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('customer', 'partner')),
    message_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(telegram_id),
    partner_id INTEGER,
    status TEXT NOT NULL CHECK (status IN ('pending', 'active', 'closed')),
    group_message_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    closed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_customer ON messages(customer_id, id);
CREATE INDEX IF NOT EXISTS idx_chats_customer_status ON chats(customer_id, status);
"""


class DatabaseError(Exception):
    """Raised when a database operation fails."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, rollback on error, always close."""
    conn = None
    try:
        conn = sqlite3.connect(config.DATABASE_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        if conn is not None:
            conn.rollback()
        logger.exception("Database error")
        raise DatabaseError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def _row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


# --------------------------------------------------------------------------
# Initialisation
# --------------------------------------------------------------------------
def init_database() -> None:
    """Create the database file, folders and tables if they do not exist."""
    try:
        Path(config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DatabaseError(f"Cannot create database folder: {exc}") from exc
    with _connect() as conn:
        conn.executescript(SCHEMA)
    logger.info("Database ready at %s", config.DATABASE_PATH)


# --------------------------------------------------------------------------
# Customers
# --------------------------------------------------------------------------
def add_customer(
    telegram_id: int, first_name: Optional[str], username: Optional[str]
) -> Dict[str, Any]:
    """Insert a customer, or refresh name/username if it already exists.

    The assignment (assigned_partner_id) is never touched here.
    """
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO customers (telegram_id, first_name, username, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                first_name = excluded.first_name,
                username = excluded.username,
                updated_at = excluded.updated_at
            """,
            (telegram_id, first_name, username, now, now),
        )
        row = conn.execute(
            "SELECT * FROM customers WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    return dict(row)


def get_customer(telegram_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    return _row(row)


def update_customer(telegram_id: int, /, **fields: Any) -> bool:
    """Update allowed customer fields. Returns True if a row was changed."""
    invalid = set(fields) - set(_CUSTOMER_UPDATABLE)
    if invalid:
        raise ValueError(f"Cannot update fields: {', '.join(sorted(invalid))}")
    if not fields:
        return False
    assignments = ", ".join(f"{name} = ?" for name in fields)
    params = list(fields.values()) + [_now(), telegram_id]
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE customers SET {assignments}, updated_at = ? WHERE telegram_id = ?",
            params,
        )
        return cur.rowcount > 0


def get_customer_partner(customer_id: int) -> Optional[int]:
    """Return the partner Telegram ID assigned to the customer (or None)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT assigned_partner_id FROM customers WHERE telegram_id = ?",
            (customer_id,),
        ).fetchone()
    return row["assigned_partner_id"] if row else None


def set_customer_partner(
    customer_id: int,
    partner_id: Optional[int],
    only_if_unassigned: bool = False,
) -> bool:
    """Assign (or clear, with partner_id=None) the partner of a customer.

    With ``only_if_unassigned=True`` the update is atomic: it succeeds only if
    nobody else holds the customer. Returns True when a row was changed.
    """
    query = "UPDATE customers SET assigned_partner_id = ?, updated_at = ? WHERE telegram_id = ?"
    if only_if_unassigned:
        query += " AND assigned_partner_id IS NULL"
    with _connect() as conn:
        cur = conn.execute(query, (partner_id, _now(), customer_id))
        return cur.rowcount > 0


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------
def save_message(
    customer_id: int,
    telegram_message_id: Optional[int],
    sender_id: int,
    direction: str,
    message_text: str,
) -> int:
    if direction not in (DIRECTION_CUSTOMER, DIRECTION_PARTNER):
        raise ValueError(f"Invalid direction: {direction}")
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO messages
                (customer_id, telegram_message_id, sender_id, direction, message_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (customer_id, telegram_message_id, sender_id, direction, message_text, _now()),
        )
        return int(cur.lastrowid)


def get_customer_messages(customer_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """Return the latest ``limit`` messages of a customer, oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE customer_id = ? ORDER BY id DESC LIMIT ?",
            (customer_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


# --------------------------------------------------------------------------
# Partners
# --------------------------------------------------------------------------
def add_partner(telegram_id: int, status: str = STATUS_OFFLINE) -> None:
    """Register a partner. An existing partner keeps its current status."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO partners (telegram_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (telegram_id, status, now, now),
        )


def get_partner_status(telegram_id: int) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT status FROM partners WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    return row["status"] if row else None


def set_partner_status(telegram_id: int, status: str) -> bool:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE partners SET status = ?, updated_at = ? WHERE telegram_id = ?",
            (status, _now(), telegram_id),
        )
        return cur.rowcount > 0


def get_available_partners() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM partners WHERE status = ? ORDER BY id", (STATUS_AVAILABLE,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_partners() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM partners ORDER BY id").fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Chats (group notification + open/closed state)
# --------------------------------------------------------------------------
def create_chat(customer_id: int, group_message_id: Optional[int]) -> int:
    """Create a pending chat for a customer (closes nothing; caller checks)."""
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO chats (customer_id, status, group_message_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (customer_id, CHAT_PENDING, group_message_id, now, now),
        )
        return int(cur.lastrowid)


def get_open_chat(customer_id: int) -> Optional[Dict[str, Any]]:
    """Return the customer's pending/active chat, if any."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM chats
            WHERE customer_id = ? AND status IN (?, ?)
            ORDER BY id DESC LIMIT 1
            """,
            (customer_id, CHAT_PENDING, CHAT_ACTIVE),
        ).fetchone()
    return _row(row)


def set_chat_active(customer_id: int, partner_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE chats SET status = ?, partner_id = ?, updated_at = ?
            WHERE customer_id = ? AND status = ?
            """,
            (CHAT_ACTIVE, partner_id, _now(), customer_id, CHAT_PENDING),
        )
        return cur.rowcount > 0


def set_chat_pending(customer_id: int) -> bool:
    """Roll an active chat back to pending (used if the partner cannot be reached)."""
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE chats SET status = ?, partner_id = NULL, updated_at = ?
            WHERE customer_id = ? AND status = ?
            """,
            (CHAT_PENDING, _now(), customer_id, CHAT_ACTIVE),
        )
        return cur.rowcount > 0


def close_chat(customer_id: int) -> bool:
    """Mark the open chat closed and clear the customer's assignment."""
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE chats SET status = ?, closed_at = ?, updated_at = ?
            WHERE customer_id = ? AND status IN (?, ?)
            """,
            (CHAT_CLOSED, now, now, customer_id, CHAT_PENDING, CHAT_ACTIVE),
        )
        changed = cur.rowcount > 0
        conn.execute(
            "UPDATE customers SET assigned_partner_id = NULL, updated_at = ? WHERE telegram_id = ?",
            (now, customer_id),
        )
        return changed


def get_pending_customers() -> List[Dict[str, Any]]:
    """Customers whose chat is waiting for a partner to press Take Chat."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*, ch.group_message_id AS group_message_id, ch.created_at AS chat_created_at
            FROM chats ch
            JOIN customers c ON c.telegram_id = ch.customer_id
            WHERE ch.status = ? AND c.assigned_partner_id IS NULL
            ORDER BY ch.id
            """,
            (CHAT_PENDING,),
        ).fetchall()
    return [dict(r) for r in rows]
