# deteccion_crisis.py
# ---------------------------------------------------------
# FILTRO DE SEGURIDAD: Detección de lenguaje de crisis
# ---------------------------------------------------------
# IMPORTANTE: Esto NO es un diagnóstico ni una evaluación clínica.
# Es un filtro de palabras/frases de alto riesgo que actúa como
# "freno de mano" antes de que el texto del usuario se procese
# como un motivo de tarea normal (posponer, capturar, etc).
#
# Principio de diseño: pocos falsos negativos > pocos falsos positivos.
# Preferimos mostrar el mensaje de ayuda de más, antes que dejarlo pasar.
# Si se activa por error (ej. el usuario escribió "me quiero matar de
# la risa"), el mensaje de recursos no hace daño; omitirlo cuando
# correspondía sí puede hacerlo.

import re

# Frases que indican riesgo agudo (ideación de daño a sí mismo/suicidio).
# Deliberadamente NO incluimos aquí frases de frustración normal como
# "no puedo más", "estoy harto", "esto me supera" — esas son parte
# normal de la experiencia con TDAH/depresión y NO deben disparar esto.
# Solo frases que apuntan a daño físico, desaparecer, o terminar con la vida.
PATRONES_RIESGO_ALTO = [
    r"quiero\s+(morir|matarme|suicidarme|desaparecer\s+para\s+siempre)",
    r"quiero\s+terminar\s+con\s+(mi\s+vida|todo\s+esto\s+de\s+una\s+vez)",
    r"no\s+quiero\s+(seguir\s+viviendo|vivir\s+más|despertar)",
    r"(pensando|pienso)\s+en\s+(matarme|suicidarme|quitarme\s+la\s+vida)",
    r"ya\s+no\s+(vale|tiene\s+sentido)\s+(la\s+pena\s+)?seguir",
    r"mejor\s+(estaría|estaria)\s+muerto",
    r"acabar\s+con\s+(mi\s+vida|todo)",
    r"hacerme\s+daño",
    r"lastimarme",
    r"cortarme",
    r"\bsuicid",  # cubre suicidio, suicidarme, suicida, etc.
    r"no\s+aguanto\s+más\s+(la\s+vida|vivir|estar\s+vivo)",
]

_REGEX_COMPILADOS = [re.compile(p, re.IGNORECASE) for p in PATRONES_RIESGO_ALTO]


def detectar_riesgo(texto: str) -> bool:
    """
    Devuelve True si el texto contiene lenguaje de riesgo agudo.
    Solo evalúa texto libre proveniente del usuario (no campos de
    botones predefinidos, que ya son seguros por diseño).
    """
    if not texto or not isinstance(texto, str):
        return False

    texto_normalizado = texto.strip().lower()
    if not texto_normalizado:
        return False

    for patron in _REGEX_COMPILADOS:
        if patron.search(texto_normalizado):
            return True
    return False


# Recursos de ayuda. Mantener actualizados — revisar periódicamente
# que las líneas sigan activas. Colombia + recursos internacionales
# en español, dado que el usuario base está en LatAm.
RECURSOS_AYUDA = {
    "mensaje_principal": (
        "Esto que escribiste suena a que estás cargando algo muy pesado "
        "en este momento. No tienes que resolverlo solo/a."
    ),
    "lineas": [
        {
            "pais": "Colombia (nacional)",
            "nombre": "Línea Nacional de Teleorientación en Salud Mental",
            "telefono": "106",
            "detalle": "Gratuita, anónima, 24/7. No necesitas estar afiliado a una EPS."
        },
        {
            "pais": "Colombia (emergencia inmediata)",
            "nombre": "Línea de Emergencias",
            "telefono": "123",
            "detalle": "Si hay riesgo inmediato de daño, este es el canal de respuesta de emergencia."
        },
        {
            "pais": "Internacional",
            "nombre": "Directorio internacional de líneas de ayuda",
            "url": "https://findahelpline.com",
            "detalle": "Por si el usuario está fuera de Colombia."
        },
    ],
    "mensaje_secundario": (
        "Si en este momento estás en peligro inmediato, por favor llama a la línea 123 "
        "o acude al centro de salud más cercano."
    )
}


def respuesta_crisis() -> dict:
    """
    Construye la respuesta estándar que el backend devuelve cuando
    se detecta riesgo. El frontend debe tratar esta respuesta de forma
    DIFERENTE al flujo normal (no debe decir "tarea pospuesta con éxito").
    """
    return {
        "estado": "riesgo_detectado",
        "recursos": RECURSOS_AYUDA
    }