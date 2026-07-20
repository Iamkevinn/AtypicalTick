# discrepancia_emocional.py
import logging
from core.feedback_discrepancia import fue_rechazada_antes
from db import db_connection
from repositories.db_repository import execute
from utils.texto import normalizar

MINIMO_REPETICIONES = 5

PALABRAS_AGOTAMIENTO = (
    "agotado", "agotada", "cansado", "cansada", "muy cansado", "muy cansada",
    "sin energia", "sin energía", "fatiga", "exhausto", "exhausta", "quemado", "quemada"
)
PALABRAS_ANSIEDAD = ("ansiedad", "miedo", "nervioso", "nerviosa", "me preocupa", "pánico", "panico")
PALABRAS_PERFECCIONISMO = ("perfecto", "perfecta", "listo", "lista", "perfeccionismo")


def detectar_discrepancia_motivo(motivo_declarado: str, energia_actual: str):
    if not motivo_declarado:
        return None
    try:
        with db_connection() as conn:
            cursor = execute(conn, """
                SELECT COUNT(*) FROM sesiones_tarea
                WHERE bloqueo_inicial = ? AND energia = ?
            """, (motivo_declarado, energia_actual))
            total_declaraciones = cursor.fetchone()[0]
            if total_declaraciones < MINIMO_REPETICIONES:
                return None
            cursor = execute(conn, """
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

        if not fila or fila[1] < 2:
            return None
        intervencion_top, total, exitos = fila
        tasa = round((exitos / total) * 100) if total else 0
        motivo_lower = normalizar(motivo_declarado)
        categoria_declarada = None
        if any(normalizar(palabra) in motivo_lower for palabra in PALABRAS_AGOTAMIENTO):
            categoria_declarada = "agotamiento"
        elif any(normalizar(palabra) in motivo_lower for palabra in PALABRAS_ANSIEDAD):
            categoria_declarada = "ansiedad"
        elif any(normalizar(palabra) in motivo_lower for palabra in PALABRAS_PERFECCIONISMO):
            categoria_declarada = "perfeccionismo"
        intervencion_lower = normalizar(intervencion_top)
        es_intervencion_ansiedad = "exposicion" in intervencion_lower or "amigdalina" in intervencion_lower
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
    except Exception as e:
        logging.exception("Error detectando discrepancia de motivo: %s", e)
        return None