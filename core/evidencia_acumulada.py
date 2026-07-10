# evidencia_acumulada.py
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from db import db_connection
from config import BOGOTA

# --- Zona horaria centralizada (ver main.py) ---
 
MAX_HORAS_MISMA_SESION = 8


def _hace_n_dias_bogota(n: int) -> str:
    return (datetime.now(BOGOTA) - timedelta(days=n)).strftime("%Y-%m-%d %H:%M:%S")


def obtener_evidencia_acumulada():
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            limite_30 = _hace_n_dias_bogota(30)
            cursor.execute("""
                SELECT COUNT(*) FROM interacciones
                WHERE accion IN ('paso1_realizado', 'paso1_comprometido', 'exposicion_mirar', 'intento', 'afronto_ansiedad')
                AND timestamp >= ?
            """, (limite_30,))
            veces_inicio = cursor.fetchone()[0]
            cursor.execute("""
                SELECT tarea_id, accion, timestamp FROM interacciones
                WHERE timestamp >= ?
                ORDER BY tarea_id, timestamp ASC
            """, (limite_30,))
            filas = cursor.fetchall()
            cursor.execute("""
                SELECT COUNT(*) FROM interacciones
                WHERE energia = 'baja'
                AND accion IN ('completada', 'avance_parcial', 'paso1_realizado', 'paso1_comprometido', 'exposicion_mirar')
                AND timestamp >= ?
            """, (limite_30,))
            veces_energia_baja = cursor.fetchone()[0]

        friccion_previa = {}
        veces_siguio_tras_bloqueo = 0
        for tarea_id, accion, ts_str in filas:
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                continue

            if accion in ('intento', 'afronto_ansiedad', 'pidio_ayuda', 'exposicion_mirar', 'paso1_comprometido'):
                friccion_previa[tarea_id] = ts
            elif accion in ('completada', 'avance_parcial', 'paso1_realizado'):
                inicio = friccion_previa.get(tarea_id)
                if inicio and ts.date() == inicio.date() and (ts - inicio) <= timedelta(hours=MAX_HORAS_MISMA_SESION):
                    veces_siguio_tras_bloqueo += 1
                friccion_previa.pop(tarea_id, None)

        if veces_inicio == 0 and veces_siguio_tras_bloqueo == 0 and veces_energia_baja == 0:
            return None
        return {
            "periodo_dias": 30,
            "veces_inicio": veces_inicio,
            "veces_siguio_tras_bloqueo": veces_siguio_tras_bloqueo,
            "veces_energia_baja": veces_energia_baja,
        }
    except Exception as e:
        logging.exception("Error obteniendo evidencia acumulada: %s", e)
        return None
