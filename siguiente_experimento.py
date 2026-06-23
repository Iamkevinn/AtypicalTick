# siguiente_experimento.py
# ---------------------------------------------------------
# Convierte el análisis de /mente en UNA acción concreta.
# Regla dura: el experimento sugerido SOLO puede basarse en
# datos que ya existen en la BD del propio usuario (qué
# intervención le funcionó, en qué carpeta, con qué fricción).
# Si no hay suficiente historial para sugerir algo específico,
# se devuelve None — no rellenamos con frases genéricas.
# ---------------------------------------------------------

import sqlite3


def generar_siguiente_experimento():
    """
    Mira los datos reales de las últimas 2 semanas y construye
    UNA sugerencia concreta de experimento conductual, citando
    el dato que la respalda. Si no hay suficiente evidencia,
    devuelve None (la pantalla simplemente no muestra esta sección).
    """
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()

        # ¿Qué intervención ha generado más movimiento real en las
        # últimas 2 semanas, sin importar el motivo de bloqueo?
        cursor.execute("""
            SELECT intervencion_usada,
                   COUNT(*) as total,
                   SUM(CASE WHEN resultado_final IN ('completada', 'avance_parcial', 'paso1_realizado') THEN 1 ELSE 0 END) as exitos
            FROM sesiones_tarea
            WHERE timestamp >= datetime('now', '-14 days')
              AND intervencion_usada != 'Ninguna'
            GROUP BY intervencion_usada
            HAVING total >= 3
            ORDER BY exitos DESC
            LIMIT 1
        """)
        fila = cursor.fetchone()
        conn.close()

        if not fila:
            return None  # no hay suficientes datos reales todavía

        intervencion, total, exitos = fila
        if exitos == 0:
            return None

        tasa = round((exitos / total) * 100)
        if tasa < 50:
            return None  # no es lo bastante consistente para sugerirlo con confianza

        # Mapeamos la intervención a UNA acción concreta y repetible.
        # Este mapa es fijo (no generado por IA) para garantizar que
        # el experimento sea siempre accionable y específico.
        mapa_experimentos = {
            "Intervención de Salud Física": "Antes de pensar en la tarea, pon el objeto físico (vaso, pastillero, etc.) directamente frente a ti.",
            "Reducción de Incertidumbre Financiera": "Abre la app o documento del banco sin la intención de decidir nada todavía, solo para mirar el número.",
            "Exposición Segura de Comunicación": "Escribe el borrador del mensaje en notas, sin enviarlo, antes de acercarte al chat real.",
            "Ruptura de Perfeccionismo": "Haz la versión intencionalmente mediocre primero, antes de permitirte mejorarla.",
            "Reducción de Sobrecarga (Inercia)": "Ubícate frente al espacio de trabajo sin intención de empezar todavía.",
            "Exposición Conductual": "Observa la tarea o sus requisitos 30 segundos antes de decidir si actúas.",
            "Intervención de Activación Amigdalina": "Cuando sientas pesadez, haz un estiramiento de 5 segundos antes de decidir si es cansancio o tensión.",
            "Acomodación a Fricción Física (Agotamiento Real)": "Haz la tarea desde donde ya estás sentado, sin moverte de lugar primero.",
            "Despeje de Incertidumbre": "Escribe en una sola oración el punto exacto donde dejaste de entender.",
            "Activación Estándar": "Abre los recursos de la tarea y haz un solo movimiento relacionado, sin comprometerte a más.",
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
    except Exception:
        return None