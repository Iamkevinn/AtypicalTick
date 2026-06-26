# evidencia_acumulada.py
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --- Zona horaria centralizada (ver main.py) ---
BOGOTA = ZoneInfo("America/Bogota")


def _hace_n_dias_bogota(n: int) -> str:
    return (datetime.now(BOGOTA) - timedelta(days=n)).strftime("%Y-%m-%d %H:%M:%S")


def obtener_evidencia_acumulada():
    try:
        conn = sqlite3.connect('atypical_data.db')
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
        friccion_previa = {}
        veces_siguio_tras_bloqueo = 0
        for tarea_id, accion, _ in filas:
            if accion in ('intento', 'afronto_ansiedad', 'pidio_ayuda', 'exposicion_mirar', 'paso1_comprometido'):
                friccion_previa[tarea_id] = friccion_previa.get(tarea_id, 0) + 1
            elif accion in ('completada', 'avance_parcial', 'paso1_realizado'):
                if friccion_previa.get(tarea_id, 0) >= 1:
                    veces_siguio_tras_bloqueo += 1
                friccion_previa[tarea_id] = 0
        cursor.execute("""
            SELECT COUNT(*) FROM interacciones
            WHERE energia = 'baja'
            AND accion IN ('completada', 'avance_parcial', 'paso1_realizado', 'paso1_comprometido', 'exposicion_mirar')
            AND timestamp >= ?
        """, (limite_30,))
        veces_energia_baja = cursor.fetchone()[0]
        conn.close()
        if veces_inicio == 0 and veces_siguio_tras_bloqueo == 0 and veces_energia_baja == 0:
            return None
        return {
            "periodo_dias": 30,
            "veces_inicio": veces_inicio,
            "veces_siguio_tras_bloqueo": veces_siguio_tras_bloqueo,
            "veces_energia_baja": veces_energia_baja,
        }
    except Exception:
        return None