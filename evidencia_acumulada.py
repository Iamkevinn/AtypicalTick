# evidencia_acumulada.py
# ---------------------------------------------------------
# "Evidencia", no "logros" ni "victorias".
#
# La diferencia no es solo de tono: un logro se puede negar o
# minimizar ("no fue nada"). Un conteo de hechos es más difícil
# de discutir con la propia narrativa negativa, porque no pide
# que la persona se sienta orgullosa — solo señala lo que pasó.
#
# REGLA DURA: todos los números vienen directo de conteos en
# interacciones / sesiones_tarea de los últimos 30 días. Cero
# inferencia, cero redondeo narrativo.
# ---------------------------------------------------------

import sqlite3


def obtener_evidencia_acumulada():
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()

        # Veces que inició algo a pesar del bloqueo (acciones de aproximación real)
        cursor.execute("""
            SELECT COUNT(*) FROM interacciones
            WHERE accion IN ('paso1_realizado', 'paso1_comprometido', 'exposicion_mirar', 'intento', 'afronto_ansiedad')
            AND timestamp >= datetime('now', '-30 days')
        """)
        veces_inicio = cursor.fetchone()[0]

        # Veces que siguió DESPUÉS de un bloqueo registrado ese mismo día para la misma tarea
        # (fricción consecutiva >= 1 antes de una acción real — mismo criterio que bloqueos_atravesados)
        cursor.execute("""
            SELECT tarea_id, accion, timestamp FROM interacciones
            WHERE timestamp >= datetime('now', '-30 days')
            ORDER BY tarea_id, timestamp ASC
        """)
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

        # Veces que trabajó (cualquier acción de movimiento) con energía baja registrada
        cursor.execute("""
            SELECT COUNT(*) FROM interacciones
            WHERE energia = 'baja'
            AND accion IN ('completada', 'avance_parcial', 'paso1_realizado', 'paso1_comprometido', 'exposicion_mirar')
            AND timestamp >= datetime('now', '-30 days')
        """)
        veces_energia_baja = cursor.fetchone()[0]

        conn.close()

        # Si no hay ningún dato todavía, no devolvemos la sección
        # (no inventamos ceros decorativos para llenar espacio)
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