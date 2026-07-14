# services/formatter_service.py

from services.perfil_service import (
    analizar_perfil_clinico,
    contar_friccion_consecutiva,
    fue_perdonada_recientemente,
    obtener_patron_contextual,
)


def formatear_tareas(
    tareas,
    mapa_carpetas,
    dia_actual,
    info_horario_estricto,
):
    """
    Convierte las tareas de TickTick al formato esperado
    por el frontend.
    """

    lista_formateada = []

    for tarea in tareas:

        project_id = tarea.get(
            "projectId",
            "inbox",
        )

        carpeta = mapa_carpetas.get(
            project_id,
            "Inbox",
        )

        etiquetas = tarea.get(
            "tags",
            [],
        )

        lista_formateada.append({

            "id": tarea["id"],

            "titulo": tarea["title"],

            "descripcion": tarea.get(
                "content",
                "",
            ),

            "proyecto_id": project_id,

            "carpeta": carpeta,

            "etiquetas": etiquetas,

            "prioridad": tarea.get(
                "priority",
                0,
            ),

            "perfil_clinico": analizar_perfil_clinico(
                carpeta,
                etiquetas,
            ),

            "friccion_consecutiva": contar_friccion_consecutiva(
                tarea["id"],
            ),

            "fue_auto_perdonada_antes": fue_perdonada_recientemente(
                tarea["id"],
            ),

            "patron_emocional": obtener_patron_contextual(
                carpeta,
                dia_actual,
            ),

            "es_horario_estricto_activo": bool(
                info_horario_estricto
                .get(tarea["id"], {})
                .get("activo")
            ),
        })

    return lista_formateada