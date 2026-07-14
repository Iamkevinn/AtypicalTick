import logging

from db import db_connection


def obtener_metricas_clinicas_service():
    """
    Obtiene las métricas clínicas principales
    mostradas en el panel del usuario.
    """

    try:

        with db_connection() as conn:

            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*)
                FROM sesiones_tarea
                WHERE bloqueo_inicial != 'Ninguno'
                AND resultado_final IN (
                    'completada',
                    'avance_parcial'
                )
            """)

            recuperaciones_exitosas = cursor.fetchone()[0]

        return {
            "recuperaciones_exitosas": recuperaciones_exitosas,
            "mensaje": (
                f"Has superado {recuperaciones_exitosas} bloqueos "
                "que parecían imposibles. Tu historial demuestra "
                "que los bloqueos no son permanentes."
                if recuperaciones_exitosas > 0
                else ""
            ),
        }

    except Exception as e:

        logging.exception(
            "Error obteniendo métricas clínicas: %s",
            e,
        )

        return {
            "error": str(e),
        }