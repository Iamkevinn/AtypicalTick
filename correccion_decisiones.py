# correccion_decisiones.py
# ---------------------------------------------------------
# Canal de corrección GENÉRICO para decisiones que el sistema
# toma sin preguntar (perdón automático de rutinas, scoring de
# criticidad al posponer, clasificación de perfil clínico).
#
# Diseño: en vez de un botón distinto por cada tipo de decisión,
# una sola tabla con un campo "tipo_decision" que identifica
# QUÉ se está corrigiendo, y una respuesta CERRADA (no texto libre),
# para no generar otra superficie de riesgo ni pedirle al usuario
# trabajo cognitivo extra en un momento de fricción.
#
# Regla dura: todo dato es generado por el propio usuario al
# tocar un botón. Nada se infiere ni se asume.
# ---------------------------------------------------------

import sqlite3


def init_tabla_correcciones():
    """Crea la tabla si no existe. Llamar una vez al iniciar la app."""
    conn = sqlite3.connect('atypical_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS correcciones_usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarea_id TEXT,
            tipo_decision TEXT,     -- ej: 'perdon_rutina', 'criticidad_posponer', 'perfil_clinico'
            valor_original TEXT,    -- lo que el sistema decidió (ej: 'perdonada', 'no_critica')
            correccion TEXT,        -- la opción cerrada que el usuario eligió
            carpeta TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def registrar_correccion(tarea_id: str, tipo_decision: str, valor_original: str, correccion: str, carpeta: str = "Inbox"):
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO correcciones_usuario (tarea_id, tipo_decision, valor_original, correccion, carpeta)
            VALUES (?, ?, ?, ?, ?)
        ''', (tarea_id, tipo_decision, valor_original, correccion, carpeta))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("🚨 Error al guardar corrección:", e)
        return False


def carpeta_fue_corregida_como_critica(carpeta: str) -> bool:
    """
    Si el usuario ya corrigió 2+ veces que tareas de esta carpeta
    SÍ eran críticas (cuando el sistema las trató como perdonables),
    el sistema debe dejar de perdonarlas automáticamente en esa carpeta.
    Esto es una salvaguarda real basada en corrección explícita repetida,
    no una suposición.
    """
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM correcciones_usuario
            WHERE tipo_decision = 'perdon_rutina'
            AND correccion = 'era_critica'
            AND carpeta = ?
        ''', (carpeta,))
        count = cursor.fetchone()[0]
        conn.close()
        return count >= 2
    except Exception:
        return False