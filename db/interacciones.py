# interacciones.py
import logging
from datetime import datetime

from config import BOGOTA
from repositories.db_repository import db_connection, execute


DIAS_SEMANA = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)


def registrar_interaccion(
    tarea_id, tarea_nombre, energia, accion, emocion, carpeta,
    etiquetas=None,
    metadata_ia=None,
):
    try:
        ahora = datetime.now(BOGOTA)

        with db_connection() as conn:
            execute(
                conn,
                """
                INSERT INTO interacciones (
                    tarea_id,
                    tarea_nombre,
                    energia,
                    emocion_motivo,
                    accion,
                    hora,
                    dia_semana,
                    carpeta,
                    etiquetas,
                    metadata_ia,
                    timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tarea_id,
                    tarea_nombre,
                    energia,
                    emocion,
                    accion,
                    ahora.hour,
                    DIAS_SEMANA[ahora.weekday()],
                    carpeta,
                    etiquetas,
                    metadata_ia,
                    ahora.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )

    except Exception:
        logging.exception("Error al guardar interacción")