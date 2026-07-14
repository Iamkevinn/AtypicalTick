# sesiones_service.py
import logging
from datetime import datetime

from config import BOGOTA
from db import db_connection

from core.prediccion_vs_resultado import cerrar_prediccion_con_resultado


def registrar_resultado_posponer(
    tarea_id: str,
    motivo_posponer: str,
    bloqueo_previo: str,
    intervencion_usada: str,
    energia: str,
    carpeta: str,
    accion_historial: str,
):
    resultado_sesion = (
        "avance_parcial"
        if "Avance Parcial" in motivo_posponer
        else "abandono_consciente"
    )

    cerrar_prediccion_con_resultado(
        tarea_id,
        resultado_sesion
        if accion_historial != "perdonada"
        else "completada",
    )

    registrar_sesion(
        tarea_id=tarea_id,
        bloqueo_inicial=bloqueo_previo,
        intervencion_usada=intervencion_usada,
        resultado_final=resultado_sesion,
        energia=energia,
        carpeta=carpeta,
    )

def registrar_sesion(
    tarea_id: str,
    bloqueo_inicial: str,
    intervencion_usada: str,
    resultado_final: str,
    energia: str,
    carpeta: str,
):
    """
    Guarda una sesión de trabajo sobre una tarea.
    """

    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO sesiones_tarea (
                    tarea_id,
                    bloqueo_inicial,
                    intervencion_usada,
                    resultado_final,
                    energia,
                    carpeta,
                    timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tarea_id,
                    bloqueo_inicial,
                    intervencion_usada,
                    resultado_final,
                    energia,
                    carpeta,
                    datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )

    except Exception as e:
        logging.exception(
            "Error registrando sesión: %s",
            e,
        )

