# clasificacion_tareas.py
# ---------------------------------------------------------
# RESTRICCIONES DE CONDUCTA, NO "TIPOS DE TAREA"
# ---------------------------------------------------------
# v2: reemplaza el modelo de 4 categorías cerradas (rígida/
# semirrígida/flexible/ritual) por restricciones COMPONIBLES.
# Motivo: una tarea puede tener más de una restricción a la vez
# (ej. "tomar vitamina después de desayunar" depende de contexto
# Y de una ventana horaria suave). Forzarla a una sola categoría
# pierde o distorsiona esa información.
#
# Restricciones:
#   hora_importa:      ¿el momento exacto del reloj importa?
#   ventana:           si hora_importa=True, ventana válida
#                       (None = la hora debe ser exacta, sin margen)
#   contexto_importa:  ¿depende de un disparador situacional
#                       (despertar, antes de dormir) más que del reloj?
#   contexto_ideal:    cuál disparador, si contexto_importa=True
#
# REGLA DE DISEÑO (no negociable): el usuario NUNCA necesita
# clasificar nada para que esto funcione. Todo parte de inferencia
# automática sobre datos que YA existen (título, carpeta, si la
# tarea tiene hora específica puesta en TickTick — eso ya es una
# señal gratuita de que la hora le importó a la persona al crearla).
# Los tags (#rigida, #ritual, #ctx-despertar, #ventana-7-11) siguen
# soportados, pero solo como override de casos especiales — nunca
# como requisito. Si el usuario nunca toca un tag, el sistema debe
# funcionar igual de bien.
# ---------------------------------------------------------

import re
from datetime import datetime, time

PALABRAS_HORA_FUERTE = [
    "pastilla", "medicamento", "medicina", "dosis", "inyeccion", "inyección",
    "cita medica", "cita médica", "cita con el medico", "cita con el médico",
    "vuelo", "tren", "bus a las", "clase de", "reunion con", "reunión con",
    "examen", "entrevista",
]
PALABRAS_HORA_MEDIA = ["pagar", "vence", "vencimiento", "tramite", "trámite", "transferir"]
PALABRAS_CONTEXTO = {
    "al_despertar": ["rutina matutina", "morning routine", "al despertar", "al levantarme"],
    "antes_de_dormir": ["rutina nocturna", "antes de dormir", "antes de acostarme"],
    "despues_de_almorzar": ["despues de almorzar", "después de almorzar"],
}
CARPETAS_SALUD = ["health", "salud"]
CARPETAS_FINANZAS = ["finanzas", "banco", "pagos"]

CONTEXTOS_VALIDOS = {
    "al_despertar": (time(4, 0), time(11, 0)),
    "antes_de_dormir": (time(20, 0), time(23, 59)),
    "despues_de_almorzar": (time(12, 30), time(15, 0)),
}

PATRON_VENTANA = re.compile(r"^ventana-(\d{1,2})-(\d{1,2})$")
PATRON_CONTEXTO_TAG = re.compile(r"^ctx-([a-z_]+)$")


def clasificar_tarea(titulo: str, etiquetas: list = None, carpeta: str = "",
                      tiene_hora_especifica: bool = False) -> dict:
    """
    Inferencia automática, cero configuración requerida.

    'tiene_hora_especifica' = True si en TickTick la tarea NO es
    'isAllDay' (el usuario ya puso una hora concreta). Eso es en sí
    mismo una señal gratuita de que la hora le importa — sin que el
    usuario tenga que etiquetar nada.
    """
    tags = [t.lower().strip() for t in (etiquetas or [])]
    titulo_lower = (titulo or "").lower()
    carpeta_lower = (carpeta or "").lower()

    resultado = {
        "hora_importa": False, "ventana": None,
        "contexto_importa": False, "contexto_ideal": None,
        "confianza": "ninguna", "fuente": "default",
    }

    # --- 1. Tags explícitos: override de casos especiales (OPCIONAL) ---
    hubo_tag = False
    for tag in tags:
        m = PATRON_VENTANA.match(tag)
        if m:
            resultado.update(hora_importa=True,
                              ventana=(time(int(m.group(1)), 0), time(int(m.group(2)), 0)),
                              confianza="alta", fuente="tag_explicito")
            hubo_tag = True
        m2 = PATRON_CONTEXTO_TAG.match(tag)
        if m2:
            resultado.update(contexto_importa=True, contexto_ideal=m2.group(1),
                              confianza="alta", fuente="tag_explicito")
            hubo_tag = True
    if "rigida" in tags:
        resultado.update(hora_importa=True, ventana=None, confianza="alta", fuente="tag_explicito")
        hubo_tag = True
    if "ritual" in tags and not resultado["contexto_importa"]:
        resultado.update(contexto_importa=True, contexto_ideal="al_despertar",
                          confianza="alta", fuente="tag_explicito")
        hubo_tag = True
    if "flexible" in tags:
        return {"hora_importa": False, "ventana": None, "contexto_importa": False,
                "contexto_ideal": None, "confianza": "alta", "fuente": "tag_explicito"}

    if hubo_tag:
        return resultado  # el tag manda; no seguimos infiriendo encima

    # --- 2. Inferencia automática (esto hace el trabajo pesado SIEMPRE) ---
    if any(p in titulo_lower for p in PALABRAS_HORA_FUERTE):
        resultado.update(hora_importa=True, ventana=None, confianza="alta", fuente="inferido_fuerte")
        return resultado

    for contexto, palabras in PALABRAS_CONTEXTO.items():
        if any(p in titulo_lower for p in palabras):
            resultado.update(contexto_importa=True, contexto_ideal=contexto,
                              confianza="alta", fuente="inferido_fuerte")
            return resultado

    # Señal media: carpeta sensible (salud/finanzas) + ya tiene hora puesta en TickTick.
    # No necesitamos palabras clave aquí: si la persona YA puso una hora exacta
    # en una tarea de Salud o Finanzas, eso ya es evidencia suficiente.
    es_carpeta_sensible = any(c in carpeta_lower for c in CARPETAS_SALUD + CARPETAS_FINANZAS)
    if tiene_hora_especifica and es_carpeta_sensible:
        resultado.update(hora_importa=True, ventana=None, confianza="media", fuente="inferido_debil")
        return resultado

    if any(p in titulo_lower for p in PALABRAS_HORA_MEDIA) and tiene_hora_especifica:
        resultado.update(hora_importa=True, ventana=None, confianza="media", fuente="inferido_debil")
        return resultado

    return resultado  # default: sin restricciones — NUNCA restringimos sin evidencia


def esta_en_ventana_valida(restricciones: dict, momento: datetime = None) -> bool:
    momento = momento or datetime.now()
    hora_actual = momento.time()

    if restricciones.get("hora_importa") and restricciones.get("ventana"):
        inicio, fin = restricciones["ventana"]
        return inicio <= hora_actual <= fin

    if restricciones.get("contexto_importa"):
        rango = CONTEXTOS_VALIDOS.get(restricciones.get("contexto_ideal"))
        if rango:
            inicio, fin = rango
            return inicio <= hora_actual <= fin

    return True


def requiere_chequeo_de_fidelidad(restricciones: dict, momento_completado: datetime,
                                   hora_esperada: datetime = None) -> bool:
    """
    ¿Conviene preguntar (1 tap, cerrado: Sí/No) "¿fue en el momento
    correcto?" al completar? Nunca bloquea ni deshace nada en
    TickTick — solo decide si vale la pena un dato extra para que
    efectividad_historica_v2 / siguiente_experimento no aprendan de
    un dato contaminado (completó != completó cuando debía).
    """
    if restricciones.get("hora_importa") and not restricciones.get("ventana") and hora_esperada:
        diferencia_minutos = abs((momento_completado - hora_esperada).total_seconds()) / 60
        return diferencia_minutos > 90

    if restricciones.get("contexto_importa"):
        return not esta_en_ventana_valida(restricciones, momento_completado)

    return False


def necesita_confirmacion_unica(restricciones: dict) -> bool:
    """
    ¿Vale la pena preguntar, UNA sola vez, "Detectamos que esto es
    [algo con hora fija / parte de un ritual]. ¿Correcto? Sí/No"?

    Solo si hay una restricción real Y vino de inferencia (si vino
    de un tag explícito, el usuario ya lo dijo a propósito — no hace
    falta confirmar algo que la persona configuró ella misma).
    """
    hay_restriccion = restricciones.get("hora_importa") or restricciones.get("contexto_importa")
    return bool(hay_restriccion) and restricciones.get("fuente") in ("inferido_fuerte", "inferido_debil")