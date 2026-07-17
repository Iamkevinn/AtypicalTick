# services/criticidad_service.py

from core.correccion_decisiones import carpeta_fue_corregida_como_critica
from utils.texto import normalizar


PALABRAS_CRITICAS = (
    "pagar",
    "impuesto",
    "tramite",
    "cita",
    "medico",
    "pastilla",
    "transferir",
)

PALABRAS_NO_CRITICAS = (
    "aprender",
    "curso",
    "leer",
    "estudiar",
)

TAGS_CRITICOS = (
    "medicina",
    "medicine",
    "urgente",
)

CARPETAS_CRITICAS = (
    "health",
    "salud",
    "finanzas",
    "banco",
    "pagos",
)


def calcular_score_criticidad(
    tarea: dict,
    carpeta: str,
    titulo: str,
) -> int:
    """
    Devuelve un score de criticidad basado en prioridad,
    tags, carpeta e historial clínico.
    """

    score = 0

    prioridad = tarea.get("priority", 0)

    tags = [
        t.lower()
        for t in tarea.get("tags", [])
    ]

    carpeta = normalizar(carpeta)
    titulo = normalizar(titulo)

    if prioridad == 5:
        score += 10

    if any(tag in tags for tag in TAGS_CRITICOS):
        score += 10

    if any(c in carpeta for c in CARPETAS_CRITICAS):
        score += 2

    for palabra in PALABRAS_CRITICAS:
        if palabra in titulo:
            score += 3

    for palabra in PALABRAS_NO_CRITICAS:
        if palabra in titulo:
            score -= 5

    if carpeta_fue_corregida_como_critica(carpeta):
        score += 10

    return score


def es_tarea_critica(
    tarea: dict,
    carpeta: str,
    titulo: str,
) -> bool:
    """
    Devuelve True si la tarea debe considerarse crítica.
    """

    return (
        calcular_score_criticidad(
            tarea,
            carpeta,
            titulo,
        )
        >= 4
    )