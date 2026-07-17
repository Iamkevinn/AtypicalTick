# services/estadisticas_service.py

import logging
from datetime import datetime

from config import BOGOTA
from db import db_connection
from utils.fechas import hace_n_dias_bogota, hoy_bogota_str


def calcular_dias_ausente():
    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT timestamp
                FROM interacciones
                WHERE accion != 'omitida_auto'
                ORDER BY timestamp DESC
                LIMIT 1
            """)

            ultima = cursor.fetchone()

        if ultima:
            fecha_ultima = datetime.strptime(
                ultima[0],
                "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=BOGOTA)

            dias = (
                datetime.now(BOGOTA) - fecha_ultima
            ).days

            return max(0, dias)

        return 0

    except Exception as e:
        logging.exception(
            "Error calculando dias ausente: %s",
            e
        )
        return 0


def contar_intentos_hoy():
    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*)
                FROM interacciones
                WHERE accion IN (
                    'intento',
                    'afronto_ansiedad',
                    'completada',
                    'paso1_comprometido',
                    'exposicion_mirar'
                )
                AND date(timestamp) = ?
            """, (hoy_bogota_str(),))

            return cursor.fetchone()[0]

    except Exception as e:
        logging.exception(
            "Error contando intentos de hoy: %s",
            e
        )
        return 0