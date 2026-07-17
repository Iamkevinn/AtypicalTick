# ticktick_service.py
import logging
import requests

from fastapi import HTTPException

from datetime import datetime, timedelta

from config import BOGOTA

from services.auth_ticktick import obtener_token


BASE_URL = "https://api.ticktick.com/open/v1"


def obtener_headers(content_type: bool = False):
    """
    Devuelve los headers autenticados para la API de TickTick.
    """

    token = obtener_token()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="No hay token de acceso."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    if content_type:
        headers["Content-Type"] = "application/json"

    return headers


def obtener_listas():
    """
    Obtiene todos los proyectos/listas del usuario.
    """

    try:
        respuesta = requests.get(
            f"{BASE_URL}/project",
            headers=obtener_headers(),
            timeout=10,
        )

        respuesta.raise_for_status()

        return respuesta.json()

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=503,
            detail="TickTick tardó demasiado en responder.",
        )

    except requests.exceptions.RequestException as e:
        logging.exception(
            "Error obteniendo listas: %s",
            e,
        )

        raise HTTPException(
            status_code=503,
            detail="Error comunicándose con TickTick.",
        )


def obtener_tareas_proyecto(project_id: str):
    """
    Obtiene todas las tareas de un proyecto.
    """

    try:
        respuesta = requests.get(
            f"{BASE_URL}/project/{project_id}/data",
            headers=obtener_headers(),
            timeout=10,
        )

        respuesta.raise_for_status()

        return respuesta.json().get("tasks", [])

    except requests.exceptions.Timeout:
        logging.warning(
            "Timeout obteniendo tareas del proyecto %s",
            project_id,
        )

        return []

    except requests.exceptions.RequestException as e:
        logging.exception(
            "Error obteniendo tareas: %s",
            e,
        )

        return []


def obtener_tarea(project_id: str, task_id: str):
    """
    Obtiene una tarea específica.
    """

    try:
        respuesta = requests.get(
            f"{BASE_URL}/project/{project_id}/task/{task_id}",
            headers=obtener_headers(),
            timeout=10,
        )

        respuesta.raise_for_status()

        return respuesta.json()

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=503,
            detail="TickTick tardó demasiado en responder.",
        )

    except requests.exceptions.RequestException as e:
        logging.exception(
            "Error obteniendo tarea: %s",
            e,
        )

        raise HTTPException(
            status_code=503,
            detail="No fue posible obtener la tarea.",
        )


def actualizar_tarea(
    project_id: str,
    task: dict,
):
    """
    Actualiza una tarea existente.
    """

    try:
        respuesta = requests.post(
            f"{BASE_URL}/project/{project_id}/task/{task['id']}",
            headers=obtener_headers(content_type=True),
            json=task,
            timeout=10,
        )

        respuesta.raise_for_status()

        return respuesta.json()

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=503,
            detail="TickTick tardó demasiado en responder.",
        )

    except requests.exceptions.RequestException as e:
        logging.exception(
            "Error actualizando tarea: %s",
            e,
        )

        raise HTTPException(
            status_code=503,
            detail="No fue posible actualizar la tarea.",
        )


def completar_tarea(
    project_id: str,
    task_id: str,
):
    """
    Marca una tarea como completada.
    """

    try:
        respuesta = requests.post(
            f"{BASE_URL}/project/{project_id}/task/{task_id}/complete",
            headers=obtener_headers(),
            timeout=10,
        )

        respuesta.raise_for_status()

        return True

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=503,
            detail="TickTick tardó demasiado en responder.",
        )

    except requests.exceptions.RequestException as e:
        logging.exception(
            "Error completando tarea: %s",
            e,
        )

        raise HTTPException(
            status_code=503,
            detail="No fue posible completar la tarea.",
        )


def crear_tarea(
    titulo: str,
):
    """
    Crea una tarea en el Inbox.
    """

    try:
        respuesta = requests.post(
            f"{BASE_URL}/task",
            headers=obtener_headers(content_type=True),
            json={
                "title": titulo,
            },
            timeout=10,
        )

        respuesta.raise_for_status()

        return respuesta.json()

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=503,
            detail="TickTick tardó demasiado en responder.",
        )

    except requests.exceptions.RequestException as e:
        logging.exception(
            "Error creando tarea: %s",
            e,
        )

        raise HTTPException(
            status_code=503,
            detail="No fue posible crear la tarea.",
        )
    
def obtener_mapa_carpetas(listas):
    mapa = {
        lista["id"]: lista["name"]
        for lista in listas
    }

    mapa["inbox"] = "Inbox"

    return mapa

def obtener_todas_las_tareas(listas):
    """
    Obtiene todas las tareas abiertas de todas las listas activas.
    """

    tareas = []

    for lista in listas:
        if lista.get("closed") or lista.get("isClosed"):
            continue

        nombre = lista.get("name", "").lower()

        if nombre in (
            "archivado",
            "archived",
            "archived lists",
            "trash",
        ):
            continue

        tareas.extend(
            obtener_tareas_proyecto(lista["id"])
        )

    return tareas

def reprogramar_para_hoy(
    project_id: str,
    task_id: str,
):
    """
    Reprograma una tarea para el día de hoy conservando la hora original
    cuando existe.
    """

    from datetime import datetime

    from config import BOGOTA

    tarea = obtener_tarea(project_id, task_id)

    hoy = datetime.now(BOGOTA).date()

    tarea["status"] = 0

    if "dueDate" in tarea:
        if tarea.get("isAllDay", True):
            tarea["dueDate"] = (
                hoy.strftime("%Y-%m-%dT12:00:00+0000")
            )
        else:
            hora_original = tarea["dueDate"][10:]
            tarea["dueDate"] = (
                hoy.strftime("%Y-%m-%d") + hora_original
            )
    else:
        tarea["dueDate"] = (
            hoy.strftime("%Y-%m-%dT12:00:00+0000")
        )

    actualizar_tarea(project_id, tarea)

    return tarea

def completar_tarea_y_obtener_recurrencia(
    project_id: str,
    task_id: str,
):
    """
    Completa una tarea en TickTick y devuelve si era recurrente,
    junto con la tarea obtenida (o None si no se pudo consultar).
    """

    es_recurrente = False
    tarea = None

    try:
        tarea = obtener_tarea(project_id, task_id)
        es_recurrente = bool(tarea.get("repeatFlag"))
    except HTTPException:
        logging.warning(
            "No se pudo obtener la tarea antes de completarla. "
            "Se asume que no era recurrente."
        )

    completar_tarea(project_id, task_id)

    return es_recurrente, tarea

def es_tarea_recurrente(project_id: str, task_id: str):
    tarea = obtener_tarea(project_id, task_id)
    return bool(tarea.get("repeatFlag")), tarea

def posponer_para_manana(project_id: str, tarea: dict):
    hoy = datetime.now(BOGOTA).date()
    manana = hoy + timedelta(days=1)

    if "dueDate" in tarea:
        if tarea.get("isAllDay", True):
            tarea["dueDate"] = manana.strftime("%Y-%m-%dT12:00:00+0000")
        else:
            hora = tarea["dueDate"][10:]
            tarea["dueDate"] = manana.strftime("%Y-%m-%d") + hora
    else:
        tarea["dueDate"] = manana.strftime("%Y-%m-%dT12:00:00+0000")

    actualizar_tarea(project_id, tarea)