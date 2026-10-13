import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from flask import g, current_app

from config import Config


def get_db_path():
    """Resolve database path from current app config or default Config."""
    if current_app:
        return current_app.config.get("DATABASE_PATH", Config.DATABASE_PATH)
    return Config.DATABASE_PATH


def create_connection(db_path=None):
    """Create and return a configured raw SQLite connection."""
    path = db_path or get_db_path()
    if path != ":memory:":
        parent_dir = Path(path).parent
        parent_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        path,
        timeout=15.0,
    )
    conn.row_factory = sqlite3.Row
    # Crucial: enable foreign key support for data integrity
    conn.execute("PRAGMA foreign_keys = ON;")
    # Better concurrency for readers & writers
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def get_db():
    """Retrieve or create a database connection scoped to the current Flask request."""
    if "db" not in g:
        g.db = create_connection()
    return g.db


def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(db_path=None, schema_file=None):
    """Initialize database tables using schema.sql."""
    schema_path = schema_file or (Path(__file__).resolve().parent / "schema.sql")
    conn = create_connection(db_path)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def query_db(query, args=(), one=False, conn=None):
    """Execute a read query and return dictionary-like rows."""
    close_after = False
    if conn is None:
        if current_app:
            conn = get_db()
        else:
            conn = create_connection()
            close_after = True

    try:
        cur = conn.execute(query, args)
        rv = cur.fetchall()
        cur.close()
        return (rv[0] if rv else None) if one else rv
    finally:
        if close_after:
            conn.close()


def execute_db(query, args=(), commit=True, conn=None):
    """Execute an INSERT/UPDATE/DELETE query with parameterization."""
    close_after = False
    if conn is None:
        if current_app:
            conn = get_db()
        else:
            conn = create_connection()
            close_after = True

    try:
        cur = conn.execute(query, args)
        if commit:
            conn.commit()
        last_id = cur.lastrowid
        row_count = cur.rowcount
        cur.close()
        return {"lastrowid": last_id, "rowcount": row_count}
    finally:
        if close_after:
            conn.close()


@contextmanager
def transaction(conn=None):
    """Context manager for atomic database transactions with rollback on error."""
    close_after = False
    if conn is None:
        if current_app:
            conn = get_db()
        else:
            conn = create_connection()
            close_after = True

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if close_after:
            conn.close()
