# services/filtros_enfoque.py

import re

from datetime import datetime

from config import BOGOTA

from core.clasificacion_tareas import (
    clasificar_tarea,
    calcular_ventana_visibilidad,
    necesita_confirmacion_unica,
)

from core.gestion_horario_estricto import (
    _es_critica_salud,
)

from core.correccion_decisiones import (
    clasificacion_ya_fue_preguntada,
    clasificacion_fue_rechazada,
)


def parsear_fecha_ticktick(fecha: str):
    """
    Convierte una fecha de TickTick a datetime.
    """

    if not fecha:
        return None

    try:
        fecha = re.sub(r"\.\d+", "", fecha)
        return datetime.strptime(
            fecha,
            "%Y-%m-%dT%H:%M:%S%z",
        )
    except Exception:
        return None


def filtrar_tareas_visibles(
    tareas,
    mapa_carpetas,
    energia,
):
    """
    Filtra únicamente las tareas que deberían mostrarse
    en la pantalla de enfoque.

    También devuelve la información necesaria sobre
    horario estricto para el cálculo posterior del score.
    """

    ahora = datetime.now(BOGOTA)
    hoy = ahora.date()

    tareas_validas = []
    info_horario_estricto = {}

    for tarea in tareas:

        if tarea.get("status", 0) != 0:
            continue

        project_id = tarea.get("projectId", "inbox")
        carpeta = mapa_carpetas.get(
            project_id,
            "Inbox",
        )

        es_recurrente = bool(
            tarea.get("repeatFlag")
        )

        restricciones = clasificar_tarea(
            titulo=tarea.get("title", ""),
            etiquetas=tarea.get("tags", []),
            carpeta=carpeta,
            tiene_hora_especifica=not tarea.get(
                "isAllDay",
                True,
            ),
        )

        # Si el usuario ya nos dijo que esta inferencia estaba mal para
        # esta tarea puntual (respondió "No" a "¿Detectamos que...?"),
        # dejamos de tratarla como horario/contexto estricto. Sin esto,
        # la pregunta de confirmación no tendría ningún efecto real.
        if restricciones.get("fuente") in ("inferido_fuerte", "inferido_debil") and clasificacion_fue_rechazada(tarea["id"]):
            restricciones["hora_importa"] = False
            restricciones["contexto_importa"] = False

        es_horario_estricto = bool(
            restricciones.get("hora_importa")
            and not restricciones.get("ventana")
        )

        if (
            es_horario_estricto
            and not tarea.get("isAllDay", True)
            and "dueDate" in tarea
        ):

            hora_programada = parsear_fecha_ticktick(
                tarea["dueDate"]
            )

            if hora_programada:

                es_salud = _es_critica_salud(
                    tarea,
                    carpeta,
                )

                ventana = calcular_ventana_visibilidad(
                    restricciones=restricciones,
                    es_recurrente=es_recurrente,
                    hora_programada=hora_programada,
                    reminders=tarea.get("reminders"),
                    ahora=ahora,
                    es_critica_salud=es_salud,
                )

                info_horario_estricto[
                    tarea["id"]
                ] = {
                    "activo": ventana[
                        "es_horario_estricto_activo"
                    ],
                    "es_salud": es_salud,
                }

                if not ventana["visible"]:
                    continue

        tiene_fecha = "dueDate" in tarea
        mostrar_ahora = True
        es_hoy_o_atrasada = False

        if tiene_fecha:

            fecha_str = tarea["dueDate"]

            fecha_tarea = datetime.strptime(
                fecha_str[:10],
                "%Y-%m-%d",
            ).date()

            if fecha_tarea <= hoy:

                es_hoy_o_atrasada = True

                if (
                    not tarea.get("isAllDay", True)
                    and tarea["id"]
                    not in info_horario_estricto
                ):

                    hora_tarea = parsear_fecha_ticktick(
                        fecha_str
                    )

                    # Antes esto usaba un umbral fijo de 3600s (1h) sin
                    # importar el tipo de tarea. Usamos el margen_minutos
                    # real que ya calculó clasificar_tarea() arriba (90
                    # min para tags explícitos, 60 para inferencia
                    # fuerte, 180 para inferencia débil, 120 por
                    # default) -- así una tarea con margen de 180 min no
                    # queda oculta hasta que falte 1h, contradiciendo su
                    # propia clasificación.
                    margen_segundos = (
                        restricciones.get(
                            "margen_minutos",
                            120,
                        )
                        * 60
                    )

                    if (
                        hora_tarea
                        and hora_tarea.timestamp()
                        > ahora.timestamp() + margen_segundos
                    ):
                        mostrar_ahora = False

        if (
            (not es_hoy_o_atrasada and tiene_fecha)
            or not mostrar_ahora
        ):
            continue

        if energia == "baja":

            tags_lower = [
                t.lower()
                for t in tarea.get("tags", [])
            ]

            carpeta_lower = carpeta.lower()

            es_vital_o_facil = (
                any(
                    palabra in tags_lower
                    for palabra in (
                        "baja-energia",
                        "energia-baja",
                        "facil",
                        "simple",
                        "rutina",
                        "medicine",
                        "medicina",
                    )
                )
                or "health" in carpeta_lower
                or "salud" in carpeta_lower
            )

            if (
                tarea.get("priority", 0) == 5
                or es_vital_o_facil
            ):
                tareas_validas.append(tarea)

        else:

            tareas_validas.append(tarea)

    info_confirmaciones = {}

    for tarea in tareas_validas:

        project_id = tarea.get("projectId", "inbox")
        carpeta = mapa_carpetas.get(project_id, "Inbox")

        restricciones = clasificar_tarea(
            titulo=tarea.get("title", ""),
            etiquetas=tarea.get("tags", []),
            carpeta=carpeta,
            tiene_hora_especifica=not tarea.get("isAllDay", True),
        )

        if not necesita_confirmacion_unica(restricciones):
            continue

        if clasificacion_ya_fue_preguntada(tarea["id"]):
            continue

        if restricciones.get("hora_importa"):
            info_confirmaciones[tarea["id"]] = {
                "tipo": "hora_fija",
                "pregunta": "Detectamos que esta tarea tiene una hora fija. ¿Es correcto?",
                "valor_detectado": "hora_fija",
            }
        elif restricciones.get("contexto_importa"):
            info_confirmaciones[tarea["id"]] = {
                "tipo": "contexto",
                "pregunta": (
                    "Detectamos que esta tarea es parte de tu rutina de "
                    f"{restricciones.get('contexto_ideal')}. ¿Es correcto?"
                ),
                "valor_detectado": restricciones.get("contexto_ideal"),
            }

    return (
        tareas_validas,
        info_horario_estricto,
        info_confirmaciones,
    )