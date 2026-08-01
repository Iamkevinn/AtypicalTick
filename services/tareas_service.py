# tareas_service.py
import json
from datetime import datetime

from config import BOGOTA

from core.prediccion_vs_resultado import (
    cerrar_prediccion_con_resultado,
)

from core.clasificacion_tareas import (
    clasificar_tarea,
    requiere_chequeo_de_fidelidad,
)

from services.filtros_enfoque import parsear_fecha_ticktick

from db.interacciones import registrar_interaccion
from db.pospuestas_hoy import registrar_posponer_hoy

from services.sesiones_service import registrar_sesion, registrar_resultado_posponer

from services.ticktick_service import (
    completar_tarea,
    completar_tarea_y_obtener_recurrencia,
    obtener_tarea,
    posponer_para_manana,
    es_tarea_recurrente,
)

from services.criticidad_service import es_tarea_critica

def liberar_tarea_service(
    proyecto_id: str,
    tarea_id: str,
    tarea_nombre: str,
    energia: str,
    carpeta: str,
    bloqueo_previo: str,
    intervencion_usada: str,
):
    es_recurrente, tarea = completar_tarea_y_obtener_recurrencia(
        proyecto_id,
        tarea_id,
    )

    registrar_interaccion(
        tarea_id=tarea_id,
        tarea_nombre=tarea_nombre,
        energia=energia,
        accion="completada",
        emocion=None,
        carpeta=carpeta,
    )

    cerrar_prediccion_con_resultado(
        tarea_id,
        "completada",
    )

    registrar_sesion(
        tarea_id=tarea_id,
        bloqueo_inicial=bloqueo_previo,
        intervencion_usada=intervencion_usada,
        resultado_final="completada",
        energia=energia,
        carpeta=carpeta,
    )

    chequeo_fidelidad = None

    if tarea and "dueDate" in tarea:

        restricciones = clasificar_tarea(
            titulo=tarea.get("title", ""),
            etiquetas=tarea.get("tags", []),
            carpeta=carpeta,
            tiene_hora_especifica=not tarea.get("isAllDay", True),
        )

        hora_esperada = parsear_fecha_ticktick(tarea["dueDate"])

        if requiere_chequeo_de_fidelidad(
            restricciones,
            datetime.now(BOGOTA),
            hora_esperada,
        ):
            chequeo_fidelidad = {
                "pregunta": "¿Fue en el momento correcto?",
            }

    return {
        "estado": "exito",
        "es_recurrente": es_recurrente,
        "chequeo_fidelidad": chequeo_fidelidad,
    }


def posponer_tarea_service(
    proyecto_id: str,
    tarea_id: str,
    datos,
):
    es_recurrente, tarea = es_tarea_recurrente(
        proyecto_id,
        tarea_id,
    )

    es_critica = es_tarea_critica(
        tarea,
        datos.carpeta,
        datos.tarea_nombre,
    )

    accion_historial = "pospuesta"

    if es_recurrente and not es_critica:

        completar_tarea(
            proyecto_id,
            tarea_id,
        )

        accion_historial = "perdonada"

    else:

        posponer_para_manana(
            proyecto_id,
            tarea,
        )

    registrar_interaccion(
        tarea_id=tarea_id,
        tarea_nombre=datos.tarea_nombre,
        energia=datos.energia,
        accion=accion_historial,
        emocion=datos.motivo_posponer,
        carpeta=datos.carpeta,
    )

    registrar_resultado_posponer(
        tarea_id=tarea_id,
        motivo_posponer=datos.motivo_posponer,
        bloqueo_previo=datos.bloqueo_previo,
        intervencion_usada=datos.intervencion_usada,
        energia=datos.energia,
        carpeta=datos.carpeta,
        accion_historial=accion_historial,
    )

    return {
        "estado": "exito",
    }


def avance_parcial_service(
    proyecto_id: str,
    tarea_id: str,
    datos,
):
    """
    Estado intermedio entre "no hice nada" y "la completé": el usuario
    avanzó una parte real de la tarea y quiere dejar el resto para
    mañana. A diferencia de posponer_tarea_service, aquí NO se evalúa
    si la tarea es recurrente para "perdonarla" -- hubo trabajo real,
    así que siempre se reprograma conservando la hora, nunca se marca
    como completada de forma artificial.
    """

    tarea = obtener_tarea(
        proyecto_id,
        tarea_id,
    )

    posponer_para_manana(
        proyecto_id,
        tarea,
    )

    metadata_ia = json.dumps({
        "tipo": "avance_parcial",
        "restante": datos.restante,
        "estimado_restante_minutos": datos.estimado_restante_minutos,
    })

    registrar_interaccion(
        tarea_id=tarea_id,
        tarea_nombre=datos.tarea_nombre,
        energia=datos.energia,
        accion="avance_parcial",
        emocion=None,
        carpeta=datos.carpeta,
        metadata_ia=metadata_ia,
    )

    cerrar_prediccion_con_resultado(
        tarea_id,
        "avance_parcial",
    )

    registrar_sesion(
        tarea_id=tarea_id,
        bloqueo_inicial=datos.bloqueo_previo,
        intervencion_usada=datos.intervencion_usada,
        resultado_final="avance_parcial",
        energia=datos.energia,
        carpeta=datos.carpeta,
    )

    return {
        "estado": "exito",
    }


def posponer_hoy_service(
    tarea_id: str,
    datos,
):
    """
    "Más tarde hoy": NO cambia dueDate ni toca TickTick. Solo empuja la
    tarea al final de la cola de hoy vía una penalización temporal en
    scoring_service (ver db/pospuestas_hoy.py). Psicológicamente es
    distinto a "posponer" -- la tarea sigue siendo de hoy, el usuario
    solo está gestionando el orden, no evitando el día completo.
    """

    veces_hoy = registrar_posponer_hoy(tarea_id)

    registrar_interaccion(
        tarea_id=tarea_id,
        tarea_nombre=datos.tarea_nombre,
        energia=datos.energia,
        accion="pospuesto_hoy",
        emocion=None,
        carpeta=datos.carpeta,
        metadata_ia=json.dumps({
            "tipo": "pospuesto_hoy",
            "veces_hoy": veces_hoy,
        }),
    )

    return {
        "estado": "exito",
        "veces_hoy": veces_hoy,
    }


def completar_retroactivo_service(
    proyecto_id: str,
    tarea_id: str,
    tarea_nombre: str,
    carpeta: str,
):
    completar_tarea(
        proyecto_id,
        tarea_id,
    )

    registrar_interaccion(
        tarea_id=tarea_id,
        tarea_nombre=tarea_nombre,
        energia="desconocida",
        accion="completada_fuera_app",
        emocion="Cierre Diario",
        carpeta=carpeta,
    )

    cerrar_prediccion_con_resultado(
        tarea_id,
        "completada_fuera_app",
    )

    return {
        "estado": "exito",
    }


def posponer_cierre_service(
    proyecto_id: str,
    tarea_id: str,
    tarea_nombre: str,
    carpeta: str,
):
    tarea = obtener_tarea(
        proyecto_id,
        tarea_id,
    )

    posponer_para_manana(
        proyecto_id,
        tarea,
    )

    registrar_interaccion(
        tarea_id=tarea_id,
        tarea_nombre=tarea_nombre,
        energia="desconocida",
        accion="pospuesta_cierre",
        emocion="Sinceridad Nocturna",
        carpeta=carpeta,
    )

    return {
        "estado": "exito",
    }

def olvido_cierre_service(
    proyecto_id: str,
    tarea_id: str,
    tarea_nombre: str,
    carpeta: str,
):
    """
    El usuario no recuerda si realizó la tarea.
    Se reprograma para mañana y se registra el evento.
    """

    tarea = obtener_tarea(
        proyecto_id,
        tarea_id,
    )

    posponer_para_manana(
        proyecto_id,
        tarea,
    )

    registrar_interaccion(
        tarea_id=tarea_id,
        tarea_nombre=tarea_nombre,
        energia="desconocida",
        accion="no_recuerda",
        emocion="Cierre Diario",
        carpeta=carpeta,
    )

    return {
        "estado": "exito",
    }