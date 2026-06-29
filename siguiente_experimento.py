# siguiente_experimento.py
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from db import db_connection

# --- Zona horaria centralizada (ver main.py) ---
BOGOTA = ZoneInfo("America/Bogota")


def generar_siguiente_experimento():
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            hace_14_dias = (datetime.now(BOGOTA) - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                SELECT intervencion_usada,
                       COUNT(*) as total,
                       SUM(CASE WHEN resultado_final IN ('completada', 'avance_parcial', 'paso1_realizado') THEN 1 ELSE 0 END) as exitos
                FROM sesiones_tarea
                WHERE timestamp >= ?
                  AND intervencion_usada != 'Ninguna'
                GROUP BY intervencion_usada
                HAVING total >= 3
                ORDER BY exitos DESC
                LIMIT 1
            """, (hace_14_dias,))
            fila = cursor.fetchone()
        if not fila:
            return None
        intervencion, total, exitos = fila
        if exitos == 0:
            return None
        tasa = round((exitos / total) * 100)
        if tasa < 50:
            return None
        mapa_experimentos = {
            "Intervencion de Salud Fisica": "Antes de pensar en la tarea, pon el objeto físico (vaso, pastillero, etc.) directamente frente a ti.",
            "Reduccion de Incertidumbre Financiera": "Abre la app o documento del banco sin la intención de decidir nada todavía, solo para mirar el número.",
            "Exposicion Segura de Comunicacion": "Escribe el borrador del mensaje en notas, sin enviarlo, antes de acercarte al chat real.",
            "Ruptura de Perfeccionismo": "Haz la versión intencionalmente mediocre primero, antes de permitirte mejorarla.",
            "Reduccion de Sobrecarga (Inercia)": "Ubícate frente al espacio de trabajo sin intención de empezar todavía.",
            "Exposicion Conductual": "Observa la tarea o sus requisitos 30 segundos antes de decidir si actúas.",
            "Intervencion de Activacion Amigdalina": "Cuando sientas pesadez, haz un estiramiento de 5 segundos antes de decidir si es cansancio o tensión.",
            "Acomodacion a Friccion Fisica (Agotamiento Real)": "Haz la tarea desde donde ya estás sentado, sin moverte de lugar primero.",
            "Despeje de Incertidumbre": "Escribe en una sola oración el punto exacto donde dejaste de entender.",
            "Activacion Estandar": "Abre los recursos de la tarea y haz un solo movimiento relacionado, sin comprometerte a más.",
        }
        accion_concreta = mapa_experimentos.get(intervencion)
        if not accion_concreta:
            return None
        return {
            "intervencion": intervencion,
            "veces_usada": total,
            "tasa_exito": tasa,
            "experimento": accion_concreta,
            "evidencia": f"En las últimas 2 semanas, esto te ayudó a avanzar {exitos} de {total} veces que lo intentaste."
        }
    except Exception as e:
        logging.exception("Error generando siguiente experimento: %s", e)
        return None
