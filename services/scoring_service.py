# services/scoring_service.py

from datetime import datetime

from core.gestion_horario_estricto import (
    es_horario_estricto_recurrente,
    contar_perdidas_consecutivas_salud,
)


def calcular_peso_psicologico(
    tarea: dict,
    *,
    energia: str,
    hoy,
    necesita_calentamiento: bool,
    mapa_carpetas: dict,
    info_horario_estricto: dict,
    veces_pospuesta_hoy: int = 0,
):
    """
    Calcula el score psicológico de una tarea.

    Cuanto MENOR sea el score,
    mayor prioridad tendrá la tarea
    (porque posteriormente se ordena con sort()).
    """

    prioridad = tarea.get("priority", 0)

    dias_atraso = 0

    if "dueDate" in tarea:

        fecha = datetime.strptime(
            tarea["dueDate"][:10],
            "%Y-%m-%d",
        ).date()

        if fecha < hoy:
            dias_atraso = (hoy - fecha).days

    project_id = tarea.get(
        "projectId",
        "inbox",
    )

    carpeta = mapa_carpetas.get(
        project_id,
        "Inbox",
    )

    # Las tareas recurrentes de horario estricto
    # nunca acumulan castigo por atraso.
    if es_horario_estricto_recurrente(
        tarea,
        carpeta,
    ):
        dias_atraso = 0

    # -----------------------
    # Score base
    # -----------------------

    if energia == "alta":

        if necesita_calentamiento:

            score = (
                (prioridad * 10)
                - (dias_atraso * 5)
            )

        else:

            score = -(
                (prioridad * 10)
                + (dias_atraso * 20)
            )

    else:

        score = prioridad * 5

        if (
            dias_atraso > 0
            and prioridad == 5
        ):
            score -= 50

    # -----------------------
    # Horario estricto
    # -----------------------

    info = info_horario_estricto.get(
        tarea.get("id")
    )

    if info and info.get("activo"):

        score -= 100000

        if info.get("es_salud"):

            perdidas = contar_perdidas_consecutivas_salud(
                tarea["id"]
            )

            if perdidas >= 2:
                score -= 500

    # -----------------------
    # "Más tarde hoy"
    # -----------------------
    # No cambia dueDate ni pasa al día siguiente -- solo empuja la
    # tarea hacia el final de la cola de HOY. La penalización decae
    # con cada repetición (300, 200, 100, 50, 50, ...) para que una
    # tarea evitada varias veces en el mismo día no quede enterrada
    # para siempre -- eso sería procrastinación invisible, no manejo
    # consciente de energía.
    if veces_pospuesta_hoy > 0:
        penalizacion = max(
            300 - (veces_pospuesta_hoy - 1) * 100,
            50,
        )
        score += penalizacion

    return score