from fastapi import HTTPException

from db import db_connection
from repositories.db_repository import fetch_all


def obtener_historial_service():
    """
    Devuelve el historial completo de interacciones,
    ordenado desde la más reciente.
    """

    try:

        with db_connection() as conn:

            # NOTA (migración): antes esto usaba cursor.fetchall() crudo,
            # que en SQLite sin row_factory devolvía tuplas (arrays en el
            # JSON de respuesta). Usamos fetch_all() para que la respuesta
            # sea una lista de objetos con nombre de columna, igual en
            # SQLite y en Postgres. Este endpoint es solo de depuración y
            # no está consumido por el frontend actual, así que este
            # cambio de forma en el JSON es seguro.
            filas = fetch_all(conn, """
                SELECT *
                FROM interacciones
                ORDER BY timestamp DESC
            """)

        return {
            "total": len(filas),
            "registros": filas,
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Error al leer la base de datos: {str(e)}",
        )