# core/microhabitos.py
"""
Sistema de microhábitos de bienestar: intervenciones de 10-30 segundos
(ojos, articulaciones, hidratación, respiración) que NUNCA son tareas.

Principio de diseño (no negociable): estas intervenciones no generan
culpa. No aparecen en TickTick, no afectan ninguna métrica clínica de
la app, no tienen "racha rota" ni contador visible de veces ignoradas.
Simplemente aparecen, se registran internamente, y desaparecen.
"""

CATEGORIAS = {
    "vista": {
        "emoji": "👀",
        "titulo": "Descansa la vista",
        "instrucciones": "Mira algo lejano durante 20 segundos y parpadea varias veces seguidas.",
        "duracion_segundos": 20,
        "intervalo_minutos": 20,
    },
    "movilidad": {
        "emoji": "🦴",
        "titulo": "Mueve el cuerpo",
        "instrucciones": "Rota cuello, hombros y muñecas. Ponte de pie si puedes.",
        "duracion_segundos": 30,
        "intervalo_minutos": 45,
    },
    "hidratacion": {
        "emoji": "💧",
        "titulo": "Toma agua",
        "instrucciones": "Un vaso de agua, ahora mismo.",
        "duracion_segundos": 10,
        "intervalo_minutos": 60,
    },
    "regulacion": {
        "emoji": "🧠",
        "titulo": "Respira",
        "instrucciones": "Inhala 4 segundos, sostén 4, exhala 6. Repite 3 veces. Relaja mandíbula y hombros.",
        "duracion_segundos": 30,
        "intervalo_minutos": 90,
    },
}

ACCIONES_VALIDAS = ("hecho", "ignorado", "pospuesto")


def es_hora_evitada(conteos: dict) -> bool:
    """
    "Si siempre ignoras 'Mover cuello' a las 3pm, la app aprende a no
    volver a sugerirla a esa hora." Se activa solo con evidencia real
    y consistente: al menos 3 rechazos (ignorado/pospuesto) y CERO
    veces que sí se haya hecho en esa franja horaria.
    """

    negativos = conteos.get("ignorado", 0) + conteos.get("pospuesto", 0)
    return negativos >= 3 and conteos.get("hecho", 0) == 0


def elegir_categoria_pendiente(ahora, estados: dict, contador_resultados):
    """
    ahora: datetime tz-aware (Bogotá).
    estados: {categoria: {"ultima_vez": datetime|None, "snooze_hasta": datetime|None}}
    contador_resultados: función (categoria, hora) -> dict de conteos,
        inyectada así para que esta función se pueda probar sin tocar
        la base de datos.

    Devuelve el nombre de la categoría más atrasada y elegible en este
    momento, o None si ninguna está vencida todavía. Solo se sugiere
    UNA a la vez -- nunca se apilan varios recordatorios.
    """

    mejor_categoria = None
    mejor_ratio = 0.0

    for categoria, config in CATEGORIAS.items():
        estado = estados.get(categoria) or {}

        snooze_hasta = estado.get("snooze_hasta")
        if snooze_hasta and ahora < snooze_hasta:
            continue

        intervalo = config["intervalo_minutos"]
        ultima_vez = estado.get("ultima_vez")

        if ultima_vez is None:
            # Nunca se ha mostrado -- elegible desde ya, con el mismo
            # peso que si acabara de vencer su intervalo por primera vez.
            minutos_transcurridos = intervalo
        else:
            minutos_transcurridos = (ahora - ultima_vez).total_seconds() / 60

        ratio = minutos_transcurridos / intervalo

        if ratio < 1.0:
            continue

        conteos = contador_resultados(categoria, ahora.hour)

        # Se respeta el horario aprendido como "malo", a menos que ya
        # esté MUY atrasada (2x su intervalo) -- ahí el bienestar
        # físico pesa más que la señal de aprendizaje.
        if es_hora_evitada(conteos) and ratio < 2.0:
            continue

        if ratio > mejor_ratio:
            mejor_ratio = ratio
            mejor_categoria = categoria

    return mejor_categoria