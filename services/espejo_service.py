# services/espejo_service.py

import logging

from fastapi import HTTPException

from core.espejo_analisis import (
    calcular_bloqueos_atravesados,
    construir_insight_profundo,
    detectar_patron,
)
from db import db_connection

from utils.fechas import (
    hace_n_dias_bogota,
)

from services.estadisticas_service import (
    calcular_dias_ausente,
)

from core.espejo_metricas import (
    calcular_aproximaciones,
    calcular_latencia_activacion,
    calcular_desglose_aproximaciones,
    construir_anti_patron,
    construir_evidencia_retorno,
)

from core.siguiente_experimento import (
    generar_siguiente_experimento,
)

from core.prediccion_vs_resultado import (
    obtener_contrastes_recientes,
)

from core.evidencia_acumulada import (
    obtener_evidencia_acumulada,
)

def _obtener_datos_espejo():
    """
    Consulta toda la información necesaria de la base de datos
    para construir el Espejo Conductual.
    """

    with db_connection() as conn:

        cursor = conn.cursor()

        hace_7_dias = hace_n_dias_bogota(7)

        cursor.execute("""
            SELECT accion, COUNT(*)
            FROM interacciones
            WHERE timestamp >= ?
            GROUP BY accion
        """, (hace_7_dias,))

        acciones = dict(cursor.fetchall())

        cursor.execute("""
            SELECT COUNT(DISTINCT tarea_id)
            FROM interacciones
            WHERE accion IN (
                'completada',
                'avance_parcial',
                'paso1_realizado'
            )
            AND tarea_id IN (
                SELECT tarea_id
                FROM interacciones
                WHERE accion IN (
                    'pospuesta',
                    'rechazada',
                    'abandono_consciente'
                )
            )
        """)

        recuperaciones = cursor.fetchone()[0]

        cursor.execute("""
            SELECT tarea_id,
                   accion,
                   timestamp
            FROM interacciones
            WHERE timestamp >= ?
            ORDER BY tarea_id,
                     timestamp ASC
        """, (hace_7_dias,))

        filas_friccion = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(DISTINCT date(timestamp))
            FROM interacciones
            WHERE accion='autocuidado'
            AND timestamp>=?
        """, (hace_7_dias,))

        dias_autocuidado = cursor.fetchone()[0]

        cursor.execute("""
            SELECT carpeta,
                   COUNT(*) as total,
                   SUM(
                        CASE
                            WHEN accion IN (
                                'completada',
                                'avance_parcial',
                                'paso1_realizado'
                            )
                            THEN 1
                            ELSE 0
                        END
                   ) as exitos
            FROM interacciones
            WHERE carpeta!='Inbox'
            GROUP BY carpeta
            HAVING total>3
            ORDER BY exitos DESC
            LIMIT 1
        """)

        datos_evidencia = cursor.fetchone()

    return {
        "acciones": acciones,
        "recuperaciones": recuperaciones,
        "filas_friccion": filas_friccion,
        "dias_autocuidado": dias_autocuidado,
        "datos_evidencia": datos_evidencia,
    }


def obtener_espejo_conductual():
    """
    Construye todas las métricas e insights
    del Espejo Conductual.
    """

    try:

        datos = _obtener_datos_espejo()

        acciones = datos["acciones"]
        filas_friccion = datos["filas_friccion"]
        datos_evidencia = datos["datos_evidencia"]

        recuperaciones = datos["recuperaciones"]
        dias_autocuidado = datos["dias_autocuidado"]

        (
            aproximaciones_reales,
            transiciones_logradas,
        ) = calcular_aproximaciones(
            acciones,
        )

        bloqueos_atravesados = (
            calcular_bloqueos_atravesados(
                filas_friccion,
            )
        )

        patron_detectado = detectar_patron(
            acciones,
        )

        insight_profundo = (
            construir_insight_profundo(
                datos_evidencia,
            )
        )

        siguiente_experimento = generar_siguiente_experimento()

        contrastes_recientes = obtener_contrastes_recientes(
            limite=3,
        )

        evidencia_acumulada = obtener_evidencia_acumulada()

        latencia, tendencia_latencia = (
            calcular_latencia_activacion()
        )

        desglose = (
            calcular_desglose_aproximaciones()
        )

        anti_patron = construir_anti_patron(
            patron_detectado,
        )

        evidencia_retorno = construir_evidencia_retorno(
            insight_profundo,
            calcular_dias_ausente(),
        )

        return {
            "aproximaciones": aproximaciones_reales,
            "transiciones_logradas": transiciones_logradas,
            "recuperaciones": recuperaciones,
            "bloqueos_atravesados": bloqueos_atravesados,
            "dias_autocuidado": dias_autocuidado,
            "patron_detectado": patron_detectado,
            "anti_patron": anti_patron,
            "insight_profundo": insight_profundo,
            "evidencia_retorno": evidencia_retorno,
            "latencia": latencia,
            "tendencia_latencia": tendencia_latencia,
            "desglose": desglose,
            "siguiente_experimento": siguiente_experimento,
            "contrastes_recientes": contrastes_recientes,
            "evidencia_acumulada": evidencia_acumulada,
        }

    except Exception as e:

        logging.exception(
            "Error construyendo espejo conductual: %s",
            e,
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )