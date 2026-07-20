# feedback_discrepancia.py
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from db import db_connection
from repositories.db_repository import execute
from config import BOGOTA

# --- Zona horaria centralizada (ver main.py) ---
 


def init_tabla_feedback():
    # DEPRECATED (Fase 3): el schema ahora lo maneja Alembic. Ver nota
    # completa en main.py::init_db().
    logging.warning(
        "init_tabla_feedback() esta obsoleta -- el schema lo maneja Alembic."
    )


def registrar_feedback_discrepancia(motivo_declarado: str, energia: str, intervencion_sugerida: str, respuesta: str):
    try:
        with db_connection() as conn:
            execute(conn, '''
                INSERT INTO feedback_discrepancia (motivo_declarado, energia, intervencion_sugerida, respuesta, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (motivo_declarado, energia, intervencion_sugerida, respuesta, datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S")))
    except Exception as e:
        logging.exception("Error al guardar feedback de discrepancia: %s", e)


def fue_rechazada_antes(motivo_declarado: str, energia: str, intervencion_sugerida: str) -> bool:
    try:
        with db_connection() as conn:
            cursor = execute(conn, '''
                SELECT respuesta FROM feedback_discrepancia
                WHERE motivo_declarado = ? AND energia = ? AND intervencion_sugerida = ?
                ORDER BY timestamp DESC LIMIT 1
            ''', (motivo_declarado, energia, intervencion_sugerida))
            fila = cursor.fetchone()

        respuesta = (fila[0] or "").strip().lower() if fila else ""
        if respuesta in ("no_es_eso", "no es eso"):
            return True
        return False
    except Exception as e:
        logging.exception("Error consultando feedback de discrepancia: %s", e)
        return False