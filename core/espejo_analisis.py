# core/espejo_analisis.py

from datetime import (
    datetime,
    timedelta,
)

def calcular_bloqueos_atravesados(
    filas_friccion,
):
    """
    Cuenta cuántas veces el usuario logró completar
    una tarea tras haber mostrado previamente señales
    de fricción el mismo día.
    """

    bloqueos_atravesados = 0

    friccion_previa = {}

    for tarea_id, accion, ts_str in filas_friccion:

        try:

            ts = datetime.strptime(
                ts_str,
                "%Y-%m-%d %H:%M:%S",
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        if accion in (
            "intento",
            "afronto_ansiedad",
            "pidio_ayuda",
            "exposicion_mirar",
            "paso1_comprometido",
        ):

            friccion_previa[tarea_id] = ts

        elif accion in (
            "completada",
            "avance_parcial",
            "paso1_realizado",
        ):

            inicio = friccion_previa.get(
                tarea_id
            )

            if (
                inicio
                and ts.date() == inicio.date()
                and (ts - inicio)
                <= timedelta(hours=8)
            ):

                bloqueos_atravesados += 1

            friccion_previa.pop(
                tarea_id,
                None,
            )

    return bloqueos_atravesados


def detectar_patron(
    acciones,
):
    """
    Detecta el principal patrón conductual observado
    durante la última semana.
    """

    pospuestas = (
        acciones.get("pospuesta", 0)
        + acciones.get("rechazada", 0)
    )

    completadas = acciones.get(
        "completada",
        0,
    )

    ayudas_ia = acciones.get(
        "afronto_ansiedad",
        0,
    )

    if pospuestas > (completadas + 5):

        return {
            "tipo": "Ciclo de Evitacion",
            "icono": "🛡️",
            "mensaje": (
                "Los datos muestran que has pospuesto frecuentemente esta semana. "
                "Posponer alivia el malestar por unas horas, "
                "pero el costo es que la friccion reaparece mañana. "
                "Considera usar la regla de 'solo mirar 30 segundos' "
                "para romper el ciclo."
            ),
        }

    if (
        ayudas_ia > 5
        and completadas < 2
    ):

        return {
            "tipo": "Exceso de Preparacion",
            "icono": "⚖️",
            "mensaje": (
                "Has pedido mucha asistencia pero ejecutado poca accion fisica. "
                "Esto suele pasar cuando buscamos sentirnos completamente listos "
                "antes de empezar. El objetivo hoy es dar un paso imperfecto."
            ),
        }

    return None


def construir_insight_profundo(
    datos_evidencia,
):
    """
    Construye un insight basado en la evidencia histórica
    del usuario.
    """

    if not datos_evidencia:
        return None

    carpeta = datos_evidencia[0]
    total = datos_evidencia[1]
    exitos = datos_evidencia[2]

    if not total:
        return None

    tasa = round(
        (exitos / total) * 100
    )

    if tasa < 50:
        return None

    return (
        f"La sensacion de dificultad suele ser alta con las tareas de "
        f"'{carpeta}'. "
        f"Sin embargo, tu historial clinico muestra que cuando decides "
        f"dar el primer micro-paso fisico, logras avanzar o terminar "
        f"el {tasa}% de las veces."
    )