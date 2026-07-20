# correccion_decisiones.py
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from db import db_connection
from repositories.db_repository import execute
from config import BOGOTA

# --- Zona horaria centralizada (ver main.py) ---
 


def init_tabla_correcciones():
    """Crea la tabla si no existe. Llamar una vez al iniciar la app."""
    # NOTA (Fase 3 pendiente): AUTOINCREMENT es sintaxis SQLite.
    with db_connection() as conn:
        execute(conn, '''
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


def registrar_correccion(tarea_id: str, tipo_decision: str, valor_original: str, correccion: str, carpeta: str = "Inbox"):
    try:
        with db_connection() as conn:
            execute(conn, '''
                INSERT INTO correcciones_usuario (tarea_id, tipo_decision, valor_original, correccion, carpeta, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (tarea_id, tipo_decision, valor_original, correccion, carpeta, datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S")))
        return True
    except Exception as e:
        logging.exception("Error al guardar correccion: %s", e)
        return False


def carpeta_fue_corregida_como_critica(carpeta: str) -> bool:
    try:
        with db_connection() as conn:
            cursor = execute(conn, '''
                SELECT COUNT(*) FROM correcciones_usuario
                WHERE tipo_decision = 'perdon_rutina'
                AND correccion = 'era_critica'
                AND carpeta = ?
            ''', (carpeta,))
            count = cursor.fetchone()[0]
        return count >= 2
    except Exception as e:
        logging.exception("Error consultando correcciones por carpeta: %s", e)
        return False


def clasificacion_ya_fue_preguntada(tarea_id: str) -> bool:
    try:
        with db_connection() as conn:
            cursor = execute(conn, '''
                SELECT COUNT(*) FROM correcciones_usuario
                WHERE tipo_decision = 'clasificacion_tarea' AND tarea_id = ?
            ''', (tarea_id,))
            count = cursor.fetchone()[0]
        return count > 0
    except Exception as e:
        logging.exception("Error consultando si clasificacion ya fue preguntada: %s", e)
        return False


def clasificacion_fue_rechazada(tarea_id: str) -> bool:
    try:
        with db_connection() as conn:
            cursor = execute(conn, '''
                SELECT correccion FROM correcciones_usuario
                WHERE tipo_decision = 'clasificacion_tarea' AND tarea_id = ?
                ORDER BY timestamp DESC LIMIT 1
            ''', (tarea_id,))
            fila = cursor.fetchone()
        return fila is not None and fila[0] == 'rechazada'
    except Exception as e:
        logging.exception("Error consultando rechazo de clasificacion: %s", e)
        return False
