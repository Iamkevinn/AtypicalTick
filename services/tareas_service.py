# tareas_service.py
from core.prediccion_vs_resultado import (
    cerrar_prediccion_con_resultado,
)

from db.interacciones import registrar_interaccion

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
    es_recurrente = completar_tarea_y_obtener_recurrencia(
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

    return {
        "estado": "exito",
        "es_recurrente": es_recurrente,
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