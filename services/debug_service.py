from db import db_connection
from repositories.db_repository import fetch_all


def obtener_sesiones_debug_service():
    """
    Devuelve las sesiones registradas.
    Endpoint utilizado únicamente para depuración.
    """

    with db_connection() as conn:

        # NOTA (migración): fetch_all() en vez de cursor.fetchall() crudo,
        # mismo motivo que en historial_service.py -- JSON consistente
        # entre SQLite y Postgres para un endpoint que devuelve filas tal cual.
        sesiones = fetch_all(conn, """
            SELECT
                bloqueo_inicial,
                intervencion_usada,
                resultado_final,
                energia
            FROM sesiones_tarea
        """)

    return {
        "sesiones_registradas": sesiones,
    }