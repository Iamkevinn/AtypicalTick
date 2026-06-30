# main.py - Backend de AtypicalTick con FastAPI
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import requests
import re
import logging
from datetime import datetime, timedelta 
from dotenv import load_dotenv
import os
from zoneinfo import ZoneInfo
from db import db_connection

logging.debug("Proceso backend iniciado con pid %s", os.getpid())

# --- Zona horaria centralizada del proyecto ---
BOGOTA = ZoneInfo("America/Bogota")

def hace_n_dias_bogota(n: int) -> str:
    return (datetime.now(BOGOTA) - timedelta(days=n)).strftime("%Y-%m-%d %H:%M:%S")

def hoy_bogota_str() -> str:
    return datetime.now(BOGOTA).strftime("%Y-%m-%d")

# --- Modulos clinicos separados ---
from discrepancia_emocional import PALABRAS_AGOTAMIENTO, PALABRAS_ANSIEDAD, PALABRAS_PERFECCIONISMO
from deteccion_crisis import detectar_riesgo, respuesta_crisis
from efectividad_historica_v2 import obtener_efectividad_historica
from discrepancia_emocional import detectar_discrepancia_motivo
from siguiente_experimento import generar_siguiente_experimento
from feedback_discrepancia import init_tabla_feedback, registrar_feedback_discrepancia
from prediccion_vs_resultado import (
    init_tabla_predicciones, registrar_prediccion,
    cerrar_prediccion_con_resultado, obtener_contrastes_recientes
)
from evidencia_acumulada import obtener_evidencia_acumulada
from correccion_decisiones import (
    init_tabla_correcciones, registrar_correccion, carpeta_fue_corregida_como_critica
)
from espejo_metricas import (
    calcular_latencia_activacion, calcular_desglose_aproximaciones,
    construir_anti_patron, construir_evidencia_retorno
)

from clasificacion_tareas import clasificar_tarea, calcular_ventana_visibilidad
from gestion_horario_estricto import (
    tarea_es_horario_estricto_vencida,
    procesar_horario_estricto_vencido,
    es_horario_estricto_recurrente,
    init_tabla_lock_horario_estricto,
    contar_perdidas_consecutivas_salud,
    _es_critica_salud,
)
from apscheduler.schedulers.background import BackgroundScheduler

PALABRAS_FALTA_CLARIDAD = ("no entiendo", "me falta entender", "no tengo claridad", "no sé qué", "no se que")


class PeticionAutocuidado(BaseModel):
    tipo: str

def init_db():
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tarea_id TEXT,
                tarea_nombre TEXT,
                energia TEXT,
                emocion_motivo TEXT,
                accion TEXT,
                hora INTEGER,
                dia_semana TEXT, 
                carpeta TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sesiones_tarea (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tarea_id TEXT,
                bloqueo_inicial TEXT,
                intervencion_usada TEXT,
                resultado_final TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        columnas = [
            ("interacciones", "dia_semana", "TEXT"),
            ("interacciones", "carpeta", "TEXT"),
            ("interacciones", "etiquetas", "TEXT"),
            ("sesiones_tarea", "energia", "TEXT"),
            ("interacciones", "metadata_ia", "TEXT"),
            ("sesiones_tarea", "carpeta", "TEXT"),
        ]
        for tabla, columna, tipo in columnas:
            try:
                cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    logging.exception("Error agregando columna %s.%s: %s", tabla, columna, e)

def registrar_interaccion(tarea_id: str, tarea_nombre: str, energia: str, accion: str, emocion: str = None, carpeta: str = "Inbox", etiquetas: str = "", metadata_ia: str = ""):
    try:
        ahora = datetime.now(BOGOTA)
        hora_actual = ahora.hour
        dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        dia_semana = dias[ahora.weekday()]
        timestamp_str = ahora.strftime("%Y-%m-%d %H:%M:%S")

        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO interacciones (tarea_id, tarea_nombre, energia, emocion_motivo, accion, hora, dia_semana, carpeta, etiquetas, metadata_ia, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (tarea_id, tarea_nombre, energia, emocion, accion, hora_actual, dia_semana, carpeta, etiquetas, metadata_ia, timestamp_str))
    except Exception as e:
        logging.exception("Error al guardar interaccion: %s", e)
        
init_db()
init_tabla_feedback()
init_tabla_predicciones()
init_tabla_correcciones()
init_tabla_lock_horario_estricto() 

def analizar_perfil_clinico(carpeta: str, etiquetas: list):
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            etiquetas_str = ",".join(etiquetas).lower() if etiquetas else "sin_etiquetas"

            cursor.execute("""
                SELECT emocion_motivo, COUNT(*) FROM interacciones 
                WHERE (carpeta = ? OR (etiquetas != '' AND ? LIKE '%' || etiquetas || '%'))
                AND emocion_motivo IS NOT NULL 
                AND timestamp >= ? 
                GROUP BY emocion_motivo ORDER BY COUNT(*) DESC
            """, (carpeta, etiquetas_str, hace_n_dias_bogota(30)))
            resultados = cursor.fetchall()

        if not resultados: return {"dominante": None, "perfil": "desconocido"}
        
        emocion_principal = resultados[0][0].lower()
        if any(p in emocion_principal for p in PALABRAS_ANSIEDAD):
            return {"dominante": emocion_principal, "perfil": "evitacion"}
        elif any(p in emocion_principal for p in PALABRAS_AGOTAMIENTO):
            return {"dominante": emocion_principal, "perfil": "agotamiento"}
        elif any(p in emocion_principal for p in PALABRAS_FALTA_CLARIDAD):
            return {"dominante": emocion_principal, "perfil": "falta_claridad"}
        else:
            return {"dominante": emocion_principal, "perfil": "sobrecarga"}
    except Exception as e:
        logging.exception("Error analizando perfil clinico: %s", e)
        return {"dominante": None, "perfil": "desconocido"}

def obtener_patron_contextual(carpeta: str, dia_semana: str):
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT emocion_motivo, COUNT(*) as frec FROM interacciones 
                WHERE carpeta = ? AND dia_semana = ? AND emocion_motivo IS NOT NULL AND emocion_motivo != ''
                GROUP BY emocion_motivo ORDER BY frec DESC LIMIT 1
            """, (carpeta, dia_semana))
            resultado = cursor.fetchone()
            
            if not resultado:
                cursor.execute("""
                    SELECT emocion_motivo, COUNT(*) as frec FROM interacciones 
                    WHERE carpeta = ? AND emocion_motivo IS NOT NULL AND emocion_motivo != ''
                    GROUP BY emocion_motivo ORDER BY frec DESC LIMIT 1
                """, (carpeta,))
                resultado = cursor.fetchone()
        return resultado[0] if resultado else None
    except Exception as e:
        logging.exception("Error obteniendo patron contextual: %s", e)
        return None
    
def obtener_token():
    try:
        with open(".token-oauth", "r") as archivo:
            datos_token = json.load(archivo)
            return datos_token["access_token"]
    except FileNotFoundError:
        return None

def calcular_dias_ausente():
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp FROM interacciones ORDER BY timestamp DESC LIMIT 1")
            ultima = cursor.fetchone()
        
        if ultima:
            fecha_ultima = datetime.strptime(ultima[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=BOGOTA)
            dias = (datetime.now(BOGOTA) - fecha_ultima).days
            return max(0, dias)
        return 0
    except Exception as e:
        logging.exception("Error calculando dias ausente: %s", e)
        return 0

def contar_intentos_hoy():
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM interacciones 
                WHERE accion IN ('intento', 'afronto_ansiedad', 'completada', 'paso1_comprometido', 'exposicion_mirar') 
                AND date(timestamp) = ?
            """, (hoy_bogota_str(),))
            intentos = cursor.fetchone()[0]
        return intentos
    except Exception as e:
        logging.exception("Error contando intentos de hoy: %s", e)
        return 0

load_dotenv()

def contar_friccion_consecutiva(tarea_id: str):
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT accion FROM interacciones 
                WHERE tarea_id = ? AND date(timestamp) = ?
                ORDER BY timestamp DESC
            """, (tarea_id, hoy_bogota_str()))
            acciones = cursor.fetchall()
        
        friccion = 0
        for (acc,) in acciones:
            if acc in ['completada', 'avance_parcial', 'paso1_realizado']:
                break
            if acc in ['intento', 'afronto_ansiedad', 'pidio_ayuda', 'exposicion_mirar', 'paso1_comprometido']:
                friccion += 1
        return friccion
    except Exception as e:
        logging.exception("Error contando friccion consecutiva: %s", e)
        return 0

def fue_perdonada_recientemente(tarea_id: str) -> bool:
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM interacciones
                WHERE tarea_id = ? AND accion = 'perdonada'
                AND timestamp >= ?
            """, (tarea_id, hace_n_dias_bogota(7)))
            count = cursor.fetchone()[0]
        return count > 0
    except Exception as e:
        logging.exception("Error consultando perdon reciente: %s", e)
        return False

app = FastAPI(title="AtypicalTick API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _job_horario_estricto():
    logging.debug("JOB EJECUTADO")
    token = obtener_token()
    if not token:
        logging.debug("[scheduler] Sin token, se omite revision de horario estricto.")
        return
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    procesadas = procesar_horario_estricto_vencido(headers, {}, registrar_interaccion)
    if procesadas:
        logging.info("[scheduler] %s tarea(s) ciclicas marcadas como desconocidas (ocultas localmente).", procesadas)

scheduler = BackgroundScheduler()
scheduler.add_job(_job_horario_estricto, "interval", minutes=1, id="horario_estricto")
logging.debug("INICIANDO SCHEDULER")
logging.debug("Scheduler id: %s", id(scheduler))
scheduler.start()


def _parsear_fecha_ticktick_main(fecha_str: str):
    """
    Mismo parseo que usa gestion_horario_estricto._parsear_fecha_ticktick,
    duplicado aqui para no crear un import circular. Devuelve un datetime
    con tzinfo (normalmente UTC, segun lo que entrega TickTick), o None
    si no se pudo parsear.
    """
    try:
        fecha_limpia = re.sub(r'\.\d+', '', fecha_str)
        return datetime.strptime(fecha_limpia, "%Y-%m-%dT%H:%M:%S%z")
    except Exception as e:
        logging.exception("Error parseando fecha de TickTick: %s", e)
        return None


@app.get("/api/enfoque")
def obtener_tarea_enfoque(energia: str = "alta"):
    token = obtener_token()
    if not token: raise HTTPException(status_code=401)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    url_listas = "https://api.ticktick.com/open/v1/project"

    try:
        resp_listas = requests.get(url_listas, headers=headers, timeout=10)
        if resp_listas.status_code != 200: raise HTTPException(status_code=500)
    except requests.exceptions.RequestException as e:
        logging.exception("Error al obtener listas de TickTick: %s", e)
        raise HTTPException(status_code=503, detail="TickTick tardo demasiado en responder.")
        
    listas = resp_listas.json()
    mapa_carpetas = {lista['id']: lista['name'] for lista in listas}
    mapa_carpetas['inbox'] = "Inbox"

    todas_las_tareas = []
    for lista in listas:
        if lista.get('closed') == True or lista.get('isClosed') == True:
            continue
        nombre_lista = lista.get('name', '').lower()
        if nombre_lista in ['archivado', 'archived', 'archived lists', 'trash']:
            continue
        
        url_tareas = f"https://api.ticktick.com/open/v1/project/{lista['id']}/data"
        
        try:
            resp_tareas = requests.get(url_tareas, headers=headers, timeout=10)
            if resp_tareas.status_code == 200:
                todas_las_tareas.extend(resp_tareas.json().get('tasks', []))
            elif resp_tareas.status_code == 429:
                logging.warning("TickTick pidio frenar por Rate Limit en la lista %s", nombre_lista)
        except requests.exceptions.Timeout:
            logging.warning("TickTick tardo demasiado en la lista '%s'. Se omite por ahora.", nombre_lista)
        except requests.exceptions.RequestException as e:
            logging.exception("Error de conexion con TickTick en lista '%s': %s", nombre_lista, e)

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM interacciones WHERE accion='completada' AND date(timestamp) = ?", (hoy_bogota_str(),))
        completadas_hoy = cursor.fetchone()[0]
    
    necesita_calentamiento = completadas_hoy == 0
    tareas_validas = []
    info_horario_estricto = {}
    ahora = datetime.now(BOGOTA)
    hoy = ahora.date()
    dias_nombres = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    dia_actual = dias_nombres[ahora.weekday()]

    for tarea in todas_las_tareas:
        if tarea.get('status', 0) != 0:
            continue
        
        id_proy_tmp = tarea.get('projectId', 'inbox')
        nombre_carpeta_tmp = mapa_carpetas.get(id_proy_tmp, "Inbox")

        es_recurrente_tmp = bool(tarea.get('repeatFlag'))
        restricciones_tmp = clasificar_tarea(
            titulo=tarea.get('title', ''),
            etiquetas=tarea.get('tags', []),
            carpeta=nombre_carpeta_tmp,
            tiene_hora_especifica=not tarea.get('isAllDay', True)
        )
        es_horario_estricto_tmp = bool(
            restricciones_tmp.get('hora_importa') and not restricciones_tmp.get('ventana')
        )

        if es_horario_estricto_tmp and not tarea.get('isAllDay', True) and 'dueDate' in tarea:
            hora_programada_tmp = _parsear_fecha_ticktick_main(tarea['dueDate'])
            if hora_programada_tmp:
                es_salud_tmp = _es_critica_salud(tarea, nombre_carpeta_tmp)
                ventana = calcular_ventana_visibilidad(
                    restricciones_tmp,
                    es_recurrente=es_recurrente_tmp,
                    hora_programada=hora_programada_tmp,
                    reminders=tarea.get('reminders'),
                    ahora=ahora,
                    es_critica_salud=es_salud_tmp,
                )
                info_horario_estricto[tarea['id']] = {
                    "activo": ventana["es_horario_estricto_activo"],
                    "es_salud": es_salud_tmp,
                }
                if not ventana["visible"]:
                    continue

        tiene_fecha = 'dueDate' in tarea
        mostrar_ahora = True
        es_hoy_o_atrasada = False

        if tiene_fecha:
            fecha_str = tarea['dueDate']
            fecha_tarea = datetime.strptime(fecha_str[:10], "%Y-%m-%d").date()
            if fecha_tarea <= hoy:
                es_hoy_o_atrasada = True
                if not tarea.get('isAllDay', True) and tarea['id'] not in info_horario_estricto:
                    fecha_limpia = re.sub(r'\.\d+', '', fecha_str)
                    hora_tarea = datetime.strptime(fecha_limpia, "%Y-%m-%dT%H:%M:%S%z")
                    if hora_tarea.timestamp() > ahora.timestamp() + 3600:
                        mostrar_ahora = False

        if (not es_hoy_o_atrasada and tiene_fecha) or not mostrar_ahora: continue

        if energia == "baja":
            tags_lower = [t.lower() for t in tarea.get('tags', [])]
            id_proy = tarea.get('projectId', 'inbox')
            nombre_carpeta_t = mapa_carpetas.get(id_proy, "Inbox").lower()
            
            es_vital_o_facil = any(palabra in tags_lower for palabra in [
                "baja-energia", "energia-baja", "facil", "simple", "rutina", "medicine","Medicine", "medicina"
            ]) or "health" in nombre_carpeta_t or "salud" in nombre_carpeta_t
            
            if tarea.get('priority', 0) == 5 or es_vital_o_facil:
                tareas_validas.append(tarea)
        else:
            tareas_validas.append(tarea)
    
    def calcular_peso_psicologico(t):
        prio = t.get('priority', 0)
        dias_atraso = 0
        if 'dueDate' in t:
            fecha_t = datetime.strptime(t['dueDate'][:10], "%Y-%m-%d").date()
            if fecha_t < hoy: dias_atraso = (hoy - fecha_t).days
        
        id_proy_peso = t.get('projectId', 'inbox')
        nombre_carpeta_peso = mapa_carpetas.get(id_proy_peso, "Inbox")
        
        if es_horario_estricto_recurrente(t, nombre_carpeta_peso):
            dias_atraso = 0

        score = 0
        if necesita_calentamiento and energia == "alta": score = (prio * 10) - (dias_atraso * 5)
        elif not necesita_calentamiento and energia == "alta": score = -(prio * 10) - (dias_atraso * 20)
        else: 
            score = prio * 5
            if dias_atraso > 0 and prio == 5: score -= 50

        info = info_horario_estricto.get(t.get('id'))
        if info and info.get("activo"):
            score -= 100000

            if info.get("es_salud"):
                perdidas = contar_perdidas_consecutivas_salud(t.get('id'))
                if perdidas >= 2:
                    score -= 500

        return score

    dias_ausente = calcular_dias_ausente()
    modo_reingreso = dias_ausente > 7


    if modo_reingreso:
        def es_muy_atrasada(t):
            if 'dueDate' not in t:
                return False
            fecha_t = datetime.strptime(t['dueDate'][:10], "%Y-%m-%d").date()
            return (hoy - fecha_t).days > 7

        atrasadas = [t for t in tareas_validas if es_muy_atrasada(t)]
        recientes = [t for t in tareas_validas if not es_muy_atrasada(t)]
        atrasadas.sort(key=lambda t: t.get('priority', 0))
        tareas_validas = recientes + atrasadas[:1]

    tareas_validas.sort(key=calcular_peso_psicologico)
    intentos_hoy = contar_intentos_hoy()

    if not tareas_validas:
        return {"estado": "vacio", "mensaje": "Bandeja limpia por ahora!", "dias_ausente": dias_ausente}

    
    lista_formateada = []
    for t in tareas_validas:
        id_proy = t.get('projectId', 'inbox')
        nombre_carpeta = mapa_carpetas.get(id_proy, "Inbox")
        etiquetas = t.get('tags', [])
        
        lista_formateada.append({
            "id": t['id'],
            "titulo": t['title'],
            "descripcion": t.get('content', ''),
            "proyecto_id": t.get('projectId', 'inbox'),
            "carpeta": nombre_carpeta,
            "etiquetas": etiquetas,
            "prioridad": t.get('priority', 0),
            "perfil_clinico": analizar_perfil_clinico(nombre_carpeta, etiquetas),
            "friccion_consecutiva": contar_friccion_consecutiva(t['id']),
            "fue_auto_perdonada_antes": fue_perdonada_recientemente(t['id']),
            "patron_emocional": obtener_patron_contextual(nombre_carpeta, dia_actual),
            "es_horario_estricto_activo": bool(info_horario_estricto.get(t['id'], {}).get("activo"))
        })

    return {
        "estado": "enfoque",
        "tareas": lista_formateada,
        "fase": "calentamiento" if necesita_calentamiento else "trabajo_profundo",
        "estadisticas": {
            "dias_ausente": dias_ausente,
            "intentos_hoy": intentos_hoy
        }
    }

class PeticionFeedbackDiscrepancia(BaseModel):
    motivo_declarado: str
    energia: str
    intervencion_sugerida: str
    respuesta: str

@app.post("/api/feedback-discrepancia")
def feedback_discrepancia(datos: PeticionFeedbackDiscrepancia):
    registrar_feedback_discrepancia(
        datos.motivo_declarado, datos.energia, datos.intervencion_sugerida, datos.respuesta
    )
    return {"estado": "exito"}

class PeticionCorreccion(BaseModel):
    tarea_id: str
    tipo_decision: str
    valor_original: str
    correccion: str
    carpeta: str = "Inbox"

@app.post("/api/corregir-decision")
def corregir_decision(datos: PeticionCorreccion):
    registrar_correccion(datos.tarea_id, datos.tipo_decision, datos.valor_original, datos.correccion, datos.carpeta)
    return {"estado": "exito"}

@app.post("/api/corregir-perdon/{proyecto_id}/{tarea_id}")
def corregir_perdon(proyecto_id: str, tarea_id: str, tarea_nombre: str = "Desconocida", carpeta: str = "Inbox"):
    token = obtener_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    url_tarea = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}"
    try:
        tarea = requests.get(url_tarea, headers=headers, timeout=10).json()
        tarea['status'] = 0
        hoy = datetime.now(BOGOTA).date()
        if 'dueDate' in tarea and not tarea.get('isAllDay', True):
            hora_original = tarea['dueDate'][10:]
            tarea['dueDate'] = hoy.strftime("%Y-%m-%d") + hora_original
        else:
            tarea['dueDate'] = hoy.strftime("%Y-%m-%dT12:00:00+0000")
        requests.post(url_tarea, headers=headers, json=tarea, timeout=10)
    except requests.exceptions.RequestException as e:
        logging.exception("Error al corregir perdon en TickTick: %s", e)
        raise HTTPException(status_code=503, detail="TickTick tardo demasiado en responder.")

    registrar_correccion(tarea_id, "perdon_rutina", "perdonada", "era_critica", carpeta)
    registrar_interaccion(tarea_id, tarea_nombre, "desconocida", "correccion_perdon_revertida", "Usuario corrigio auto-perdon", carpeta)
    return {"estado": "exito"}

class PeticionRechazo(BaseModel):
    tarea_nombre: str = "Desconocida"
    energia: str = "desconocida"
    carpeta: str = "Inbox"
    intencion: str = "Sin intencion"

@app.post("/api/rechazar/{tarea_id}")
def rechazar_tarea(tarea_id: str, datos: PeticionRechazo):
    if detectar_riesgo(datos.intencion):
        return respuesta_crisis()
    registrar_interaccion(tarea_id, datos.tarea_nombre, datos.energia, "rechazada", datos.intencion, datos.carpeta)
    return {"estado": "exito"}

@app.post("/api/intento/{tarea_id}")
def registrar_intento_valiente(tarea_id: str, accion: str = "intento", tarea_nombre: str = "", energia: str = "desconocida", carpeta: str = "Inbox"):
    registrar_interaccion(tarea_id, tarea_nombre, energia, accion, None, carpeta)
    if accion in ('paso1_realizado', 'avance_parcial'):
        cerrar_prediccion_con_resultado(tarea_id, accion)
    return {"estado": "exito"}


# ─── CAMBIO: /api/liberar ahora detecta si la tarea es recurrente ───
@app.post("/api/liberar/{proyecto_id}/{tarea_id}")
def liberar_tarea(proyecto_id: str, tarea_id: str, tarea_nombre: str = "Desconocida",
                  energia: str = "desconocida", carpeta: str = "Inbox",
                  bloqueo_previo: str = "Ninguno", intervencion_usada: str = "Ninguna"):
    token = obtener_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Obtenemos los datos de la tarea ANTES de completarla para leer repeatFlag.
    # Si el GET falla (timeout, red), no bloqueamos la operacion principal:
    # simplemente asumimos que no es recurrente y seguimos.
    es_recurrente = False
    url_tarea = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}"
    try:
        resp_tarea = requests.get(url_tarea, headers=headers, timeout=10)
        if resp_tarea.status_code == 200:
            tarea_data = resp_tarea.json()
            es_recurrente = bool(tarea_data.get('repeatFlag'))
    except requests.exceptions.RequestException as e:
        logging.warning("No se pudo obtener datos de la tarea antes de completar (se asume no recurrente): %s", e)

    # Completar la tarea en TickTick.
    url_complete = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}/complete"
    respuesta = requests.post(url_complete, headers=headers, timeout=10)

    if respuesta.status_code == 200:
        registrar_interaccion(tarea_id, tarea_nombre, energia, "completada", None, carpeta)
        cerrar_prediccion_con_resultado(tarea_id, "completada")

        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sesiones_tarea (tarea_id, bloqueo_inicial, intervencion_usada, "
                "resultado_final, energia, carpeta, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (tarea_id, bloqueo_previo, intervencion_usada, "completada", energia,
                 carpeta, datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S"))
            )

        # Le decimos al frontend si era recurrente para que muestre
        # el mensaje explicativo correcto ("reaparece mañana porque
        # eso es lo que hacen los hábitos").
        return {"estado": "exito", "es_recurrente": es_recurrente}

    raise HTTPException(status_code=500)
# ────────────────────────────────────────────────────────────────────


class PeticionPosponer(BaseModel):
    tarea_nombre: str = "Desconocida"
    energia: str = "desconocida"
    carpeta: str = "Inbox"
    motivo_posponer: str = "Sin motivo"
    bloqueo_previo: str = "Ninguno"
    intervencion_usada: str = "Ninguna"

@app.post("/api/posponer/{proyecto_id}/{tarea_id}")
def posponer_tarea(proyecto_id: str, tarea_id: str, datos: PeticionPosponer):
    if detectar_riesgo(datos.motivo_posponer):
        return respuesta_crisis()

    token = obtener_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    url_tarea = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}"
    try:
        resp_tarea = requests.get(url_tarea, headers=headers, timeout=10)
        if resp_tarea.status_code != 200:
            raise HTTPException(status_code=502, detail="TickTick no devolvió la tarea correctamente.")
        tarea = resp_tarea.json()
    except requests.exceptions.RequestException as e:
        logging.exception("Error al obtener tarea para posponer: %s", e)
        raise HTTPException(status_code=503, detail="TickTick tardó demasiado en responder.")
        
    es_recurrente = bool(tarea.get('repeatFlag'))
    carpeta_lower = datos.carpeta.lower()
    titulo_lower = datos.tarea_nombre.lower()
    prioridad = tarea.get('priority', 0)
    tags_lower = [t.lower() for t in tarea.get('tags', [])]
    
    score_critico = 0
    if prioridad == 5: score_critico += 10
    if any(t in tags_lower for t in ["medicina", "medicine", "urgente"]): score_critico += 10
    if any(c in carpeta_lower for c in ["health", "salud", "finanzas", "banco", "pagos"]): score_critico += 2
    
    palabras_criticas = ["pagar", "impuesto", "tramite", "cita", "medico", "pastilla", "transferir"]
    for w in palabras_criticas:
        if w in titulo_lower: score_critico += 3
        
    if any(w in titulo_lower for w in ["aprender", "curso", "leer", "estudiar"]): score_critico -= 5

    if carpeta_fue_corregida_como_critica(datos.carpeta):
        score_critico += 10
    
    es_critica = score_critico >= 4
    accion_historial = "pospuesta"
    
    if es_recurrente and not es_critica:
        url_complete = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}/complete"
        requests.post(url_complete, headers=headers, timeout=10)
        accion_historial = "perdonada"
    else:
        hoy_local = datetime.now(BOGOTA).date()
        manana = hoy_local + timedelta(days=1)
        
        if 'dueDate' in tarea:
            if tarea.get('isAllDay', True):
                tarea['dueDate'] = manana.strftime("%Y-%m-%dT12:00:00+0000")
            else:
                hora_original = tarea['dueDate'][10:] 
                tarea['dueDate'] = manana.strftime("%Y-%m-%d") + hora_original
        else:
            tarea['dueDate'] = manana.strftime("%Y-%m-%dT12:00:00+0000")
            
        requests.post(url_tarea, headers=headers, json=tarea, timeout=10)
    
    registrar_interaccion(tarea_id, datos.tarea_nombre, datos.energia, accion_historial, datos.motivo_posponer, datos.carpeta)
    resultado_sesion = "avance_parcial" if "Avance Parcial" in datos.motivo_posponer else "abandono_consciente"
    cerrar_prediccion_con_resultado(tarea_id, resultado_sesion if accion_historial != "perdonada" else "completada")
    
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sesiones_tarea (tarea_id, bloqueo_inicial, intervencion_usada, resultado_final, energia, carpeta, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (tarea_id, datos.bloqueo_previo, datos.intervencion_usada, resultado_sesion, datos.energia, datos.carpeta, datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S")))
    return {"estado": "exito"}
       
class TareaNueva(BaseModel):
    texto: str

@app.post("/api/captura")
def captura_rapida(tarea: TareaNueva):
    if detectar_riesgo(tarea.texto):
        return respuesta_crisis()

    token = obtener_token()
    if not token:
        raise HTTPException(status_code=401, detail="No hay token de acceso")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    url_crear = "https://api.ticktick.com/open/v1/task"
    nueva_tarea = {"title": tarea.texto}

    respuesta = requests.post(url_crear, headers=headers, json=nueva_tarea, timeout=10)

    if respuesta.status_code == 200:
        return {"estado": "exito", "mensaje": "Capturada en el Inbox"}
    else:
        raise HTTPException(status_code=500, detail="Error al capturar la idea")

class PeticionPrediccion(BaseModel):
    tarea_id: str
    tarea_nombre: str = "Desconocida"
    prediccion: str
    energia: str = "desconocida"
    carpeta: str = "Inbox"

@app.post("/api/prediccion")
def guardar_prediccion(datos: PeticionPrediccion):
    if detectar_riesgo(datos.prediccion):
        return respuesta_crisis()
    registrar_prediccion(datos.tarea_id, datos.tarea_nombre, datos.prediccion, datos.energia, datos.carpeta)
    return {"estado": "exito"}

@app.get("/api/contrastes")
def ver_contrastes():
    return {"contrastes": obtener_contrastes_recientes(limite=5)}

class PeticionBloqueo(BaseModel):
    tarea_id: str = "ID_DESCONOCIDO"
    titulo_tarea: str
    descripcion_tarea: str = ""
    motivo: str
    energia: str = "desconocida"
    carpeta: str = ""
    etiquetas: list[str] = []
    patron_historico: str = None

@app.post("/api/desglose")
def desglose_magico(peticion: PeticionBloqueo):
    if detectar_riesgo(peticion.motivo):
        return respuesta_crisis()

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    url_gemini = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    motivo = peticion.motivo.lower()
    carpeta = peticion.carpeta.lower()
    titulo = peticion.titulo_tarea.lower()
    etiquetas_texto = " ".join([t.lower() for t in peticion.etiquetas])
    
    score_salud, score_burocracia, score_social = 0, 0, 0
    
    if any(c in carpeta for c in ["health", "salud"]): score_salud += 2
    if any(c in carpeta for c in ["finanzas", "banco"]): score_burocracia += 2
    if "medicina" in etiquetas_texto: score_salud += 5
    if "ansiedad" in etiquetas_texto: score_social += 3
    if "pago" in etiquetas_texto: score_burocracia += 3
    
    if any(w in titulo for w in ["pastilla", "medico", "meds", "cita medica"]): score_salud += 4
    if any(w in titulo for w in ["pagar", "transferir", "impuesto", "tramite"]): score_burocracia += 4
    if any(w in titulo for w in ["llamar", "escribir a", "responder", "correo a", "mensaje"]): score_social += 3
    
    if any(w in titulo for w in ["aprender", "curso", "leer", "estudiar"]): 
        score_burocracia -= 5
        score_social -= 5

    es_salud = score_salud >= 4
    es_burocracia = score_burocracia >= 4
    es_ansiedad_social = score_social >= 3
    
    metadata = json.dumps({"score_salud": score_salud, "score_buro": score_burocracia, "score_social": score_social})
    registrar_interaccion(peticion.tarea_id, peticion.titulo_tarea, peticion.energia, "afronto_ansiedad", peticion.motivo, peticion.carpeta, metadata_ia=metadata) 

    plantilla_psicologica = ""
    nombre_intervencion = ""
    
    if es_salud:
        nombre_intervencion = "Intervencion de Salud Fisica"
        plantilla_psicologica = "Paso 1: Pon el elemento (vaso/pastilla/telefono) frente a ti. Paso 2: Ejecuta el movimiento fisico basico sin pensarlo. Paso 3: Marca como completado."
    elif es_burocracia:
        nombre_intervencion = "Reduccion de Incertidumbre Financiera"
        plantilla_psicologica = "Paso 1: Abre la pestana/app del banco o documento. Paso 2: Mira el monto exacto o la informacion que falta. Paso 3: Cierra la app o mantenla abierta. No tomes ninguna decision de pago aun."
    elif es_ansiedad_social:
        nombre_intervencion = "Exposicion Segura de Comunicacion"
        plantilla_psicologica = "Paso 1: Abre una app de notas donde sea imposible enviar el mensaje por error. Paso 2: Escribe un borrador intencionalmente malo sin formato. Paso 3: Copia el texto y acercate al chat de destino."
    elif "perfecto" in motivo or "listo" in motivo:
        nombre_intervencion = "Ruptura de Perfeccionismo"
        plantilla_psicologica = "Paso 1: Crea un documento o entorno intencionalmente desordenado. Paso 2: Identifica el unico requisito que hace que la tarea sea funcional. Paso 3: Escribe o haz la version mas mediocre posible de ese requisito."
    elif "empezar" in motivo or "abruma" in motivo or "grande" in motivo:
        nombre_intervencion = "Reduccion de Sobrecarga (Inercia)"
        plantilla_psicologica = "Paso 1: Ubica tu cuerpo frente al area de trabajo sin intencion de trabajar. Paso 2: Ejecuta una accion fisica absurda (ej. abrir solo 1 enlace). Paso 3: Haz una micro-unidad de trabajo y detente."
    elif "ansiedad" in motivo or "miedo" in motivo:
        nombre_intervencion = "Exposicion Conductual"
        plantilla_psicologica = "Paso 1: Observa la tarea o sus requisitos durante 30 segundos sin intervenir. Paso 2: Nombra en voz alta que te genera incomodidad. Paso 3: Haz un micro-movimiento de acercamiento."
    elif "agotado" in motivo or "energia" in motivo:
        historial_emocion = peticion.patron_historico.lower() if peticion.patron_historico else ""
        if "ansiedad" in historial_emocion or "miedo" in historial_emocion:
            nombre_intervencion = "Intervencion de Activacion Amigdalina"
            plantilla_psicologica = "Paso 1: Reconoce que la pesadez fisica viene de la tension, no del sueno. Paso 2: Haz un estiramiento de 5 segundos. Paso 3: Toca el elemento de la tarea y retirate si lo deseas."
        else:
            nombre_intervencion = "Acomodacion a Friccion Fisica (Agotamiento Real)"
            plantilla_psicologica = "Paso 1: No te muevas de donde estas. Usa tu dispositivo desde tu posicion actual. Paso 2: Haz la tarea a un 10% de su calidad normal. Paso 3: Detente despues de 2 minutos y decide conscientemente si continuas."
    elif "entiendo" in motivo or "claridad" in motivo:
        nombre_intervencion = "Despeje de Incertidumbre"
        plantilla_psicologica = "Paso 1: Localiza el punto exacto donde dejaste de entender. Paso 2: Escribe la duda especifica en 1 oracion. Paso 3: Identifica a quien le puedes preguntar o donde buscar."
    else: 
        nombre_intervencion = "Activacion Estandar"
        plantilla_psicologica = "Paso 1: Abre los recursos de la tarea. Paso 2: Ejecuta un movimiento motriz relacionado. Paso 3: Parar a los 2 minutos."

    insight_discrepancia = detectar_discrepancia_motivo(peticion.motivo, peticion.energia)
    mejor_intervencion, peor_intervencion = obtener_efectividad_historica(peticion.motivo, peticion.energia)

    instruccion_adaptativa = ""
    if mejor_intervencion:
        instruccion_adaptativa += f"\n- LO QUE SI FUNCIONA: El historial muestra que el usuario actua cuando usas '{mejor_intervencion}'. Replica esta estructura."
    if peor_intervencion:
        instruccion_adaptativa += f"\n- LO QUE LO BLOQUEA (EVITAR ESTO): Cuando usas '{peor_intervencion}', el usuario se paraliza o abandona. ALEJATE por completo de ese enfoque."

    prompt = f"""
    Eres un entrenador conductual. El usuario esta bloqueado:
    - Tarea: "{peticion.titulo_tarea}"
    - Motivo de friccion: "{peticion.motivo}"
    
    INTERVENCION BASE: {nombre_intervencion}
    Logica a seguir: {plantilla_psicologica}
    
    === APRENDIZAJE DEL SISTEMA (MUY IMPORTANTE) === {instruccion_adaptativa}
    =================================================
    
    INSTRUCCION CLINICA ESTRICTA (10% CONTEXTO, 90% CONDUCTA):
    1. CONTEXTO MINIMO: Usa maximo UNA oracion inicial para validar el motivo. (Ej: "Entiendo que organizar facturas abruma.").
    2. CERO REFLEXION: El sobreanalisis genera paralisis. Pide acciones fisicas directas.
    3. El paso 3 DEBE llamarse EXACTAMENTE "Accion de 30 segundos:" seguido de un micro-movimiento.
    
    Devuelve EXACTAMENTE este JSON:
    {{"pasos": ["Oracion de contexto. Paso motriz 1", "Paso motriz 2", "Accion de 30 segundos: [Tu instruccion]"]}}
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
    try:
        respuesta = requests.post(url_gemini, headers={"Content-Type": "application/json"}, json=payload, timeout=15)
        resultado = json.loads(respuesta.json()['candidates'][0]['content']['parts'][0]['text'])
        resultado["insight_discrepancia"] = insight_discrepancia
        resultado["nombre_intervencion"] = nombre_intervencion
        return resultado
    except Exception as e:
        return {
            "pasos": ["Abre la aplicacion o documento correspondiente.", "Lee la primera linea u observa el entorno.", "Detente a los 2 minutos y decide si continuar."],
            "insight_discrepancia": insight_discrepancia,
            "nombre_intervencion": nombre_intervencion
        }

@app.get("/api/historial")
def ver_historial():
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM interacciones ORDER BY timestamp DESC")
            filas = cursor.fetchall()
        
        return {"total": len(filas), "registros": filas}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer la base de datos: {str(e)}")

@app.get("/api/debug-sesiones")
def ver_sesiones():
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT bloqueo_inicial, intervencion_usada, resultado_final, energia FROM sesiones_tarea")
        sesiones = cursor.fetchall()
    return {"sesiones_registradas": sesiones}

@app.get("/api/metricas-clinicas")
def obtener_metricas_clinicas():
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sesiones_tarea WHERE bloqueo_inicial != 'Ninguno' AND resultado_final IN ('completada', 'avance_parcial')")
            recuperaciones_exitosas = cursor.fetchone()[0]
        
        return {
            "recuperaciones_exitosas": recuperaciones_exitosas,
            "mensaje": f"Has superado {recuperaciones_exitosas} bloqueos que parecian imposibles. Tu historial demuestra que los bloqueos no son permanentes." if recuperaciones_exitosas > 0 else ""
        }
    except Exception as e:
        logging.exception("Error obteniendo metricas clinicas: %s", e)
        return {"error": str(e)}

@app.get("/api/espejo-conductual")
def espejo_conductual():
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            hace_7_dias = hace_n_dias_bogota(7)

            cursor.execute("""
                SELECT accion, COUNT(*) FROM interacciones 
                WHERE timestamp >= ?
                GROUP BY accion
            """, (hace_7_dias,))
            acciones = dict(cursor.fetchall())

            cursor.execute("""
                SELECT COUNT(DISTINCT tarea_id) FROM interacciones 
                WHERE accion IN ('completada', 'avance_parcial', 'paso1_realizado') 
                AND tarea_id IN (
                    SELECT tarea_id FROM interacciones WHERE accion IN ('pospuesta', 'rechazada', 'abandono_consciente')
                )
            """)
            recuperaciones = cursor.fetchone()[0]

            cursor.execute("""
                SELECT tarea_id, accion, timestamp FROM interacciones
                WHERE timestamp >= ?
                ORDER BY tarea_id, timestamp ASC
            """, (hace_7_dias,))
            filas_friccion = cursor.fetchall()

            cursor.execute("""
                SELECT COUNT(DISTINCT date(timestamp)) FROM interacciones
                WHERE accion = 'autocuidado' AND timestamp >= ?
            """, (hace_7_dias,))
            dias_autocuidado = cursor.fetchone()[0]

            cursor.execute("""
                SELECT carpeta, COUNT(*) as total, 
                       SUM(CASE WHEN accion IN ('completada', 'avance_parcial', 'paso1_realizado') THEN 1 ELSE 0 END) as exitos
                FROM interacciones WHERE carpeta != 'Inbox' GROUP BY carpeta HAVING total > 3
                ORDER BY exitos DESC LIMIT 1
            """)
            datos_evidencia = cursor.fetchone()

        aproximaciones_reales = (
            acciones.get('exposicion_mirar', 0) +
            acciones.get('paso1_comprometido', 0) +
            acciones.get('paso1_realizado', 0) +
            acciones.get('avance_parcial', 0) +
            acciones.get('intento', 0) +
            acciones.get('afronto_ansiedad', 0)
        )

        transiciones_logradas = acciones.get('exposicion_mirar', 0) + acciones.get('paso1_comprometido', 0)

        bloqueos_atravesados = 0
        friccion_previa = {}
        for tarea_id, accion, ts_str in filas_friccion:
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                continue

            if accion in ('intento', 'afronto_ansiedad', 'pidio_ayuda', 'exposicion_mirar', 'paso1_comprometido'):
                friccion_previa[tarea_id] = ts
            elif accion in ('completada', 'avance_parcial', 'paso1_realizado'):
                inicio = friccion_previa.get(tarea_id)
                if inicio and ts.date() == inicio.date() and (ts - inicio) <= timedelta(hours=8):
                    bloqueos_atravesados += 1
                friccion_previa.pop(tarea_id, None)

        patron_detectado = None
        pospuestas = acciones.get('pospuesta', 0) + acciones.get('rechazada', 0)
        completadas = acciones.get('completada', 0)
        ayudas_ia = acciones.get('afronto_ansiedad', 0)

        if pospuestas > (completadas + 5):
            patron_detectado = {
                "tipo": "Ciclo de Evitacion",
                "icono": "🛡️",
                "mensaje": "Los datos muestran que has pospuesto frecuentemente esta semana. Posponer alivia el malestar por unas horas, pero el costo es que la friccion reaparece mañana. Considera usar la regla de 'solo mirar 30 segundos' para romper el ciclo."
            }
        elif ayudas_ia > 5 and completadas < 2:
            patron_detectado = {
                "tipo": "Exceso de Preparacion",
                "icono": "⚖️",
                "mensaje": "Has pedido mucha asistencia pero ejecutado poca accion fisica. Esto suele pasar cuando buscamos sentirnos 'completamente listos' antes de empezar. El objetivo hoy es dar un paso imperfecto o mediocre."
            }

        insight_profundo = None
        
        if datos_evidencia:
            tasa = round((datos_evidencia[2] / datos_evidencia[1]) * 100)
            if tasa >= 50:
                insight_profundo = f"La sensacion de dificultad suele ser alta con las tareas de '{datos_evidencia[0]}'. Sin embargo, tu historial clinico muestra que cuando decides dar el primer micro-paso fisico, logras avanzar o terminar el {tasa}% de las veces. Tienes la capacidad; el desafio es solo el momento de arranque."

        siguiente_experimento = generar_siguiente_experimento()
        contrastes_recientes = obtener_contrastes_recientes(limite=3)
        evidencia_acum = obtener_evidencia_acumulada()

        latencia, tendencia_latencia = calcular_latencia_activacion()
        desglose = calcular_desglose_aproximaciones()
        anti_patron = construir_anti_patron(patron_detectado)
        evidencia_retorno = construir_evidencia_retorno(insight_profundo, calcular_dias_ausente())

        return {
            "aproximaciones": aproximaciones_reales,
            "transiciones_logradas": transiciones_logradas,
            "recuperaciones": recuperaciones,
            "bloqueos_atravesados": bloqueos_atravesados,
            "dias_autocuidado": dias_autocuidado,
            "patron_detectado": patron_detectado,
            "anti_patron": anti_patron,
            "insight_profundo": insight_profundo,
            "evidencia_retorno": evidencia_retorno,
            "latencia": latencia,
            "tendencia_latencia": tendencia_latencia,
            "desglose": desglose,
            "siguiente_experimento": siguiente_experimento,
            "contrastes_recientes": contrastes_recientes,
            "evidencia_acumulada": evidencia_acum
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/autocuidado")
def registrar_autocuidado(datos: PeticionAutocuidado):
    registrar_interaccion(
        tarea_id="autocuidado",
        tarea_nombre=datos.tipo,
        energia="baja",
        accion="autocuidado",
        emocion=datos.tipo,
        carpeta="Autocuidado"
    )
    return {"estado": "exito"}

@app.get("/api/cierre-diario")
def obtener_tareas_cierre():
    token = obtener_token()
    if not token: raise HTTPException(status_code=401)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    url_listas = "https://api.ticktick.com/open/v1/project"
    try:
        resp_listas = requests.get(url_listas, headers=headers, timeout=10)
        listas = resp_listas.json()
    except requests.exceptions.RequestException as e:
        logging.exception("Error obteniendo listas para cierre diario: %s", e)
        raise HTTPException(status_code=503, detail="Error con TickTick")

    mapa_carpetas = {lista['id']: lista['name'] for lista in listas}
    mapa_carpetas['inbox'] = "Inbox"

    tareas_cierre = []
    ahora = datetime.now(BOGOTA)
    hoy = ahora.date()

    for lista in listas:
        if lista.get('closed') or lista.get('isClosed'): continue
        nombre_lista = lista.get('name', '').lower()
        if nombre_lista in ['archivado', 'archived', 'trash']: continue
        
        try:
            url_tareas = f"https://api.ticktick.com/open/v1/project/{lista['id']}/data"
            resp_tareas = requests.get(url_tareas, headers=headers, timeout=10)
            if resp_tareas.status_code == 200:
                todas_las_tareas = resp_tareas.json().get('tasks', [])
                
                for t in todas_las_tareas:
                    if t.get('status', 0) != 0: continue
                    
                    if 'dueDate' in t:
                        fecha_tarea = datetime.strptime(t['dueDate'][:10], "%Y-%m-%d").date()
                        es_hoy = fecha_tarea == hoy
                        es_atrasada_importante = (fecha_tarea < hoy) and (t.get('priority', 0) > 0)
                        
                        if es_hoy or es_atrasada_importante:
                            id_proy = t.get('projectId', 'inbox')
                            tareas_cierre.append({
                                "id": t['id'],
                                "titulo": t['title'],
                                "proyecto_id": id_proy,
                                "carpeta": mapa_carpetas.get(id_proy, "Inbox"),
                                "es_atrasada": fecha_tarea < hoy,
                                "es_rutina": bool(t.get('repeatFlag'))
                            })
        except requests.exceptions.RequestException as e:
            logging.exception("Error obteniendo tareas de cierre para lista %s: %s", lista.get('id'), e)
            continue

    tareas_cierre.sort(key=lambda x: (x['es_atrasada'], x['titulo']))

    return {"tareas": tareas_cierre[:5]}

@app.post("/api/completar-retroactivo/{proyecto_id}/{tarea_id}")
def completar_retroactivo(proyecto_id: str, tarea_id: str, tarea_nombre: str = "Desconocida", carpeta: str = "Inbox"):
    """Registra una tarea que el usuario hizo en la vida real, pero olvidó marcar en la app"""
    token = obtener_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    url = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}/complete"
    requests.post(url, headers=headers, timeout=10)
    
    registrar_interaccion(tarea_id, tarea_nombre, "desconocida", "completada_fuera_app", "Cierre Diario", carpeta)
    cerrar_prediccion_con_resultado(tarea_id, "completada_fuera_app")
    
    return {"estado": "exito"}

@app.post("/api/posponer-cierre/{proyecto_id}/{tarea_id}")
def posponer_cierre(proyecto_id: str, tarea_id: str, tarea_nombre: str = "Desconocida", carpeta: str = "Inbox"):
    token = obtener_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    url_tarea = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}"
    try:
        resp_tarea = requests.get(url_tarea, headers=headers, timeout=10)
        if resp_tarea.status_code != 200:
            raise HTTPException(status_code=502, detail="TickTick no devolvió la tarea correctamente.")
        tarea = resp_tarea.json()
    except requests.exceptions.RequestException as e:
        logging.exception("Error al obtener tarea para posponer cierre: %s", e)
        raise HTTPException(status_code=503, detail="TickTick tardó demasiado en responder.")

    
    hoy_local = datetime.now(BOGOTA).date()
    manana = hoy_local + timedelta(days=1)
    
    if 'dueDate' in tarea:
        if tarea.get('isAllDay', True):
            tarea['dueDate'] = manana.strftime("%Y-%m-%dT12:00:00+0000")
        else:
            hora_original = tarea['dueDate'][10:] 
            tarea['dueDate'] = manana.strftime("%Y-%m-%d") + hora_original
            
    requests.post(url_tarea, headers=headers, json=tarea, timeout=10)
    
    registrar_interaccion(tarea_id, tarea_nombre, "desconocida", "pospuesta_cierre", "Sinceridad Nocturna", carpeta)
    return {"estado": "exito"}

@app.post("/api/olvido-cierre/{proyecto_id}/{tarea_id}")
def olvido_cierre(proyecto_id: str, tarea_id: str, tarea_nombre: str = "Desconocida", carpeta: str = "Inbox"):
    """El usuario no recuerda si lo hizo. Se reprograma pacíficamente y se registra el fallo de memoria."""
    token = obtener_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    url_tarea = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}"
    try:
        tarea = requests.get(url_tarea, headers=headers, timeout=10).json()
        
        hoy_local = datetime.now(BOGOTA).date()
        manana = hoy_local + timedelta(days=1)
        
        if 'dueDate' in tarea:
            if tarea.get('isAllDay', True):
                tarea['dueDate'] = manana.strftime("%Y-%m-%dT12:00:00+0000")
            else:
                hora_original = tarea['dueDate'][10:] 
                tarea['dueDate'] = manana.strftime("%Y-%m-%d") + hora_original
                
        requests.post(url_tarea, headers=headers, json=tarea, timeout=10)
    except requests.exceptions.RequestException as e:
        logging.exception("Error reprogramando tarea olvidada en cierre diario: %s", e)
    
    registrar_interaccion(tarea_id, tarea_nombre, "desconocida", "no_recuerda", "Cierre Diario", carpeta)
    return {"estado": "exito"}

@app.get("/api/test-horario")
def test_horario():
    token = obtener_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    return {
        "procesadas": procesar_horario_estricto_vencido(
            headers,
            {},
            registrar_interaccion
        )
    }