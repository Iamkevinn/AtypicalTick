import logging
import sqlite3
from contextlib import contextmanager

DB_PATH = "atypical_data.db"
SQLITE_TIMEOUT_SECONDS = 30


@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=SQLITE_TIMEOUT_SECONDS)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        logging.exception("Error usando la base de datos SQLite")
        raise
    finally:
        conn.close()
