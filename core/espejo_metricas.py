# espejo_metricas.py
import logging
from datetime import datetime, timedelta
from db import db_connection
from config import BOGOTA
from utils.fechas import hace_n_dias_bogota
# --- Zona horaria centralizada (ver main.py) ---
# Las filas de "interacciones" ahora guardan su timestamp en hora
# Bogota (registrar_interaccion en main.py lo inserta explicitamente).
# Por eso aqui calculamos el limite de "hace N dias" tambien en
# Bogota, en vez de usar datetime('now', ...) de SQLite — que siempre
# calcula en UTC y desalinearia la ventana de busqueda contra los
# timestamps ya guardados en Bogota.
 

ACCIONES_FRICCION = ('intento', 'afronto_ansiedad', 'pidio_ayuda', 'exposicion_mirar', 'paso1_comprometido')
ACCIONES_MOVIMIENTO = ('completada', 'avance_parcial', 'paso1_realizado')
ACCIONES_RETIRADA = ('rechazada', 'pospuesta', 'abandono_consciente')


def calcular_aproximaciones(
    acciones: dict,
):
    aproximaciones = (
        acciones.get("exposicion_mirar", 0)
        + acciones.get("paso1_comprometido", 0)
        + acciones.get("paso1_realizado", 0)
        + acciones.get("avance_parcial", 0)
        + acciones.get("intento", 0)
        + acciones.get("afronto_ansiedad", 0)
    )

    transiciones = (
        acciones.get("exposicion_mirar", 0)
        + acciones.get("paso1_comprometido", 0)
    )

    return aproximaciones, transiciones

def calcular_latencia_activacion(dias: int = 14):
    """
    Minutos promedio entre el primer registro de fricción del día para
    una tarea y el momento en que esa misma tarea recibe una acción de
    movimiento, ese mismo día.

    Devuelve (latencia_promedio, tendencia). tendencia es uno de
    "↓ bajando", "↑ subiendo", "→ estable", o None si no hay suficiente
    historial para comparar (mínimo 4 pares completos). Nunca inventamos
    una tendencia sin al menos dos mitades de datos que comparar.
    """
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tarea_id, accion, timestamp FROM interacciones
                WHERE timestamp >= ?
                ORDER BY tarea_id, timestamp ASC
            """, (hace_n_dias_bogota(dias),))
            filas = cursor.fetchall()

        primer_friccion_del_dia = {}  # (tarea_id, fecha) -> datetime
        pares_minutos = []  # (timestamp_cierre, minutos_transcurridos)

        for tarea_id, accion, ts_str in filas:
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue

            clave = (tarea_id, ts.date())

            if accion in ACCIONES_FRICCION and clave not in primer_friccion_del_dia:
                primer_friccion_del_dia[clave] = ts
            elif accion in ACCIONES_MOVIMIENTO and clave in primer_friccion_del_dia:
                inicio = primer_friccion_del_dia.pop(clave)
                minutos = (ts - inicio).total_seconds() / 60
                if 0 <= minutos <= 24 * 60:  # descarta outliers de más de un día
                    pares_minutos.append((ts, minutos))

        if len(pares_minutos) < 4:
            return None, None

        pares_minutos.sort(key=lambda par: par[0])
        mitad = len(pares_minutos) // 2
        if mitad == 0 or mitad == len(pares_minutos):
            return None, None

        promedio_temprano = sum(m for _, m in pares_minutos[:mitad]) / mitad
        promedio_reciente = sum(m for _, m in pares_minutos[mitad:]) / (len(pares_minutos) - mitad)
        promedio_general = round(sum(m for _, m in pares_minutos) / len(pares_minutos))

        if promedio_reciente < promedio_temprano * 0.85:
            tendencia = "↓ bajando"
        elif promedio_reciente > promedio_temprano * 1.15:
            tendencia = "↑ subiendo"
        else:
            tendencia = "→ estable"

        return promedio_general, tendencia
    except Exception as e:
        logging.exception("Error calculando latencia de activacion: %s", e)
        return None, None


def calcular_desglose_aproximaciones(dias: int = 7):
    """
    Desglosa, por tipo, las veces que la persona se acercó a algo que
    evitaba en los últimos `dias` días:
      - miradas: veces que solo se expuso a mirar (exposicion_mirar)
      - primeros_pasos: veces que dio el primer paso físico real
      - retornos: veces que, tras posponer/rechazar/abandonar una tarea,
        volvió después con una acción de movimiento sobre esa misma tarea

    Si no hay ningún dato, devuelve None (no rellenamos con ceros
    decorativos — mismo principio que evidencia_acumulada.py).
    """
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            limite = hace_n_dias_bogota(dias)

            cursor.execute("""
                SELECT accion, COUNT(*) FROM interacciones
                WHERE timestamp >= ?
                GROUP BY accion
            """, (limite,))
            acciones = dict(cursor.fetchall())

            cursor.execute("""
                SELECT tarea_id, accion, timestamp FROM interacciones
                WHERE timestamp >= ?
                ORDER BY tarea_id, timestamp ASC
            """, (limite,))
            filas = cursor.fetchall()

        retiro_previo = {}
        retornos = 0
        for tarea_id, accion, _ in filas:
            if accion in ACCIONES_RETIRADA:
                retiro_previo[tarea_id] = True
            elif accion in ACCIONES_MOVIMIENTO and retiro_previo.get(tarea_id):
                retornos += 1
                retiro_previo[tarea_id] = False

        miradas = acciones.get('exposicion_mirar', 0)
        primeros_pasos = acciones.get('paso1_realizado', 0)

        if miradas == 0 and primeros_pasos == 0 and retornos == 0:
            return None

        return {"miradas": miradas, "primeros_pasos": primeros_pasos, "retornos": retornos}
    except Exception as e:
        logging.exception("Error calculando desglose de aproximaciones: %s", e)
        return None


def construir_anti_patron(patron_detectado: dict):
    """
    El frontend espera un string plano (espejo.anti_patron). El backend
    ya genera un objeto más rico (tipo/icono/mensaje) en patron_detectado.
    Tomamos solo el mensaje aquí — main.py sigue devolviendo el objeto
    completo también, por si en el futuro se quiere mostrar el icono.
    """
    if not patron_detectado:
        return None
    return patron_detectado.get("mensaje")


def construir_evidencia_retorno(insight_profundo: str, dias_ausente: int):
    """
    Una sola frase narrativa de evidencia personal, en orden de prioridad:
      1. El insight basado en datos reales de una carpeta (si existe).
      2. Si no hay ese insight pero la persona estuvo ausente y volvió,
         eso también es evidencia real y vale la pena nombrarla.
      3. Si no hay ninguno de los dos, no inventamos una frase de relleno.
    """
    if insight_profundo:
        return insight_profundo
    if dias_ausente and dias_ausente > 3:
        return (
            f"Estuviste {dias_ausente} días sin interactuar con la app y, aun así, "
            f"volviste. Volver después de una pausa también es un dato — no solo "
            f"la racha sin interrupciones."
        )
    return None
