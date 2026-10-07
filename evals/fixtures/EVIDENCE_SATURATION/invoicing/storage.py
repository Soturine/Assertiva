"""Persistence of issued invoices."""

import sqlite3


def connect(url: str) -> sqlite3.Connection:
    conn = sqlite3.connect(url)
    conn.execute("CREATE TABLE IF NOT EXISTS invoices (number TEXT PRIMARY KEY, total_cents INTEGER NOT NULL)")
    return conn


def save_invoice(conn: sqlite3.Connection, number: str, total_cents: int) -> None:
    with conn:
        conn.execute("INSERT INTO invoices (number, total_cents) VALUES (?, ?)", (number, total_cents))


def load_total(conn: sqlite3.Connection, number: str) -> int | None:
    row = conn.execute("SELECT total_cents FROM invoices WHERE number = ?", (number,)).fetchone()
    return row[0] if row else None
