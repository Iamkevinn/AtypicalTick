# db/pospuestas_hoy.py
import logging
from datetime import datetime

from config import BOGOTA
from repositories.db_repository import db_connection, execute, fetch_all
from utils.fechas import hoy_bogota_str


def registrar_posponer_hoy(tarea_id: str) -> int:
    """
    Registra que el usuario pospuso esta tarea para "más tarde hoy"
    (sin tocar TickTick ni su dueDate). Usa upsert atómico: si ya se
    había pospuesto hoy, incrementa el contador en vez de duplicar fila.

    Devuelve cuántas veces se ha pospuesto la tarea hoy (incluyendo
    esta vez). Ese número lo usa scoring_service para decidir cuánta
    penalización aplicar.
    """

    hoy = hoy_bogota_str()
    ahora = datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S")

    try:
        with db_connection() as conn:
            cursor = execute(
                conn,
                """
                INSERT INTO pospuestas_hoy (tarea_id, fecha, veces, ultima_vez)
                VALUES (?, ?, 1, ?)
                ON CONFLICT (tarea_id, fecha) DO UPDATE SET
                    veces = pospuestas_hoy.veces + 1,
                    ultima_vez = excluded.ultima_vez
                RETURNING veces
                """,
                (tarea_id, hoy, ahora),
            )

            fila = cursor.fetchone()

            return fila[0] if fila else 1

    except Exception:
        logging.exception("Error registrando posponer-hoy")
        return 1


def obtener_penalizaciones_hoy() -> dict:
    """
    Devuelve {tarea_id: veces} de todas las tareas pospuestas "para más
    tarde hoy" en el día de hoy (Bogotá). Se consulta UNA vez por
    request a /api/enfoque y el resultado se le pasa a cada cálculo de
    score, en vez de hacer una query por tarea.
    """

    hoy = hoy_bogota_str()

    try:
        with db_connection() as conn:
            filas = fetch_all(
                conn,
                "SELECT tarea_id, veces FROM pospuestas_hoy WHERE fecha = ?",
                (hoy,),
            )

            return {
                fila["tarea_id"]: fila["veces"]
                for fila in filas
            }

    except Exception:
        logging.exception("Error obteniendo penalizaciones de posponer-hoy")
        return {}