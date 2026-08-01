# services/microhabitos_service.py
from datetime import datetime, timedelta

from config import BOGOTA

from core.microhabitos import (
    ACCIONES_VALIDAS,
    CATEGORIAS,
    elegir_categoria_pendiente,
)

from db.microhabitos import (
    contar_resultados_en_hora,
    marcar_categoria,
    obtener_estado,
    registrar_historial,
)


def obtener_microhabito_pendiente():
    """
    Consulta pura (sin efectos secundarios): le dice al frontend si hay
    algún microhábito vencido en este momento. Se puede llamar tan
    seguido como se quiera (ej. cada minuto) sin registrar nada -- solo
    /api/microhabito/{categoria} (la respuesta del usuario) escribe en
    la base de datos.
    """

    ahora = datetime.now(BOGOTA)

    estados = {
        categoria: obtener_estado(categoria)
        for categoria in CATEGORIAS
    }

    categoria = elegir_categoria_pendiente(
        ahora,
        estados,
        contar_resultados_en_hora,
    )

    if not categoria:
        return {"pendiente": None}

    config = CATEGORIAS[categoria]

    return {
        "pendiente": {
            "categoria": categoria,
            "emoji": config["emoji"],
            "titulo": config["titulo"],
            "instrucciones": config["instrucciones"],
            "duracion_segundos": config["duracion_segundos"],
        }
    }


def responder_microhabito_service(categoria: str, accion: str):
    if categoria not in CATEGORIAS:
        raise ValueError(f"Categoría de microhábito desconocida: {categoria}")

    if accion not in ACCIONES_VALIDAS:
        raise ValueError(f"Acción de microhábito desconocida: {accion}")

    registrar_historial(categoria, accion)

    if accion == "pospuesto":
        marcar_categoria(
            categoria,
            tocar_ultima_vez=False,
            snooze_hasta=datetime.now(BOGOTA) + timedelta(minutes=5),
        )
    else:
        marcar_categoria(categoria, tocar_ultima_vez=True)

    return {"estado": "exito"}