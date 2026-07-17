# prediccion_vs_resultado.py
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from db import db_connection
from config import BOGOTA

# --- Zona horaria centralizada (ver main.py) ---
# timestamp_prediccion y timestamp_resultado dependian de
# DEFAULT CURRENT_TIMESTAMP / CURRENT_TIMESTAMP de SQLite, que
# siempre es UTC. Eso desalineaba estos timestamps contra los de
# "interacciones" y "sesiones_tarea" (que ahora se guardan
# explicitamente en hora Bogota desde main.py), y podia hacer que
# un contraste prediccion-vs-resultado pareciera ocurrir en un dia
# distinto al real si la accion sucedia entre las 7pm y la
# medianoche hora Bogota.
 


def _ahora_bogota_str() -> str:
    return datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S")


def init_tabla_predicciones():
    """Crea la tabla si no existe. Llamar una vez al iniciar la app."""
    with db_connection() as conn:
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


def registrar_prediccion(tarea_id: str, tarea_nombre: str, prediccion: str, energia: str, carpeta: str):
    if not prediccion or not prediccion.strip():
        return False
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO predicciones (tarea_id, tarea_nombre, prediccion, energia, carpeta, timestamp_prediccion)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (tarea_id, tarea_nombre, prediccion.strip(), energia, carpeta, _ahora_bogota_str()))
        return True
    except Exception as e:
        logging.exception("Error al guardar prediccion: %s", e)
        return False


def cerrar_prediccion_con_resultado(tarea_id: str, resultado_real: str):
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE predicciones SET resultado_real = ?, timestamp_resultado = ?
                WHERE id = (
                    SELECT id FROM predicciones
                    WHERE tarea_id = ? AND resultado_real IS NULL
                    ORDER BY timestamp_prediccion DESC
                    LIMIT 1
                )
            ''', (resultado_real, _ahora_bogota_str(), tarea_id))
        return True
    except Exception as e:
        logging.exception("Error al cerrar prediccion: %s", e)
        return False


_FRASES_RESULTADO = {
    "completada": "Terminaste la tarea por completo.",
    "avance_parcial": "Avanzaste una parte y dejaste el resto para después.",
    "paso1_realizado": "Diste el primer paso físico.",
    "pospuesta": "Decidiste posponerla.",
    "abandono_consciente": "Decidiste no continuar por hoy.",
    "rechazada": "Decidiste no tomar esta tarea en ese momento.",
}


def obtener_contrastes_recientes(limite: int = 5):
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tarea_nombre, prediccion, resultado_real, timestamp_resultado
                FROM predicciones
                WHERE resultado_real IS NOT NULL
                ORDER BY timestamp_resultado DESC LIMIT ?
            ''', (limite,))
            filas = cursor.fetchall()

        contrastes = []
        for tarea_nombre, prediccion, resultado_real, _ in filas:
            contrastes.append({
                "tarea_nombre": tarea_nombre,
                "prediccion": prediccion,
                "resultado_frase": _FRASES_RESULTADO.get(resultado_real, resultado_real)
            })
        return contrastes
    except Exception as e:
        logging.exception("Error obteniendo contrastes recientes: %s", e)
        return []