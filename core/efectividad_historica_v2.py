# efectividad_historica_v2.py
import logging
from collections import defaultdict
from db import db_connection
from repositories.db_repository import execute

MOTIVOS_EXPOSICION = ["ansiedad", "miedo", "me preocupa", "me da ansiedad"]


def _es_motivo_exposicion(motivo_bloqueo: str) -> bool:
    motivo_lower = (motivo_bloqueo or "").lower()
    return any(m in motivo_lower for m in MOTIVOS_EXPOSICION)


def _friccion_va_bajando(tarea_ids: list) -> bool:
    if not tarea_ids:
        return False

    try:
        with db_connection() as conn:
            placeholders = ",".join("?" * len(tarea_ids))
            cursor = execute(conn, f"""
                SELECT tarea_id, accion, timestamp FROM interacciones
                WHERE tarea_id IN ({placeholders})
                ORDER BY tarea_id, timestamp ASC
            """, tarea_ids)
            filas = cursor.fetchall()

        if len(filas) < 4:
            return False

        rachas_por_tarea = defaultdict(list)
        racha_actual_por_tarea = defaultdict(int)
        for tarea_id, accion, _ in filas:
            if accion in ('completada', 'avance_parcial', 'paso1_realizado'):
                if racha_actual_por_tarea[tarea_id] > 0:
                    rachas_por_tarea[tarea_id].append(racha_actual_por_tarea[tarea_id])
                racha_actual_por_tarea[tarea_id] = 0
            elif accion in ('intento', 'afronto_ansiedad', 'pidio_ayuda',
                            'exposicion_mirar', 'paso1_comprometido'):
                racha_actual_por_tarea[tarea_id] += 1

        for tarea_id, racha_actual in racha_actual_por_tarea.items():
            if racha_actual > 0:
                rachas_por_tarea[tarea_id].append(racha_actual)

        rachas = [racha for lista in rachas_por_tarea.values() for racha in lista]

        if len(rachas) < 2:
            return False

        mitad = len(rachas) // 2
        if mitad == 0 or mitad == len(rachas):
            return False

        promedio_temprano = sum(rachas[:mitad]) / mitad
        promedio_reciente = sum(rachas[mitad:]) / (len(rachas) - mitad)

        return promedio_reciente < promedio_temprano

    except Exception as e:
        logging.exception("Error calculando si la friccion va bajando: %s", e)
        return False


def obtener_efectividad_historica(motivo_bloqueo: str, energia_actual: str):
    try:
        with db_connection() as conn:

            cursor = execute(conn, """
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
                        cursor = execute(conn, """
                            SELECT DISTINCT tarea_id FROM sesiones_tarea
                            WHERE bloqueo_inicial = ? AND energia = ? AND intervencion_usada = ?
                        """, (motivo_bloqueo, energia_actual, intervencion))
                        tarea_ids = [r[0] for r in cursor.fetchall()]

                        if _friccion_va_bajando(tarea_ids):
                            continue

                    peor_tasa = tasa_fallo
                    peor_intervencion = intervencion

        return _resolver_conflicto_mejor_peor(mejor_intervencion, peor_intervencion)
    except Exception as e:
        logging.exception("Error obteniendo efectividad historica: %s", e)
        return None, None


def _resolver_conflicto_mejor_peor(mejor_intervencion, peor_intervencion):
    """
    Con datos mixtos (una intervención con ~50% de éxito Y ~50% de
    fallo al mismo tiempo) es posible que la misma intervención
    califique como "mejor" y "peor" a la vez. Enviar eso tal cual al
    prompt de Gemini produce una instrucción contradictoria: "esto SI
    funciona, replícalo" y "esto lo bloquea, evítalo" sobre la misma
    técnica.

    Ante ese empate, priorizamos la señal POSITIVA (accionable y menos
    riesgosa) y descartamos la de "peor", en vez de decirle al usuario
    que evite algo que también le funciona la mitad de las veces.
    """
    if mejor_intervencion is not None and mejor_intervencion == peor_intervencion:
        logging.debug(
            "Efectividad historica ambigua para '%s': se descarta como "
            "anti-patron porque tambien califica como mejor intervencion.",
            mejor_intervencion,
        )
        return mejor_intervencion, None

    return mejor_intervencion, peor_intervencion