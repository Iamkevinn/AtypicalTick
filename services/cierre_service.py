# cierre_service.py
from datetime import datetime

from config import BOGOTA
from services.ticktick_service import (
    obtener_listas,
    obtener_mapa_carpetas,
    obtener_tareas_proyecto,
)


def obtener_tareas_cierre():
    """
    Obtiene las tareas que deben aparecer en la pantalla
    de cierre diario.

    Incluye:
    - tareas de hoy
    - tareas atrasadas con prioridad
    """

    listas = obtener_listas()
    mapa_carpetas = obtener_mapa_carpetas(listas)

    hoy = datetime.now(BOGOTA).date()

    tareas_cierre = []

    for lista in listas:

        if lista.get("closed") or lista.get("isClosed"):
            continue

        nombre = lista.get("name", "").lower()

        if nombre in (
            "archivado",
            "archived",
            "trash",
        ):
            continue

        tareas = obtener_tareas_proyecto(
            lista["id"]
        )

        for tarea in tareas:

            if tarea.get("status", 0) != 0:
                continue

            due_date = tarea.get("dueDate")

            if not due_date:
                continue

            try:
                fecha = datetime.strptime(
                    due_date[:10],
                    "%Y-%m-%d",
                ).date()
            except ValueError:
                continue

            es_hoy = fecha == hoy

            es_atrasada_importante = (
                fecha < hoy
                and tarea.get("priority", 0) > 0
            )

            if not (
                es_hoy
                or es_atrasada_importante
            ):
                continue

            project_id = tarea.get(
                "projectId",
                "inbox",
            )

            tareas_cierre.append(
                {
                    "id": tarea["id"],
                    "titulo": tarea["title"],
                    "proyecto_id": project_id,
                    "carpeta": mapa_carpetas.get(
                        project_id,
                        "Inbox",
                    ),
                    "es_atrasada": fecha < hoy,
                    "es_rutina": bool(
                        tarea.get("repeatFlag")
                    ),
                }
            )

    tareas_cierre.sort(
        key=lambda t: (
            t["es_atrasada"],
            t["titulo"].lower(),
        )
    )

    return tareas_cierre[:5]