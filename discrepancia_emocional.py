# discrepancia_emocional.py
import sqlite3
from feedback_discrepancia import fue_rechazada_antes

MINIMO_REPETICIONES = 5


def detectar_discrepancia_motivo(motivo_declarado: str, energia_actual: str):
    if not motivo_declarado:
        return None
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM sesiones_tarea
            WHERE bloqueo_inicial = ? AND energia = ?
        """, (motivo_declarado, energia_actual))
        total_declaraciones = cursor.fetchone()[0]
        if total_declaraciones < MINIMO_REPETICIONES:
            conn.close()
            return None
        cursor.execute("""
            SELECT intervencion_usada,
                   COUNT(*) as total,
                   SUM(CASE WHEN resultado_final IN ('completada', 'avance_parcial', 'paso1_realizado') THEN 1 ELSE 0 END) as exitos
            FROM sesiones_tarea
            WHERE bloqueo_inicial = ? AND energia = ?
            GROUP BY intervencion_usada
            ORDER BY exitos DESC
            LIMIT 1
        """, (motivo_declarado, energia_actual))
        fila = cursor.fetchone()
        conn.close()
        if not fila or fila[1] < 2:
            return None
        intervencion_top, total, exitos = fila
        tasa = round((exitos / total) * 100) if total else 0
        motivo_lower = motivo_declarado.lower()
        categoria_declarada = None
        if "agotado" in motivo_lower or "energía" in motivo_lower:
            categoria_declarada = "agotamiento"
        elif "ansiedad" in motivo_lower or "miedo" in motivo_lower:
            categoria_declarada = "ansiedad"
        elif "perfecto" in motivo_lower or "listo" in motivo_lower:
            categoria_declarada = "perfeccionismo"
        intervencion_lower = (intervencion_top or "").lower()
        es_intervencion_ansiedad = "exposición" in intervencion_lower or "amigdalina" in intervencion_lower
        if categoria_declarada == "agotamiento" and es_intervencion_ansiedad and tasa >= 50:
            if fue_rechazada_antes(motivo_declarado, energia_actual, intervencion_top):
                return None
            return {
                "motivo_declarado": motivo_declarado,
                "veces_declarado": total_declaraciones,
                "intervencion_que_funciona": intervencion_top,
                "tasa_exito_real": tasa,
                "sugerencia": (
                    f"Cuando dices '{motivo_declarado}', tu historial muestra que lo que "
                    f"realmente te ayuda a moverte es una intervención pensada para ansiedad "
                    f"({tasa}% de las veces que la usaste avanzaste). "
                    f"¿Será que a veces el cansancio que sientes es ansiedad disfrazada?"
                )
            }
        return None
    except Exception:
        return None