import logging

from apscheduler.schedulers.background import BackgroundScheduler

from config import SCHEDULER_INTERVAL_MINUTES
from services.auth_ticktick import obtener_token
from core.gestion_horario_estricto import procesar_horario_estricto_vencido


def _job_horario_estricto(registrar_interaccion):

    logging.debug("JOB EJECUTADO")

    token = obtener_token()

    if not token:
        logging.debug(
            "[scheduler] Sin token, se omite revision de horario estricto."
        )
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    procesadas = procesar_horario_estricto_vencido(
        headers,
        {},
        registrar_interaccion
    )

    if procesadas:
        logging.info(
            "[scheduler] %s tarea(s) ciclicas marcadas como desconocidas (ocultas localmente).",
            procesadas,
        )


def iniciar_scheduler(registrar_interaccion):

    scheduler = BackgroundScheduler()

    scheduler.add_job(
        _job_horario_estricto,
        "interval",
        minutes=SCHEDULER_INTERVAL_MINUTES,
        id="horario_estricto",
        args=[registrar_interaccion],
    )

    logging.debug("INICIANDO SCHEDULER")
    logging.debug("Scheduler id: %s", id(scheduler))

    scheduler.start()

    return scheduler