# gestion_horario_estricto.py
import requests
import sqlite3
import re
import json
from datetime import datetime, timedelta
from clasificacion_tareas import clasificar_tarea

def _parsear_fecha_ticktick(fecha_str: str):
    try:
        fecha_limpia = re.sub(r'\.\d+', '', fecha_str)
        return datetime.strptime(fecha_limpia, "%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        return None

def _esta_fuera_de_margen(tarea: dict, carpeta: str, ahora) -> bool:
    if tarea.get('isAllDay', True):
        return False
    if 'dueDate' not in tarea:
        return False

    hora_tarea = _parsear_fecha_ticktick(tarea['dueDate'])
    if not hora_tarea:
        return False

    restricciones = clasificar_tarea(
        titulo=tarea.get('title', ''),
        etiquetas=tarea.get('tags', []),
        carpeta=carpeta,
        tiene_hora_especifica=True
    )
    margen_minutos = restricciones.get('margen_minutos', 120)

    limite = hora_tarea + timedelta(minutes=margen_minutos)
    return ahora.timestamp() > limite.timestamp()

def es_horario_estricto_recurrente(tarea: dict, carpeta: str) -> bool:
    """
    CONCEPTO CENTRAL:
    Solo las tareas de horario estricto QUE SE REPITEN son neutralizables.
    """
    if not tarea.get('repeatFlag'):
        return False
        
    restricciones = clasificar_tarea(
        titulo=tarea.get('title', ''),
        etiquetas=tarea.get('tags', []),
        carpeta=carpeta,
        tiene_hora_especifica=not tarea.get('isAllDay', True)
    )
    return bool(restricciones.get('hora_importa') and not restricciones.get('ventana'))

def tarea_es_horario_estricto_vencida(tarea: dict, carpeta: str, ahora=None) -> bool:
    ahora = ahora or datetime.now()

    if not es_horario_estricto_recurrente(tarea, carpeta):
        return False

    return _esta_fuera_de_margen(tarea, carpeta, ahora)

def _ya_fue_marcada_desconocida(tarea_id: str, due_date: str) -> bool:
    """
    CLAVE LÓGICA: tarea_id + dueDate
    Comprobamos si ESTA ocurrencia exacta ya fue neutralizada.
    """
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        # Buscamos en metadata_ia la coincidencia exacta de la fecha
        cursor.execute('''
            SELECT COUNT(*) FROM interacciones
            WHERE tarea_id = ? AND accion = 'desconocida'
            AND metadata_ia LIKE ?
        ''', (tarea_id, f'%"{due_date}"%'))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False

def procesar_horario_estricto_vencido(headers: dict, mapa_carpetas: dict, registrar_interaccion_fn):
    ahora = datetime.now()
    procesadas = 0

    try:
        url_listas = "https://api.ticktick.com/open/v1/project"
        resp_listas = requests.get(url_listas, headers=headers, timeout=10)
        if resp_listas.status_code != 200:
            return procesadas
        listas = resp_listas.json()
    except requests.exceptions.RequestException as e:
        print(f"[horario_estricto] No se pudo listar proyectos: {e}")
        return procesadas

    for lista in listas:
        if lista.get('closed') or lista.get('isClosed'):
            continue

        nombre_carpeta = lista.get('name', 'Inbox')
        url_tareas = f"https://api.ticktick.com/open/v1/project/{lista['id']}/data"

        try:
            resp_tareas = requests.get(url_tareas, headers=headers, timeout=10)
            if resp_tareas.status_code != 200:
                continue
            tareas = resp_tareas.json().get('tasks', [])
        except requests.exceptions.RequestException as e:
            print(f"[horario_estricto] Error leyendo lista '{nombre_carpeta}': {e}")
            continue

        for tarea in tareas:
            if tarea.get('status', 0) != 0:
                continue

            if not es_horario_estricto_recurrente(tarea, nombre_carpeta):
                continue

            if not _esta_fuera_de_margen(tarea, nombre_carpeta, ahora):
                continue

            # IDENTIFICADOR POR OCURRENCIA
            due_date_str = tarea.get('dueDate')
            if not due_date_str:
                continue
                
            if _ya_fue_marcada_desconocida(tarea['id'], due_date_str):
                continue

            # Guardamos la fecha de la instancia específica en metadata
            metadata = json.dumps({"due_date": due_date_str})

            try:
                registrar_interaccion_fn(
                    tarea_id=tarea['id'],
                    tarea_nombre=tarea.get('title', 'Desconocida'),
                    energia="desconocida",
                    accion="desconocida",
                    emocion=None,
                    carpeta=nombre_carpeta,
                    etiquetas=",".join(tarea.get('tags', [])),
                    metadata_ia=metadata
                )
                procesadas += 1
                # Output por consola mejorado para debugear (Muestra la instancia)
                print(f"[horario_estricto] Cíclica vencida oculta localmente: '{tarea.get('title')}' (Instancia: {due_date_str})")
            except Exception as e:
                print(f"[horario_estricto] Error registrando '{tarea.get('title')}': {e}")

    return procesadas