# correccion_decisiones.py
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

# --- Zona horaria centralizada (ver main.py) ---
BOGOTA = ZoneInfo("America/Bogota")


def init_tabla_correcciones():
    """Crea la tabla si no existe. Llamar una vez al iniciar la app."""
    conn = sqlite3.connect('atypical_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS correcciones_usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarea_id TEXT,
            tipo_decision TEXT,
            valor_original TEXT,
            correccion TEXT,
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
            INSERT INTO correcciones_usuario (tarea_id, tipo_decision, valor_original, correccion, carpeta, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (tarea_id, tipo_decision, valor_original, correccion, carpeta, datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("🚨 Error al guardar corrección:", e)
        return False


def carpeta_fue_corregida_como_critica(carpeta: str) -> bool:
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


def clasificacion_ya_fue_preguntada(tarea_id: str) -> bool:
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM correcciones_usuario
            WHERE tipo_decision = 'clasificacion_tarea' AND tarea_id = ?
        ''', (tarea_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def clasificacion_fue_rechazada(tarea_id: str) -> bool:
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT correccion FROM correcciones_usuario
            WHERE tipo_decision = 'clasificacion_tarea' AND tarea_id = ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (tarea_id,))
        fila = cursor.fetchone()
        conn.close()
        return fila is not None and fila[0] == 'rechazada'
    except Exception:
        return False