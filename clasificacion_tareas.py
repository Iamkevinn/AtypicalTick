# clasificación_tareas.py
import re
import re as _re_trigger
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# --- Zona horaria centralizada (ver main.py) ---
# Las ventanas de CONTEXTOS_VALIDOS (ej. "al_despertar" = 4am-11am)
# estan pensadas en hora real de Bogota. esta_en_ventana_valida()
# usaba datetime.now() (hora naive del servidor) como default cuando
# no se le pasaba "momento" explicitamente, lo que comparaba esas
# ventanas contra una hora que podia estar desfasada varias horas
# si el servidor corre en UTC u otra zona.
BOGOTA = ZoneInfo("America/Bogota")

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
PATRON_MARGEN = re.compile(r"^margen-(\d{1,4})$")  # ej "margen-30" = 30 min de gracia

# Antes esto SIEMPRE caia en 120 sin importar el tipo de tarea, porque
# clasificar_tarea() nunca devolvia esta clave. Diferenciamos por fuente:
# las señales fuertes (medicamentos, citas, vuelos) merecen un margen mas
# corto porque la precision importa mas; las señales debiles, uno mas largo.
MARGENES_POR_FUENTE = {
    "tag_explicito": 90,
    "inferido_fuerte": 60,
    "inferido_debil": 180,
}
MARGEN_MINUTOS_DEFAULT = 120

def clasificar_tarea(titulo: str, etiquetas: list = None, carpeta: str = "",
                      tiene_hora_especifica: bool = False) -> dict:
    tags = [t.lower().strip() for t in (etiquetas or [])]
    titulo_lower = (titulo or "").lower()
    carpeta_lower = (carpeta or "").lower()

    resultado = {
        "hora_importa": False, "ventana": None,
        "contexto_importa": False, "contexto_ideal": None,
        "confianza": "ninguna", "fuente": "default",
    }

    margen_explicito = None  # tag "margen-N", si el usuario lo puso

    def _finalizar(r: dict) -> dict:
        r["margen_minutos"] = (
            margen_explicito if margen_explicito is not None
            else MARGENES_POR_FUENTE.get(r.get("fuente"), MARGEN_MINUTOS_DEFAULT)
        )
        return r

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
        m3 = PATRON_MARGEN.match(tag)
        if m3:
            margen_explicito = int(m3.group(1))
    if "rigida" in tags:
        resultado.update(hora_importa=True, ventana=None, confianza="alta", fuente="tag_explicito")
        hubo_tag = True
    if "ritual" in tags and not resultado["contexto_importa"]:
        resultado.update(contexto_importa=True, contexto_ideal="al_despertar",
                          confianza="alta", fuente="tag_explicito")
        hubo_tag = True
    if "flexible" in tags:
        return _finalizar({"hora_importa": False, "ventana": None, "contexto_importa": False,
                            "contexto_ideal": None, "confianza": "alta", "fuente": "tag_explicito"})

    if hubo_tag:
        return _finalizar(resultado)

    # --- 2. Inferencia automática ---
    if any(p in titulo_lower for p in PALABRAS_HORA_FUERTE):
        resultado.update(hora_importa=True, ventana=None, confianza="alta", fuente="inferido_fuerte")
        return _finalizar(resultado)

    for contexto, palabras in PALABRAS_CONTEXTO.items():
        if any(p in titulo_lower for p in palabras):
            resultado.update(contexto_importa=True, contexto_ideal=contexto,
                              confianza="alta", fuente="inferido_fuerte")
            return _finalizar(resultado)

    es_carpeta_sensible = any(c in carpeta_lower for c in CARPETAS_SALUD + CARPETAS_FINANZAS)
    if tiene_hora_especifica and es_carpeta_sensible:
        resultado.update(hora_importa=True, ventana=None, confianza="media", fuente="inferido_debil")
        return _finalizar(resultado)

    if any(p in titulo_lower for p in PALABRAS_HORA_MEDIA) and tiene_hora_especifica:
        resultado.update(hora_importa=True, ventana=None, confianza="media", fuente="inferido_debil")
        return _finalizar(resultado)

    return _finalizar(resultado)

def esta_en_ventana_valida(restricciones: dict, momento: datetime = None) -> bool:
    momento = momento or datetime.now(BOGOTA)
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

def _parsear_trigger_iso8601(trigger_str: str):
    """
    Parsea un TRIGGER de iCal usado en 'reminders' de TickTick.
    Devuelve minutos de anticipo (positivo = antes de la hora), o None
    si no es un trigger "antes" parseable.
    Ejemplos: "TRIGGER:-PT2H" -> 120.0 | "TRIGGER:-PT30M" -> 30.0
    """
    if not trigger_str or not isinstance(trigger_str, str):
        return None
    m = re.match(r"^TRIGGER:(-)?P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", trigger_str.strip())
    if not m:
        return None
    es_antes = m.group(1) == "-"
    dias = int(m.group(2) or 0)
    horas = int(m.group(3) or 0)
    minutos = int(m.group(4) or 0)
    segundos = int(m.group(5) or 0)
    total_minutos = dias * 24 * 60 + horas * 60 + minutos + segundos / 60
    if not es_antes and total_minutos != 0:
        return None
    return total_minutos


def obtener_anticipo_reminders_minutos(reminders: list):
    """Mayor anticipo (minutos) configurado en TickTick, o None si no hay."""
    if not reminders:
        return None
    anticipos = [_parsear_trigger_iso8601(r) for r in reminders]
    anticipos = [a for a in anticipos if a is not None and a > 0]
    return max(anticipos) if anticipos else None


def calcular_ventana_visibilidad(restricciones: dict, es_recurrente: bool,
                                   hora_programada: datetime, reminders: list = None,
                                   ahora: datetime = None, es_critica_salud: bool = False) -> dict:
    """
    Decide si una tarea de horario estricto (hora_importa=True, ventana=None)
    debe mostrarse en /api/enfoque AHORA, y si merece el boost de "imnencia
    activa" en el score.

    RECURRENTE (pastilla diaria, rutina de salud con hora fija):
      Oculta antes de su hora. Visible + activa SOLO en [hora, hora+margen].
      Después del margen: oculta (se perdió esta ocurrencia; el día
      siguiente, main.py decide si sube prioridad por repetición).

    EVENTO ÚNICO (cita médica, vuelo) -- nunca se auto-completa:
      Anticipo = mayor reminder configurado en TickTick, o si no hay,
      margen_minutos de la clasificación automática.
      Oculta antes de (hora - anticipo). Visible desde ahí EN ADELANTE,
      sin límite superior (si se vence, sigue visible y acumulando
      dias_atraso -- eso ya lo maneja calcular_peso_psicologico aparte).
      "Activa" (boost máximo) solo cerca de la hora real:
      [hora - anticipo, hora + margen].
    """
    ahora = ahora or datetime.now(BOGOTA)
    margen = timedelta(minutes=restricciones.get("margen_minutos", MARGEN_MINUTOS_DEFAULT))

    if es_recurrente and not es_critica_salud:
        fin_ventana = hora_programada + margen
        dentro = hora_programada <= ahora <= fin_ventana
        return {"visible": dentro, "es_horario_estricto_activo": dentro}

    anticipo_min = obtener_anticipo_reminders_minutos(reminders)
    anticipo = timedelta(minutes=anticipo_min) if anticipo_min is not None else margen
    # Para salud recurrente vencida, no aplicamos el anticipo "antes de
    # la hora" (no tiene sentido recordar la pastilla 2h antes cada dia);
    # solo nos importa que quede visible DESPUES de su hora.
    inicio_ventana = hora_programada if (es_recurrente and es_critica_salud) else hora_programada - anticipo

    visible = ahora >= inicio_ventana
    activo = inicio_ventana <= ahora <= hora_programada + margen
    return {"visible": visible, "es_horario_estricto_activo": activo}