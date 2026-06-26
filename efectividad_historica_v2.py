# efectividad_historica_v2.py
import sqlite3

MOTIVOS_EXPOSICION = ["ansiedad", "miedo", "me preocupa", "me da ansiedad"]


def _es_motivo_exposicion(motivo_bloqueo: str) -> bool:
    motivo_lower = (motivo_bloqueo or "").lower()
    return any(m in motivo_lower for m in MOTIVOS_EXPOSICION)


def _friccion_va_bajando(tarea_ids: list) -> bool:
    if not tarea_ids:
        return False

    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(tarea_ids))
        cursor.execute(f"""
            SELECT tarea_id, accion, timestamp FROM interacciones
            WHERE tarea_id IN ({placeholders})
            ORDER BY timestamp ASC
        """, tarea_ids)
        filas = cursor.fetchall()
        conn.close()

        if len(filas) < 4:
            return False

        rachas = []
        racha_actual = 0
        for _, accion, _ in filas:
            if accion in ('completada', 'avance_parcial', 'paso1_realizado'):
                if racha_actual > 0:
                    rachas.append(racha_actual)
                racha_actual = 0
            elif accion in ('intento', 'afronto_ansiedad', 'pidio_ayuda',
                             'exposicion_mirar', 'paso1_comprometido'):
                racha_actual += 1

        if racha_actual > 0:
            rachas.append(racha_actual)

        if len(rachas) < 2:
            return False

        mitad = len(rachas) // 2
        promedio_temprano = sum(rachas[:mitad]) / mitad
        promedio_reciente = sum(rachas[mitad:]) / (len(rachas) - mitad)

        return promedio_reciente < promedio_temprano

    except Exception:
        return False


def obtener_efectividad_historica(motivo_bloqueo: str, energia_actual: str):
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT intervencion_usada,
                   COUNT(*) as total_veces,
                   SUM(CASE WHEN resultado_final IN ('completada', 'avance_parcial', 'paso1_realizado') THEN 1 ELSE 0 END) as exitos_movimiento,
                   SUM(CASE WHEN resultado_final IN ('abandono_consciente', 'pospuesta', 'rechazada') THEN 1 ELSE 0 END) as fallos
            FROM sesiones_tarea
            WHERE bloqueo_inicial = ? AND energia = ?
            GROUP BY intervencion_usada
        """, (motivo_bloqueo, energia_actual))

        resultados = cursor.fetchall()

        es_exposicion = _es_motivo_exposicion(motivo_bloqueo)

        minimo_para_evaluar = 4 if es_exposicion else 2
        umbral_fallo_anti_patron = 50

        mejor_intervencion = None
        peor_intervencion = None
        mejor_tasa = -1
        peor_tasa = -1

        for fila in resultados:
            intervencion = fila[0]
            total = fila[1]
            exitos = fila[2] or 0
            fallos = fila[3] or 0

            tasa_exito = round((exitos / total) * 100)
            tasa_fallo = round((fallos / total) * 100)

            if total >= 2 and tasa_exito > mejor_tasa and tasa_exito >= 50:
                mejor_tasa = tasa_exito
                mejor_intervencion = intervencion

            if total >= minimo_para_evaluar and tasa_fallo > peor_tasa and tasa_fallo >= umbral_fallo_anti_patron:
                if es_exposicion:
                    cursor.execute("""
                        SELECT DISTINCT tarea_id FROM sesiones_tarea
                        WHERE bloqueo_inicial = ? AND energia = ? AND intervencion_usada = ?
                    """, (motivo_bloqueo, energia_actual, intervencion))
                    tarea_ids = [r[0] for r in cursor.fetchall()]

                    if _friccion_va_bajando(tarea_ids):
                        continue

                peor_tasa = tasa_fallo
                peor_intervencion = intervencion

        conn.close()
        return mejor_intervencion, peor_intervencion
    except Exception:
        return None, None