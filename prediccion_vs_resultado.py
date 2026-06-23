# prediccion_vs_resultado.py
# ---------------------------------------------------------
# Reestructuración cognitiva basada en EVIDENCIA, no en argumentación.
#
# Idea: justo antes de intentar una tarea bloqueada, la persona predice
# (en sus propias palabras) qué cree que va a pasar. Más tarde, cuando
# se resuelve la sesión (completada, avance_parcial, pospuesta, etc.),
# comparamos la predicción original contra el resultado real.
#
# REGLA DURA: nunca inventamos el resultado ni lo interpretamos por la
# persona. El "resultado real" es exactamente lo que ya existe en
# sesiones_tarea.resultado_final — un campo que el usuario genera con
# sus propias acciones. Solo emparejamos predicción + resultado real,
# ambos dichos/hechos por la misma persona.
# ---------------------------------------------------------

import sqlite3


def init_tabla_predicciones():
    """Crea la tabla si no existe. Llamar una vez al iniciar la app."""
    conn = sqlite3.connect('atypical_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predicciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarea_id TEXT,
            tarea_nombre TEXT,
            prediccion TEXT,
            energia TEXT,
            carpeta TEXT,
            resultado_real TEXT,
            timestamp_prediccion DATETIME DEFAULT CURRENT_TIMESTAMP,
            timestamp_resultado DATETIME
        )
    ''')
    conn.commit()
    conn.close()


def registrar_prediccion(tarea_id: str, tarea_nombre: str, prediccion: str, energia: str, carpeta: str):
    """
    Guarda la predicción de la persona ANTES de intentar la tarea.
    Se llama desde el momento de pedir ayuda a la IA (o el menú de bloqueo),
    de forma opcional — si el usuario no escribe nada, no se guarda.
    """
    if not prediccion or not prediccion.strip():
        return False
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO predicciones (tarea_id, tarea_nombre, prediccion, energia, carpeta)
            VALUES (?, ?, ?, ?, ?)
        ''', (tarea_id, tarea_nombre, prediccion.strip(), energia, carpeta))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("🚨 Error al guardar predicción:", e)
        return False


def cerrar_prediccion_con_resultado(tarea_id: str, resultado_real: str):
    """
    Cuando la sesión se resuelve (completada, avance_parcial, pospuesta,
    abandono_consciente, etc.), buscamos la predicción más reciente SIN
    resultado para esta tarea, y la cerramos con lo que realmente pasó.

    Solo cierra la predicción más reciente abierta — si la persona predijo
    varias veces para la misma tarea en distintos días, cada una se cierra
    con su propio resultado correspondiente.
    """
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM predicciones
            WHERE tarea_id = ? AND resultado_real IS NULL
            ORDER BY timestamp_prediccion DESC LIMIT 1
        ''', (tarea_id,))
        fila = cursor.fetchone()
        if fila:
            cursor.execute('''
                UPDATE predicciones SET resultado_real = ?, timestamp_resultado = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (resultado_real, fila[0]))
            conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("🚨 Error al cerrar predicción:", e)
        return False


# Traducción de resultado_real a una frase corta, en tono observacional
# (no celebratorio, no de juicio) — esto es solo formato, no interpretación.
_FRASES_RESULTADO = {
    "completada": "Terminaste la tarea por completo.",
    "avance_parcial": "Avanzaste una parte y dejaste el resto para después.",
    "paso1_realizado": "Diste el primer paso físico.",
    "pospuesta": "Decidiste posponerla.",
    "abandono_consciente": "Decidiste no continuar por hoy.",
    "rechazada": "Decidiste no tomar esta tarea en ese momento.",
}


def obtener_contrastes_recientes(limite: int = 5):
    """
    Devuelve las predicciones más recientes que YA tienen un resultado
    real registrado, para mostrar el contraste en /mente.
    Solo datos reales — ninguna predicción se muestra sin su resultado
    correspondiente ya ocurrido.
    """
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT tarea_nombre, prediccion, resultado_real, timestamp_resultado
            FROM predicciones
            WHERE resultado_real IS NOT NULL
            ORDER BY timestamp_resultado DESC LIMIT ?
        ''', (limite,))
        filas = cursor.fetchall()
        conn.close()

        contrastes = []
        for tarea_nombre, prediccion, resultado_real, _ in filas:
            contrastes.append({
                "tarea_nombre": tarea_nombre,
                "prediccion": prediccion,
                "resultado_frase": _FRASES_RESULTADO.get(resultado_real, resultado_real)
            })
        return contrastes
    except Exception:
        return []