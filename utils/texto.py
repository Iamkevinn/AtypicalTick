# utils/texto.py
"""
Normalización de texto en español para comparaciones robustas.

BUG QUE ESTO ARREGLA:
Varias partes del sistema comparan palabras clave contra texto libre del
usuario (título de tarea, motivo de bloqueo, nombre de intervención) usando
substring simple sobre `.lower()`. Eso NO es suficiente en español: "médico"
no contiene "medico" como substring porque 'é' y 'e' son códigos distintos.
Lo mismo pasa con "trámite"/"tramite", "exposición"/"exposicion", etc.

Resultado real antes de este fix: tareas críticas de salud/trámites escritas
con tildes (lo normal en español) no se detectaban como críticas, y el
insight clínico de "ansiedad disfrazada de cansancio" casi nunca se activaba
porque buscaba "exposición" con tilde contra nombres de intervención
generados sin tilde.

Uso: normalizar TANTO el texto de origen como los patrones de búsqueda antes
de comparar, para no depender de que alguien haya escrito con o sin acento.
"""

import unicodedata


def normalizar(texto: str) -> str:
    """
    Pasa a minúsculas y quita tildes/diacríticos.
    "Médico", "médico", "MEDICO" -> "medico"
    "Exposición" -> "exposicion"
    None o "" -> ""
    """
    if not texto:
        return ""

    texto = texto.lower()
    forma_descompuesta = unicodedata.normalize("NFD", texto)
    sin_tildes = "".join(
        c for c in forma_descompuesta
        if unicodedata.category(c) != "Mn"  # Mn = marca diacrítica (combining mark)
    )
    return sin_tildes


def contiene_alguna(texto: str, palabras) -> bool:
    """
    True si `texto` contiene alguna de `palabras` como substring,
    comparando ambos lados normalizados (sin tildes, en minúsculas).
    """
    texto_norm = normalizar(texto)
    return any(normalizar(palabra) in texto_norm for palabra in palabras)