import logging
import sqlite3

from contextlib import contextmanager

from config import SQLITE_DB_PATH
from config import SQLITE_TIMEOUT_SECONDS


@contextmanager
def db_connection():

    conn = sqlite3.connect(
        SQLITE_DB_PATH,
        timeout=SQLITE_TIMEOUT_SECONDS
    )

    try:

        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 30000")

        yield conn

        conn.commit()

    except Exception:

        conn.rollback()

        logging.exception(
            "Error usando la base de datos SQLite"
        )

        raise

    finally:

        conn.close()