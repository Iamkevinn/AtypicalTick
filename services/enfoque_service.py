# services/enfoque_service.py

from datetime import datetime

from config import BOGOTA
from db import db_connection

from services.ticktick_service import (
    obtener_listas,
    obtener_mapa_carpetas,
    obtener_todas_las_tareas,
)

from services.filtros_enfoque import filtrar_tareas_visibles
from services.scoring_service import calcular_peso_psicologico
from services.formatter_service import formatear_tareas

from services.estadisticas_service import (
    calcular_dias_ausente,
    contar_intentos_hoy,
)

from utils.fechas import hoy_bogota_str


def obtener_enfoque(
    energia: str,
):
    """
    Construye completamente la respuesta de /api/enfoque.
    """

    listas = obtener_listas()

    mapa_carpetas = obtener_mapa_carpetas(listas)

    todas_las_tareas = obtener_todas_las_tareas(listas)

    with db_connection() as conn:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM interacciones
            WHERE accion='completada'
            AND date(timestamp)=?
            """,
            (hoy_bogota_str(),),
        )

        completadas_hoy = cursor.fetchone()[0]

    necesita_calentamiento = completadas_hoy == 0

    ahora = datetime.now(BOGOTA)

    tareas_validas, info_horario_estricto, info_confirmaciones = filtrar_tareas_visibles(
        tareas=todas_las_tareas,
        mapa_carpetas=mapa_carpetas,
        energia=energia,
    )

    dias_ausente = calcular_dias_ausente()

    if dias_ausente > 7:

        hoy = ahora.date()

        def muy_atrasada(t):

            if "dueDate" not in t:
                return False

            fecha = datetime.strptime(
                t["dueDate"][:10],
                "%Y-%m-%d",
            ).date()

            return (hoy - fecha).days > 7

        atrasadas = [
            t for t in tareas_validas
            if muy_atrasada(t)
        ]

        recientes = [
            t for t in tareas_validas
            if not muy_atrasada(t)
        ]

        atrasadas.sort(
            key=lambda t: t.get("priority", 0),
            reverse=True,
        )

        tareas_validas = recientes + atrasadas[:1]

    tareas_validas.sort(
        key=lambda t: calcular_peso_psicologico(
            tarea=t,
            energia=energia,
            hoy=ahora.date(),
            necesita_calentamiento=necesita_calentamiento,
            mapa_carpetas=mapa_carpetas,
            info_horario_estricto=info_horario_estricto,
        )
    )

    intentos_hoy = contar_intentos_hoy()

    if not tareas_validas:

        return {
            "estado": "vacio",
            "mensaje": "Bandeja limpia por ahora!",
            "dias_ausente": dias_ausente,
        }

    tareas = formatear_tareas(
        tareas_validas,
        mapa_carpetas,
        ahora,
        info_horario_estricto,
        info_confirmaciones,
    )

    return {
        "estado": "enfoque",
        "tareas": tareas,
        "fase": (
            "calentamiento"
            if necesita_calentamiento
            else "trabajo_profundo"
        ),
        "estadisticas": {
            "dias_ausente": dias_ausente,
            "intentos_hoy": intentos_hoy,
        },
    }