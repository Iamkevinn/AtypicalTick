# main.py - Backend de AtypicalTick con FastAPI
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import requests
import re
from datetime import datetime, timedelta 
from dotenv import load_dotenv
import os
import sqlite3
import random

def add_column_if_not_exists(cursor, table, col_name, col_type):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    if col_name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")

def init_db():
    conn = sqlite3.connect('atypical_data.db')
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

    # Actualizaciones seguras del schema
    add_column_if_not_exists(cursor, "interacciones", "dia_semana", "TEXT")
    add_column_if_not_exists(cursor, "interacciones", "carpeta", "TEXT")
    add_column_if_not_exists(cursor, "interacciones", "etiquetas", "TEXT")
    add_column_if_not_exists(cursor, "interacciones", "metadata_ia", "TEXT")
    add_column_if_not_exists(cursor, "sesiones_tarea", "energia", "TEXT")
    add_column_if_not_exists(cursor, "sesiones_tarea", "carpeta", "TEXT")
    
    conn.commit()
    conn.close()

# Nueva función para registrar todo lo que hace el usuario
def registrar_interaccion(tarea_id: str, tarea_nombre: str, energia: str, accion: str, emocion: str = None, carpeta: str = "Inbox", etiquetas: str = "", metadata_ia: str = ""):
    try:
        ahora = datetime.now()
        hora_actual = ahora.hour
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        dia_semana = dias[ahora.weekday()]

        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO interacciones (tarea_id, tarea_nombre, energia, emocion_motivo, accion, hora, dia_semana, carpeta, etiquetas, metadata_ia) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tarea_id, tarea_nombre, energia, emocion, accion, hora_actual, dia_semana, carpeta, etiquetas, metadata_ia))
        conn.commit()
        conn.close()
    except Exception as e:
        print("🚨 Error al guardar interacción:", e)
        
init_db()

# ---------------------------------------------------------
# MOTOR CLÍNICO v2: Perfil Dinámico y Reanclaje
# ---------------------------------------------------------
def analizar_perfil_clinico(carpeta: str, etiquetas: list):
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        
        # Convertimos la lista de etiquetas a un texto para buscarlo (ej. "urgente, trabajo")
        etiquetas_str = ",".join(etiquetas).lower() if etiquetas else "sin_etiquetas"

        # [MODIFICADO]: Busca si esta carpeta O estas etiquetas generan problemas
        cursor.execute("""
            SELECT emocion_motivo, COUNT(*) FROM interacciones 
            WHERE (carpeta = ? OR (etiquetas != '' AND ? LIKE '%' || etiquetas || '%'))
            AND emocion_motivo IS NOT NULL 
            AND timestamp >= datetime('now', '-30 days') 
            GROUP BY emocion_motivo ORDER BY COUNT(*) DESC
        """, (carpeta, etiquetas_str))
        
        resultados = cursor.fetchall()
        conn.close()

        if not resultados: return {"dominante": None, "perfil": "desconocido"}
        
        emocion_principal = resultados[0][0].lower()
        if "ansiedad" in emocion_principal or "miedo" in emocion_principal:
            return {"dominante": emocion_principal, "perfil": "evitacion"}
        elif "agotado" in emocion_principal or "energía" in emocion_principal:
            return {"dominante": emocion_principal, "perfil": "agotamiento"}
        elif "entiendo" in emocion_principal or "claridad" in emocion_principal:
            return {"dominante": emocion_principal, "perfil": "falta_claridad"}
        else:
            return {"dominante": emocion_principal, "perfil": "sobrecarga"}
    except: 
        return {"dominante": None, "perfil": "desconocido"}

# [NUEVO]: Extraemos la "Tasa de Éxito" de cada intervención de la IA según el bloqueo
def obtener_efectividad_historica(motivo_bloqueo: str, energia_actual: str):
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT intervencion_usada, 
                   COUNT(*) as total_veces, 
                   SUM(CASE WHEN resultado_final IN ('completada', 'avance_parcial', 'paso1_realizado') THEN 1 ELSE 0 END) as exitos_movimiento,
                   SUM(CASE WHEN resultado_final IN ('abandono_consciente', 'pospuesta', 'rechazada') THEN 1 ELSE 0 END) as fallos
            FROM sesiones_tarea 
            WHERE bloqueo_inicial = ? AND energia = ?
            GROUP BY intervencion_usada
        """, (motivo_bloqueo, energia_actual))
        
        resultados = cursor.fetchall()
        conn.close()
        
        mejor_intervencion, peor_intervencion = None, None
        mejor_tasa, peor_tasa = -1, -1

        for fila in resultados:
            intervencion, total, exitos, fallos = fila[0], fila[1], (fila[2] or 0), (fila[3] or 0)
            
            tasa_exito = round((exitos / total) * 100)
            tasa_fallo = round((fallos / total) * 100)
            
            # EL CAMBIO CRÍTICO: Muestra mínima estadística >= 5
            if total >= 5 and tasa_exito > mejor_tasa and tasa_exito >= 50:
                mejor_tasa = tasa_exito
                mejor_intervencion = intervencion
                
            if total >= 5 and tasa_fallo > peor_tasa and tasa_fallo >= 50:
                peor_tasa = tasa_fallo
                peor_intervencion = intervencion
            
        return mejor_intervencion, peor_intervencion
    except Exception as e:
        return None, None
        
# ---------------------------------------------------------
# MOTOR CLÍNICO 2: Reconocimiento de Patrones Emocionales
# ---------------------------------------------------------
def obtener_patron_contextual(carpeta: str, dia_semana: str):
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        # Buscamos qué le pasa a este usuario CON ESTA CARPETA EN ESTE DÍA ESPECÍFICO
        cursor.execute("""
            SELECT emocion_motivo, COUNT(*) as frec FROM interacciones 
            WHERE carpeta = ? AND dia_semana = ? AND emocion_motivo IS NOT NULL AND emocion_motivo != ''
            GROUP BY emocion_motivo ORDER BY frec DESC LIMIT 1
        """, (carpeta, dia_semana))
        resultado = cursor.fetchone()
        
        # Si no hay datos de ese día, buscamos el patrón general de esa carpeta
        if not resultado:
            cursor.execute("""
                SELECT emocion_motivo, COUNT(*) as frec FROM interacciones 
                WHERE carpeta = ? AND emocion_motivo IS NOT NULL AND emocion_motivo != ''
                GROUP BY emocion_motivo ORDER BY frec DESC LIMIT 1
            """, (carpeta,))
            resultado = cursor.fetchone()
            
        conn.close()
        return resultado[0] if resultado else None
    except: return None
    
def obtener_token():
    try:
        with open(".token-oauth", "r") as archivo:
            datos_token = json.load(archivo)
            return datos_token["access_token"]
    except FileNotFoundError:
        return None

def calcular_dias_ausente():
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp FROM interacciones ORDER BY timestamp DESC LIMIT 1")
        ultima = cursor.fetchone()
        conn.close()
        
        if ultima:
            fecha_ultima = datetime.strptime(ultima[0], "%Y-%m-%d %H:%M:%S")
            # Usamos utcnow en lugar de now para estar en la misma zona horaria que SQLite
            dias = (datetime.utcnow() - fecha_ultima).days 
            return max(0, dias) # <-- La protección clave
        return 0
    except: return 0

def contar_intentos_hoy():
    # Depresión: Las pequeñas victorias cuentan (abrir, pedir ayuda, intentar)
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM interacciones 
            WHERE accion IN ('intento', 'afronto_ansiedad', 'completada') 
            AND date(timestamp) = date('now')
        """)
        intentos = cursor.fetchone()[0]
        conn.close()
        return intentos
    except: return 0

load_dotenv()

# NUEVO: Cuenta FRICCIÓN CONSECUTIVA, no intentos totales
def contar_friccion_consecutiva(tarea_id: str):
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        # Traemos todas las acciones de hoy para esta tarea, desde la más reciente
        cursor.execute("""
            SELECT accion FROM interacciones 
            WHERE tarea_id = ? AND date(timestamp) = date('now')
            ORDER BY timestamp DESC
        """, (tarea_id,))
        acciones = cursor.fetchall()
        conn.close()
        
        friccion = 0
        for (acc,) in acciones:
            # 1. SOLO LA ACCIÓN FÍSICA REAL rompe la racha de fricción
            if acc in ['completada', 'avance_parcial', 'paso1_realizado']:
                break
            
            # 2. "Orbitar" (mirar o comprometerse pero no hacer) sigue sumando fricción
            if acc in ['intento', 'afronto_ansiedad', 'pidio_ayuda', 'exposicion_mirar', 'paso1_comprometido']:
                friccion += 1
                
        return friccion
    except: return 0

app = FastAPI(title="AtypicalTick API")

# Esto es VITAL para que tu futuro frontend en React pueda hablar con este backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción se cambia por localhost:3000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Añadimos un parámetro a la URL: ?energia=alta o ?energia=baja
@app.get("/api/enfoque")
def obtener_tarea_enfoque(energia: str = "alta"):
    token = obtener_token()
    if not token: raise HTTPException(status_code=401)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    url_listas = "https://api.ticktick.com/open/v1/project"
    resp_listas = requests.get(url_listas, headers=headers)
    if resp_listas.status_code != 200: raise HTTPException(status_code=500)
        
    listas = resp_listas.json()
    mapa_carpetas = {lista['id']: lista['name'] for lista in listas}
    mapa_carpetas['inbox'] = "Inbox"

    todas_las_tareas = []
    for lista in listas:
        # 🚫 FIX: Ignorar carpetas que TickTick marca como cerradas
        if lista.get('closed') == True or lista.get('isClosed') == True:
            continue
            
        # 🚫 FIX: Ignorar si la carpeta se llama explícitamente "Archivado"
        nombre_lista = lista.get('name', '').lower()
        if nombre_lista in ['archivado', 'archived', 'archived lists', 'trash']:
            continue
            
        url_tareas = f"https://api.ticktick.com/open/v1/project/{lista['id']}/data"
        resp_tareas = requests.get(url_tareas, headers=headers)
        if resp_tareas.status_code == 200:
            todas_las_tareas.extend(resp_tareas.json().get('tasks', []))

    conn = sqlite3.connect('atypical_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM interacciones WHERE accion='completada' AND date(timestamp) = date('now')")
    completadas_hoy = cursor.fetchone()[0]
    conn.close()
    
    necesita_calentamiento = completadas_hoy == 0
    tareas_validas = []
    ahora = datetime.now()
    hoy = ahora.date()

    for tarea in todas_las_tareas:
        # 👻 EL MATAFANTASMAS: Si el estatus no es 0 (pendiente), la ignoramos por completo
        if tarea.get('status', 0) != 0:
            continue

        tiene_fecha = 'dueDate' in tarea
        mostrar_ahora = True
        es_hoy_o_atrasada = False

        if tiene_fecha:
            fecha_str = tarea['dueDate']
            fecha_tarea = datetime.strptime(fecha_str[:10], "%Y-%m-%d").date()
            if fecha_tarea <= hoy:
                es_hoy_o_atrasada = True
                if not tarea.get('isAllDay', True):
                    fecha_limpia = re.sub(r'\.\d+', '', fecha_str)
                    hora_tarea = datetime.strptime(fecha_limpia, "%Y-%m-%dT%H:%M:%S%z")
                    if hora_tarea.timestamp() > ahora.timestamp() + 3600:
                        mostrar_ahora = False

        if (not es_hoy_o_atrasada and tiene_fecha) or not mostrar_ahora: continue

        if energia == "baja":
            tags_lower = [t.lower() for t in tarea.get('tags', [])]
            id_proy = tarea.get('projectId', 'inbox')
            nombre_carpeta_t = mapa_carpetas.get(id_proy, "Inbox").lower()
            
            # Es fácil O es de salud/medicina
            es_vital_o_facil = any(palabra in tags_lower for palabra in [
                "baja-energia", "energia-baja", "facil", "simple", "rutina", "medicine", "medicina"
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
        
        score = 0
        if necesita_calentamiento and energia == "alta": score = (prio * 10) - (dias_atraso * 5)
        elif not necesita_calentamiento and energia == "alta": score = -(prio * 10) - (dias_atraso * 20)
        else: 
            score = prio * 5
            if dias_atraso > 0 and prio == 5: score -= 50
        return score

    tareas_validas.sort(key=calcular_peso_psicologico)

    dias_ausente = calcular_dias_ausente()
    intentos_hoy = contar_intentos_hoy()

    if not tareas_validas:
        return {"estado": "vacio", "mensaje": "✨ ¡Bandeja limpia por ahora!", "dias_ausente": dias_ausente}

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
            "friccion_consecutiva": contar_friccion_consecutiva(t['id'])
        })

    return {
        "estado": "enfoque",
        "tareas": lista_formateada, # <-- [MODIFICADO] Enviamos el arreglo completo
        "fase": "calentamiento" if necesita_calentamiento else "trabajo_profundo",
        "estadisticas": {
            "dias_ausente": dias_ausente,
            "intentos_hoy": intentos_hoy
        }
    }



# (Tus funciones de /liberar y /posponer siguen exactamente igual)
# --- RUTAS DE ACCIÓN ---

# [NUEVO]: Modelo para recibir la intención de rechazo
class PeticionRechazo(BaseModel):
    tarea_nombre: str = "Desconocida"
    energia: str = "desconocida"
    carpeta: str = "Inbox"
    intencion: str = "Sin intencion"

# [MODIFICADO]: Ahora recibe el JSON y guarda la "intencion" en la columna "emocion_motivo"
@app.post("/api/rechazar/{tarea_id}")
def rechazar_tarea(tarea_id: str, datos: PeticionRechazo):
    registrar_interaccion(tarea_id, datos.tarea_nombre, datos.energia, "rechazada", datos.intencion, datos.carpeta)
    return {"estado": "exito"}

@app.post("/api/intento/{tarea_id}")
def registrar_intento_valiente(tarea_id: str, accion: str = "intento", tarea_nombre: str = "", energia: str = "desconocida", carpeta: str = "Inbox"):    # NUEVO: Guarda cuando el usuario intenta dar el paso 1 (Victoria Oculta)
    registrar_interaccion(tarea_id, tarea_nombre, energia, accion, None, carpeta)
    return {"estado": "exito"}

@app.post("/api/liberar/{proyecto_id}/{tarea_id}")
def liberar_tarea(proyecto_id: str, tarea_id: str, tarea_nombre: str = "Desconocida", energia: str = "desconocida", carpeta: str = "Inbox", bloqueo_previo: str = "Ninguno"):
    token = obtener_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    respuesta = requests.post(f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}/complete", headers=headers)
    
    if respuesta.status_code == 200:
        registrar_interaccion(tarea_id, tarea_nombre, energia, "completada", None, carpeta)
        
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        # NUEVO: Guardamos la carpeta como contexto
        cursor.execute("INSERT INTO sesiones_tarea (tarea_id, bloqueo_inicial, intervencion_usada, resultado_final, energia, carpeta) VALUES (?, ?, ?, ?, ?, ?)",
              (tarea_id, bloqueo_previo, "Desglose IA" if bloqueo_previo != "Ninguno" else "Ninguna", "completada", energia, carpeta))
        conn.commit()
        conn.close()
        return {"estado": "exito"}
    raise HTTPException(status_code=500)

# NUEVO: Modelo para recibir los datos de posponer conscientemente
class PeticionPosponer(BaseModel):
    tarea_nombre: str = "Desconocida"
    energia: str = "desconocida"
    carpeta: str = "Inbox"
    motivo_posponer: str = "Sin motivo"
    bloqueo_previo: str = "Ninguno" # Para saber si pospuso DESPUÉS de pedir ayuda a la IA

@app.post("/api/posponer/{proyecto_id}/{tarea_id}")
def posponer_tarea(proyecto_id: str, tarea_id: str, datos: PeticionPosponer):
    token = obtener_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    url_tarea = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}"
    tarea = requests.get(url_tarea, headers=headers).json()
    
    es_recurrente = bool(tarea.get('repeatFlag'))
    carpeta_lower = datos.carpeta.lower()
    titulo_lower = datos.tarea_nombre.lower()
    prioridad = tarea.get('priority', 0)
    tags_lower = [t.lower() for t in tarea.get('tags', [])]
    
    # 🧠 SISTEMA DE SCORE: CRITICIDAD
    score_critico = 0
    
    # Prioridad explícita del usuario
    if prioridad == 5: score_critico += 10
    if any(t in tags_lower for t in ["medicina", "medicine", "urgente"]): score_critico += 10
    
    # Pistas de carpeta
    if any(c in carpeta_lower for c in ["health", "salud", "finanzas", "banco", "pagos"]): score_critico += 2
    
    # Confirmaciones de título
    palabras_criticas = ["pagar", "impuesto", "trámite", "tramite", "cita", "médico", "pastilla", "transferir"]
    for w in palabras_criticas:
        if w in titulo_lower: score_critico += 3
        
    # ANTI FALSOS POSITIVOS (Restamos puntos si es aprendizaje)
    if any(w in titulo_lower for w in ["aprender", "curso", "leer", "estudiar"]): score_critico -= 5
    
    # Umbral de criticidad (Si alcanza 4 o más, no se perdona sola)
    es_critica = score_critico >= 4
    
    accion_historial = "pospuesta"
    
    if es_recurrente and not es_critica:
        # Rutina perdonable
        url_complete = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}/complete"
        requests.post(url_complete, headers=headers)
        accion_historial = "perdonada"
    else:
        # Obligación o Crítica
        hoy_local = datetime.now().date()
        manana = hoy_local + timedelta(days=1)
        
        if 'dueDate' in tarea:
            if tarea.get('isAllDay', True):
                tarea['dueDate'] = manana.strftime("%Y-%m-%dT12:00:00+0000")
            else:
                hora_original = tarea['dueDate'][10:] 
                tarea['dueDate'] = manana.strftime("%Y-%m-%d") + hora_original
        else:
            tarea['dueDate'] = manana.strftime("%Y-%m-%dT12:00:00+0000")
            
        requests.post(url_tarea, headers=headers, json=tarea)
    
    registrar_interaccion(tarea_id, datos.tarea_nombre, datos.energia, accion_historial, datos.motivo_posponer, datos.carpeta)
    resultado_sesion = "avance_parcial" if "Avance Parcial" in datos.motivo_posponer else "abandono_consciente"
    
    conn = sqlite3.connect('atypical_data.db')
    cursor = conn.cursor()
    # NUEVO: Guardamos la carpeta como contexto
    cursor.execute("INSERT INTO sesiones_tarea (tarea_id, bloqueo_inicial, intervencion_usada, resultado_final, energia, carpeta) VALUES (?, ?, ?, ?, ?, ?)",
            (tarea_id, datos.bloqueo_previo, "Desglose IA" if datos.bloqueo_previo != "Ninguno" else "Ninguna", resultado_sesion, datos.energia, datos.carpeta))
    conn.commit()
    conn.close()
    return {"estado": "exito"}
       
# Creamos el modelo para recibir el texto de React
class TareaNueva(BaseModel):
    texto: str

@app.post("/api/captura")
def captura_rapida(tarea: TareaNueva):
    token = obtener_token()
    if not token:
        raise HTTPException(status_code=401, detail="No hay token de acceso")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # API oficial de TickTick para crear tareas (si no le pasas projectId, va al Inbox)
    url_crear = "https://api.ticktick.com/open/v1/task"
    
    nueva_tarea = {
        "title": tarea.texto
    }

    respuesta = requests.post(url_crear, headers=headers, json=nueva_tarea)

    if respuesta.status_code == 200:
        return {"estado": "exito", "mensaje": "Capturada en el Inbox"}
    else:
        raise HTTPException(status_code=500, detail="Error al capturar la idea")
    
# ---------------------------------------------------------
# IA: Desglose Clínico con Plantillas Psicológicas (Evolucionado)
# ---------------------------------------------------------

class PeticionBloqueo(BaseModel):
    tarea_id: str = "ID_DESCONOCIDO" # <-- Agregamos el ID
    titulo_tarea: str
    descripcion_tarea: str = ""
    motivo: str
    energia: str = "desconocida"
    carpeta: str = ""
    etiquetas: list[str] = []
    patron_historico: str = None # <-- NUEVO: Recibimos la memoria de React

@app.post("/api/desglose")
def desglose_magico(peticion: PeticionBloqueo):
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    url_gemini = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    motivo = peticion.motivo.lower()
    carpeta = peticion.carpeta.lower()
    titulo = peticion.titulo_tarea.lower()
    etiquetas_texto = " ".join([t.lower() for t in peticion.etiquetas])
    
    # 🧠 SISTEMA DE SCORE (HIPÓTESIS)
    score_salud, score_burocracia, score_social = 0, 0, 0
    
    if any(c in carpeta for c in ["health", "salud"]): score_salud += 2
    if any(c in carpeta for c in ["finanzas", "banco"]): score_burocracia += 2
    if "medicina" in etiquetas_texto: score_salud += 5
    if "ansiedad" in etiquetas_texto: score_social += 3
    if "pago" in etiquetas_texto: score_burocracia += 3
    
    if any(w in titulo for w in ["pastilla", "médico", "meds", "cita médica"]): score_salud += 4
    if any(w in titulo for w in ["pagar", "transferir", "impuesto", "trámite"]): score_burocracia += 4
    if any(w in titulo for w in ["llamar", "escribir a", "responder", "correo a", "mensaje"]): score_social += 3
    
    if any(w in titulo for w in ["aprender", "curso", "leer", "estudiar"]): 
        score_burocracia -= 5
        score_social -= 5

    es_salud = score_salud >= 4
    es_burocracia = score_burocracia >= 4
    es_ansiedad_social = score_social >= 3
    
    # REGISTRAMOS LOS SCORES PARA ANALÍTICA FUTURA
    metadata = json.dumps({"score_salud": score_salud, "score_buro": score_burocracia, "score_social": score_social})
    registrar_interaccion(peticion.tarea_id, peticion.titulo_tarea, peticion.energia, "afronto_ansiedad", peticion.motivo, peticion.carpeta, metadata_ia=metadata) 

    plantilla_psicologica = ""
    nombre_intervencion = ""
    
    if es_salud:
        nombre_intervencion = "Intervención de Salud Física"
        plantilla_psicologica = "Paso 1: Pon el elemento (vaso/pastilla/teléfono) frente a ti. Paso 2: Ejecuta el movimiento físico básico sin pensarlo. Paso 3: Marca como completado."
    elif es_burocracia:
        nombre_intervencion = "Reducción de Incertidumbre Financiera"
        plantilla_psicologica = "Paso 1: Abre la pestaña/app del banco o documento. Paso 2: Mira el monto exacto o la información que falta. Paso 3: Cierra la app o manténla abierta. No tomes ninguna decisión de pago aún."
    elif es_ansiedad_social:
        nombre_intervencion = "Exposición Segura de Comunicación"
        plantilla_psicologica = "Paso 1: Abre una app de notas donde sea imposible enviar el mensaje por error. Paso 2: Escribe un borrador intencionalmente malo sin formato. Paso 3: Copia el texto y acércate al chat de destino."
    elif "perfecto" in motivo or "listo" in motivo:
        nombre_intervencion = "Ruptura de Perfeccionismo"
        plantilla_psicologica = "Paso 1: Crea un documento o entorno intencionalmente desordenado. Paso 2: Identifica el único requisito que hace que la tarea sea funcional. Paso 3: Escribe o haz la versión más mediocre posible de ese requisito."
    elif "empezar" in motivo or "abruma" in motivo or "grande" in motivo:
        nombre_intervencion = "Reducción de Sobrecarga (Inercia)"
        plantilla_psicologica = "Paso 1: Ubica tu cuerpo frente al área de trabajo sin intención de trabajar. Paso 2: Ejecuta una acción física absurda (ej. abrir solo 1 enlace). Paso 3: Haz una micro-unidad de trabajo y detente."
    elif "ansiedad" in motivo or "miedo" in motivo:
        nombre_intervencion = "Exposición Conductual"
        plantilla_psicologica = "Paso 1: Observa la tarea o sus requisitos durante 30 segundos sin intervenir. Paso 2: Nombra en voz alta qué te genera incomodidad. Paso 3: Haz un micro-movimiento de acercamiento."
    elif "agotado" in motivo or "energía" in motivo:
        historial_emocion = peticion.patron_historico.lower() if peticion.patron_historico else ""
        if "ansiedad" in historial_emocion or "miedo" in historial_emocion:
            nombre_intervencion = "Intervención de Activación Amigdalina"
            plantilla_psicologica = "Paso 1: Reconoce que la pesadez física viene de la tensión, no del sueño. Paso 2: Haz un estiramiento de 5 segundos. Paso 3: Toca el elemento de la tarea y retírate si lo deseas."
        else:
            nombre_intervencion = "Acomodación a Fricción Física (Agotamiento Real)"
            # [CORRECCIÓN PSICOLÓGICA]: Evita reforzar la huida automática
            plantilla_psicologica = "Paso 1: No te muevas de donde estás. Usa tu dispositivo desde tu posición actual. Paso 2: Haz la tarea a un 10% de su calidad normal. Paso 3: Detente después de 2 minutos y decide conscientemente si continúas."
    elif "entiendo" in motivo or "claridad" in motivo:
        nombre_intervencion = "Despeje de Incertidumbre"
        plantilla_psicologica = "Paso 1: Localiza el punto exacto donde dejaste de entender. Paso 2: Escribe la duda específica en 1 oración. Paso 3: Identifica a quién le puedes preguntar o dónde buscar."
    else: 
        nombre_intervencion = "Activación Estándar"
        plantilla_psicologica = "Paso 1: Abre los recursos de la tarea. Paso 2: Ejecuta un movimiento motriz relacionado. Paso 3: Parar a los 2 minutos."

    # --- [NUEVO] LA IA APRENDE DE TUS RESULTADOS ---
    # Obtenemos la mejor estrategia que le ha funcionado a ESTE usuario
    mejor_intervencion, peor_intervencion = obtener_efectividad_historica(peticion.motivo, peticion.energia)

    # REGLA 80/20: 80% Explotación (usar lo que sirve) / 20% Exploración (probar cosas nuevas)
    instruccion_adaptativa = ""
    if random.random() < 0.2:
        instruccion_adaptativa = "- MODO EXPLORACIÓN (20%): Ignora el historial esta vez. Usa la intervención base u otra que consideres mejor clínicamente. Queremos evaluar nuevas respuestas para evitar sesgos."
    else:
        if mejor_intervencion:
            instruccion_adaptativa += f"\n- LO QUE FUNCIONA (80%): El usuario actúa cuando usas '{mejor_intervencion}'. Replica esta estructura."
        if peor_intervencion:
            instruccion_adaptativa += f"\n- EVITAR (80%): Cuando usas '{peor_intervencion}' en este contexto, el usuario se paraliza. Aléjate de ese enfoque."

    prompt = f"""
    Eres un entrenador conductual. El usuario está bloqueado:
    - Tarea: "{peticion.titulo_tarea}"
    - Motivo de fricción: "{peticion.motivo}"
    
    INTERVENCIÓN BASE: {nombre_intervencion}
    Lógica a seguir: {plantilla_psicologica}
    
    === APRENDIZAJE DEL SISTEMA === 
    {instruccion_adaptativa}
    ===============================
    
    INSTRUCCIÓN CLÍNICA ESTRICTA (10% CONTEXTO, 90% CONDUCTA):
    1. CONTEXTO MÍNIMO: Usa máximo UNA oración inicial para validar el motivo.
    2. CERO REFLEXIÓN: Pide acciones físicas directas.
    3. El paso 3 DEBE llamarse EXACTAMENTE "Acción de 30 segundos:" seguido de un micro-movimiento.
    
    Devuelve EXACTAMENTE este JSON:
    {{"pasos": ["Oración de contexto. Paso motriz 1", "Paso motriz 2", "Acción de 30 segundos: [Tu instrucción]"]}}
    """

# ---------------------------------------------------------
# NUEVA RUTA PARA VER EL HISTORIAL CLÍNICO
# ---------------------------------------------------------
@app.get("/api/historial")
def ver_historial():
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM interacciones ORDER BY timestamp DESC")
        filas = cursor.fetchall()
        conn.close()
        
        return {"total": len(filas), "registros": filas}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer la base de datos: {str(e)}")

@app.get("/api/debug-sesiones")
def ver_sesiones():
    conn = sqlite3.connect('atypical_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT bloqueo_inicial, intervencion_usada, resultado_final, energia FROM sesiones_tarea")
    sesiones = cursor.fetchall()
    conn.close()
    return {"sesiones_registradas": sesiones}

# ---------------------------------------------------------
# ANALÍTICA CONDUCTUAL: Tasa de Recuperación
# ---------------------------------------------------------
@app.get("/api/metricas-clinicas")
def obtener_metricas_clinicas():
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM sesiones_tarea WHERE bloqueo_inicial != 'Ninguno' AND resultado_final IN ('completada', 'avance_parcial')")
        recuperaciones_exitosas = cursor.fetchone()[0]
        conn.close()
        
        return {
            "recuperaciones_exitosas": recuperaciones_exitosas,
            "mensaje": f"Has superado {recuperaciones_exitosas} bloqueos que parecían imposibles. Tu historial demuestra que los bloqueos no son permanentes." if recuperaciones_exitosas > 0 else ""
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/espejo-conductual")
def espejo_conductual():
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()

        # 1. DESGLOSE DE APROXIMACIONES
        cursor.execute("""
            SELECT accion, COUNT(*) FROM interacciones 
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY accion
        """)
        acciones = dict(cursor.fetchall())
        
        miradas = acciones.get('exposicion_mirar', 0)
        primeros_pasos = acciones.get('paso1_realizado', 0) + acciones.get('avance_parcial', 0)
        
        cursor.execute("""
            SELECT COUNT(DISTINCT tarea_id) FROM interacciones 
            WHERE accion IN ('completada', 'avance_parcial', 'paso1_realizado') 
            AND tarea_id IN (
                SELECT tarea_id FROM interacciones WHERE accion IN ('pospuesta', 'rechazada', 'abandono_consciente')
            )
        """)
        recuperaciones = cursor.fetchone()[0]

        # 2. CÁLCULO DE LATENCIA Y TENDENCIA (Los últimos 14 días separados en 2 semanas)
        cursor.execute("""
            SELECT tarea_id, accion, timestamp FROM interacciones 
            WHERE accion IN ('afronto_ansiedad', 'intento', 'exposicion_mirar', 'paso1_realizado', 'avance_parcial', 'completada')
            AND timestamp >= datetime('now', '-14 days')
            ORDER BY tarea_id, timestamp
        """)
        rows = cursor.fetchall()
        
        latencias_esta_semana = []
        latencias_semana_pasada = []
        inicios = {}
        ahora = datetime.now()
        
        for row in rows:
            t_id, acc, ts_str = row
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            if acc in ['afronto_ansiedad', 'intento', 'exposicion_mirar']:
                if t_id not in inicios:
                    inicios[t_id] = ts
            elif acc in ['paso1_realizado', 'avance_parcial', 'completada']:
                if t_id in inicios:
                    minutos = (ts - inicios[t_id]).total_seconds() / 60
                    if 0 < minutos < 1440:  # Máximo 24h
                        if (ahora - ts).days <= 7:
                            latencias_esta_semana.append(minutos)
                        else:
                            latencias_semana_pasada.append(minutos)
                    del inicios[t_id]
                    
        latencia_actual = round(sum(latencias_esta_semana) / len(latencias_esta_semana)) if latencias_esta_semana else None
        latencia_pasada = round(sum(latencias_semana_pasada) / len(latencias_semana_pasada)) if latencias_semana_pasada else None

        tendencia = None
        if latencia_actual and latencia_pasada:
            diff = latencia_pasada - latencia_actual
            if diff > 0:
                tendencia = f"↓ {diff} minutos menos que la sem. pasada. ¡Mejorando!"
            elif diff < 0:
                tendencia = f"↑ {abs(diff)} minutos más que la sem. pasada."

        # 3. IDENTIFICACIÓN DE ANTI-PATRONES (Con n >= 10 para significancia clínica)
        cursor.execute("""
            SELECT intervencion_usada, bloqueo_inicial, energia
            FROM sesiones_tarea 
            WHERE resultado_final IN ('abandono_consciente', 'pospuesta')
            GROUP BY intervencion_usada, bloqueo_inicial, energia 
            HAVING COUNT(*) >= 10
            ORDER BY COUNT(*) DESC LIMIT 1
        """)
        anti_patron = cursor.fetchone()
        
        mensaje_anti_patron = None
        if anti_patron and anti_patron[0] != 'Ninguna':
            intervencion_fallida, emocion_fallida, energia_fallida = anti_patron[0], anti_patron[1], anti_patron[2]
            mensaje_anti_patron = f"Se ha observado que el enfoque de '{intervencion_fallida}' tiende a congelarte cuando reportas '{emocion_fallida}' con energía {energia_fallida}. El sistema usará otras rutas a partir de ahora."

        # 4. EVIDENCIA EN LUGAR DE "IDENTIDAD"
        mensaje_evidencia = f"Durante los últimos 14 días, retomaste {recuperaciones} tareas después de haberlas abandonado. Esto indica una capacidad de recuperación observable en los datos, incluso cuando aparece evitación al principio." if recuperaciones > 0 else "Todavía estamos recopilando datos sobre tu capacidad de retorno a las tareas."

        conn.close()

        return {
            "desglose": {
                "miradas": miradas,
                "primeros_pasos": primeros_pasos,
                "retornos": recuperaciones
            },
            "latencia": latencia_actual,
            "tendencia_latencia": tendencia,
            "anti_patron": mensaje_anti_patron,
            "evidencia_retorno": mensaje_evidencia
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))