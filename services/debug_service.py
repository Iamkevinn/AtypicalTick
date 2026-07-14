from db import db_connection


def obtener_sesiones_debug_service():
    """
    Devuelve las sesiones registradas.
    Endpoint utilizado únicamente para depuración.
    """

    with db_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                bloqueo_inicial,
                intervencion_usada,
                resultado_final,
                energia
            FROM sesiones_tarea
        """)

        sesiones = cursor.fetchall()

    return {
        "sesiones_registradas": sesiones,
    }