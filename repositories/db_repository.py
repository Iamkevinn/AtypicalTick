# db_repository.py
"""
Capa central de acceso a datos.

Objetivo: que el resto del código (services/, core/, db/) siga escribiendo
SQL casi igual que hoy (con placeholders `?`, como en SQLite), sin tener
que preocuparse por si detrás corre SQLite (desarrollo local) o Postgres
(producción, Supabase/Render).

Cómo decide qué motor usar:
- Si la variable de entorno DATABASE_URL está configurada -> Postgres (psycopg3)
- Si no -> SQLite local (comportamiento actual, sin cambios)

Uso típico en un archivo de servicio:

    from repositories.db_repository import db_connection, execute, fetch_one, fetch_all

    with db_connection() as conn:
        execute(conn, "INSERT INTO sesiones_tarea (tarea_id) VALUES (?)", (tarea_id,))

    with db_connection() as conn:
        fila = fetch_one(conn, "SELECT * FROM sesiones_tarea WHERE tarea_id = ?", (tarea_id,))

Nota importante: esta capa NO traduce sintaxis de schema (AUTOINCREMENT,
strftime, PRAGMA). Eso se resuelve en la Fase 3 del plan de migración,
cuando reescribamos los CREATE TABLE. Esta capa solo resuelve la forma de
ejecutar queries (placeholders y acceso a filas), que es el 90% del código
disperso hoy.
"""

import logging
import sqlite3
from contextlib import contextmanager

from config import DATABASE_URL, SQLITE_DB_PATH, SQLITE_TIMEOUT_SECONDS

USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg
    from psycopg_pool import ConnectionPool
    # Excepción que se dispara al violar una restricción UNIQUE/PRIMARY KEY.
    # Se expone unificada como IntegrityError para que el código de
    # negocio (ej. locks atómicos como en gestion_horario_estricto.py)
    # pueda hacer "except IntegrityError" sin preocuparse de si corre
    # sobre SQLite o Postgres.
    IntegrityError = psycopg.errors.UniqueViolation

    # Pool de conexiones: se crea UNA sola vez (perezosamente, en el primer
    # uso) y se reutiliza en cada request. Antes, cada llamada a
    # db_connection() abría una conexión TCP+TLS nueva contra Supabase desde
    # cero (100-300ms cada una) y la cerraba al terminar -- con varias
    # decenas de queries por request (una por tarea de TickTick), esto por
    # sí solo explicaba varios segundos de latencia extra. Con el pool,
    # esas conexiones se abren una vez y se reciclan.
    _pool: "ConnectionPool | None" = None

    def _obtener_pool() -> "ConnectionPool":
        global _pool
        if _pool is None:
            _pool = ConnectionPool(
                DATABASE_URL,
                min_size=1,
                max_size=5,
                open=True,
            )
        return _pool
else:
    IntegrityError = sqlite3.IntegrityError


def _adaptar_placeholders(query: str) -> str:
    """
    Convierte placeholders estilo SQLite (?) a estilo psycopg (%s).

    Limitación conocida: si algún día un query SQLite tiene un `?` dentro
    de un string literal (ej. una columna con contenido '¿Qué tal?'), esto
    lo reemplazaría también. Revisado hoy: ningún query del proyecto tiene
    ese caso, todos los `?` son placeholders reales. Si se agrega uno así
    en el futuro, usar CHR(63) o similar en el literal en vez de `?`.
    """
    if not USE_POSTGRES:
        return query
    return query.replace("?", "%s")


@contextmanager
def db_connection():
    """
    Reemplaza a db/connection.py::db_connection(). Mismo comportamiento
    de commit/rollback/logging, pero soporta ambos motores.
    """
    if USE_POSTGRES:
        pool = _obtener_pool()
        with pool.connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                logging.exception("Error usando la base de datos Postgres")
                raise
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH, timeout=SQLITE_TIMEOUT_SECONDS)
        conn.row_factory = sqlite3.Row
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


def execute(conn, query: str, params: tuple = ()):
    """
    Ejecuta un query (INSERT/UPDATE/DELETE o SELECT manual).
    Reemplaza tanto a `conn.execute(...)` como a `cursor = conn.cursor(); cursor.execute(...)`.

    Devuelve el cursor, por si el llamador necesita cursor.lastrowid
    (ojo: en Postgres, lastrowid no existe -- usar RETURNING id en el
    query si se necesita el id insertado; esto se revisa caso por caso
    en la Fase 3).
    """
    query = _adaptar_placeholders(query)
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor


def _fila_a_dict(cursor, row):
    """
    Construye un dict {columna: valor} a partir de cursor.description,
    sin depender de row_factory especiales de psycopg (dict_row). Así
    fetch_one/fetch_all funcionan igual en SQLite y Postgres, y el resto
    del código (que hoy accede por posición, ej. fila[0], o desempaqueta
    tuplas) sigue funcionando porque las filas base siguen siendo
    tuplas/sqlite3.Row -- este dict es solo una conveniencia adicional
    para código nuevo que prefiera acceder por nombre de columna.
    """
    columnas = [c[0] for c in cursor.description]
    return dict(zip(columnas, row))


def fetch_one(conn, query: str, params: tuple = ()):
    """Devuelve una fila como dict (acceso por nombre de columna), o None."""
    cursor = execute(conn, query, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return _fila_a_dict(cursor, row)


def fetch_all(conn, query: str, params: tuple = ()):
    """Devuelve todas las filas como lista de dicts."""
    cursor = execute(conn, query, params)
    rows = cursor.fetchall()
    return [_fila_a_dict(cursor, r) for r in rows]