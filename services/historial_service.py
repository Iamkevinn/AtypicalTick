from fastapi import HTTPException

from db import db_connection


def obtener_historial_service():
    """
    Devuelve el historial completo de interacciones,
    ordenado desde la más reciente.
    """

    try:

        with db_connection() as conn:

            cursor = conn.cursor()

            cursor.execute("""
                SELECT *
                FROM interacciones
                ORDER BY timestamp DESC
            """)

            filas = cursor.fetchall()

        return {
            "total": len(filas),
            "registros": filas,
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Error al leer la base de datos: {str(e)}",
        )