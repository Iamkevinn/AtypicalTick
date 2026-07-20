# perfil_service.py
import logging

from db import db_connection
from repositories.db_repository import execute
from utils.fechas import hace_n_dias_bogota, hoy_bogota_str

from core.discrepancia_emocional import (
    PALABRAS_AGOTAMIENTO,
    PALABRAS_ANSIEDAD,
)

PALABRAS_FALTA_CLARIDAD = (
    "no entiendo",
    "me falta entender",
    "no tengo claridad",
    "no sé qué",
    "no se que",
)


def analizar_perfil_clinico(carpeta: str, etiquetas: list):
    """
    Analiza cuál es el patrón emocional predominante para una carpeta
    (o conjunto de etiquetas) durante los últimos 30 días.
    """

    try:
        with db_connection() as conn:
            etiquetas_str = (
                ",".join(etiquetas).lower()
                if etiquetas
                else "sin_etiquetas"
            )

            cursor = execute(
                conn,
                """
                SELECT emocion_motivo, COUNT(*)
                FROM interacciones
                WHERE (
                    carpeta = ?
                    OR (
                        etiquetas != ''
                        AND ? LIKE '%' || etiquetas || '%'
                    )
                )
                AND emocion_motivo IS NOT NULL
                AND timestamp >= ?
                GROUP BY emocion_motivo
                ORDER BY COUNT(*) DESC
                """,
                (
                    carpeta,
                    etiquetas_str,
                    hace_n_dias_bogota(30),
                ),
            )

            resultados = cursor.fetchall()

        if not resultados:
            return {
                "dominante": None,
                "perfil": "desconocido",
            }

        emocion_principal = resultados[0][0].lower()

        if any(
            palabra in emocion_principal
            for palabra in PALABRAS_ANSIEDAD
        ):
            perfil = "evitacion"

        elif any(
            palabra in emocion_principal
            for palabra in PALABRAS_AGOTAMIENTO
        ):
            perfil = "agotamiento"

        elif any(
            palabra in emocion_principal
            for palabra in PALABRAS_FALTA_CLARIDAD
        ):
            perfil = "falta_claridad"

        else:
            perfil = "sobrecarga"

        return {
            "dominante": emocion_principal,
            "perfil": perfil,
        }

    except Exception as e:
        logging.exception(
            "Error analizando perfil clinico: %s",
            e,
        )

        return {
            "dominante": None,
            "perfil": "desconocido",
        }


def obtener_patron_contextual(
    carpeta: str,
    dia_semana: str,
):
    """
    Devuelve la emoción predominante para esa carpeta
    en ese día de la semana.

    Si no existe historial para ese día,
    usa el historial general de la carpeta.
    """

    try:
        with db_connection() as conn:
            cursor = execute(
                conn,
                """
                SELECT emocion_motivo,
                       COUNT(*) as frec
                FROM interacciones
                WHERE carpeta = ?
                AND dia_semana = ?
                AND emocion_motivo IS NOT NULL
                AND emocion_motivo != ''
                GROUP BY emocion_motivo
                ORDER BY frec DESC
                LIMIT 1
                """,
                (
                    carpeta,
                    dia_semana,
                ),
            )

            resultado = cursor.fetchone()

            if not resultado:

                cursor = execute(
                    conn,
                    """
                    SELECT emocion_motivo,
                           COUNT(*) as frec
                    FROM interacciones
                    WHERE carpeta = ?
                    AND emocion_motivo IS NOT NULL
                    AND emocion_motivo != ''
                    GROUP BY emocion_motivo
                    ORDER BY frec DESC
                    LIMIT 1
                    """,
                    (carpeta,),
                )

                resultado = cursor.fetchone()

        return resultado[0] if resultado else None

    except Exception as e:
        logging.exception(
            "Error obteniendo patron contextual: %s",
            e,
        )

        return None
def fue_perdonada_recientemente(tarea_id: str) -> bool:
    try:
        with db_connection() as conn:
            cursor = execute(conn, """
                SELECT COUNT(*)
                FROM interacciones
                WHERE tarea_id = ?
                AND accion = 'perdonada'
                AND timestamp >= ?
            """, (
                tarea_id,
                hace_n_dias_bogota(7),
            ))

            count = cursor.fetchone()[0]

        return count > 0

    except Exception as e:
        logging.exception(
            "Error consultando perdón reciente: %s",
            e
        )
        return False
    
def contar_friccion_consecutiva(tarea_id: str):
    try:
        with db_connection() as conn:
            cursor = execute(conn, """
                SELECT accion
                FROM interacciones
                WHERE tarea_id = ?
                AND date(timestamp) = ?
                ORDER BY timestamp DESC
            """, (
                tarea_id,
                hoy_bogota_str(),
            ))

            acciones = cursor.fetchall()

        friccion = 0

        for (accion,) in acciones:

            if accion in (
                "completada",
                "avance_parcial",
                "paso1_realizado",
            ):
                break

            if accion in (
                "intento",
                "afronto_ansiedad",
                "pidio_ayuda",
                "exposicion_mirar",
                "paso1_comprometido",
            ):
                friccion += 1

        return friccion

    except Exception as e:
        logging.exception(
            "Error contando friccion consecutiva: %s",
            e
        )
        return 0