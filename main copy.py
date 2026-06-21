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

# Inicializar base de datos
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

    # --- [NUEVO] --- Parches para actualizar tu base de datos sin borrarla
    try: cursor.execute("ALTER TABLE interacciones ADD COLUMN dia_semana TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE interacciones ADD COLUMN carpeta TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE interacciones ADD COLUMN etiquetas TEXT") # NUEVO
    except: pass
    try: cursor.execute("ALTER TABLE sesiones_tarea ADD COLUMN energia TEXT") # NUEVO
    except: pass
    # ---------------
    
    conn.commit()
    conn.close()

# Nueva función para registrar todo lo que hace el usuario
def registrar_interaccion(tarea_id: str, tarea_nombre: str, energia: str, accion: str, emocion: str = None, carpeta: str = "Inbox", etiquetas: str = ""):
    try:
        ahora = datetime.now()
        hora_actual = ahora.hour
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        dia_semana = dias[ahora.weekday()]

        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        # [MODIFICADO]: Insertamos también la columna etiquetas
        cursor.execute('''
            INSERT INTO interacciones (tarea_id, tarea_nombre, energia, emocion_motivo, accion, hora, dia_semana, carpeta, etiquetas) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tarea_id, tarea_nombre, energia, emocion, accion, hora_actual, dia_semana, carpeta, etiquetas))
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
        
        # Mide cuántas veces se usó la IA para este bloqueo y cuántas terminaron en "completada" o "intento"
        # [NUEVO]: Ahora la efectividad depende estrictamente del nivel de energía actual
        cursor.execute("""
            SELECT intervencion_usada, 
                   COUNT(*) as total_veces, 
                   SUM(CASE WHEN resultado_final = 'completada' THEN 1 ELSE 0 END) as completadas,
                   SUM(CASE WHEN resultado_final = 'abandono_consciente' THEN 1 ELSE 0 END) as abandonos
            FROM sesiones_tarea 
            WHERE bloqueo_inicial = ? AND energia = ?
            GROUP BY intervencion_usada
        """, (motivo_bloqueo, energia_actual))
        
        resultados = cursor.fetchall()
        conn.close()
        
        if not resultados:
            return "Aún no hay datos históricos para este bloqueo con este nivel de energía."
            
        reporte = f"Historial de efectividad para este bloqueo con energía {energia_actual.upper()}:\n"

        for fila in resultados:
            intervencion = fila[0]
            total = fila[1]
            completadas = fila[2] if fila[2] else 0
            # Si completó la tarea, la tasa de éxito sube
            tasa_exito = round((completadas / total) * 100)
            reporte += f"- Al usar {intervencion}: {tasa_exito}% de éxito (Usado {total} veces).\n"
            
        return reporte
    except Exception as e:
        return "Error al leer historial."
    
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
    hoy = datetime.utcnow().date()
    ahora = datetime.now()

    for tarea in todas_las_tareas:
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
            
            # Buscamos cualquier variación que signifique "fácil" o "poca energía"
            es_baja_energia = any(palabra in tags_lower for palabra in [
                "baja-energia", "energia-baja", "baja_energia", "energia_baja", 
                "facil", "simple", "rutina"
            ])
            
            if tarea.get('priority', 0) == 5 or es_baja_energia:
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
        elif not necesita_calentamiento and energia == "alta": score = -(prio * 20) - (dias_atraso * 10)
        else: 
            score = prio * 5
            if dias_atraso > 0 and prio == 5: score -= 50
        return score

    tareas_validas.sort(key=calcular_peso_psicologico)

    dias_ausente = calcular_dias_ausente()
    intentos_hoy = contar_intentos_hoy()

    if not tareas_validas:
        return {"estado": "vacio", "mensaje": "✨ ¡Bandeja limpia por ahora!", "dias_ausente": dias_ausente}

    primera_tarea = tareas_validas[0]
    id_proyecto = primera_tarea.get('projectId', 'inbox')
    nombre_carpeta = mapa_carpetas.get(id_proyecto, "Inbox")
    etiquetas = primera_tarea.get('tags', [])
    
    perfil_clinico = analizar_perfil_clinico(nombre_carpeta, etiquetas)

    friccion_consecutiva = contar_friccion_consecutiva(primera_tarea['id'])

    return {
        "estado": "enfoque",
        "tarea_actual": {
            "id": primera_tarea['id'],
            "titulo": primera_tarea['title'],
            "descripcion": primera_tarea.get('content', ''), # <--- ¡NUEVO! Extraemos la descripción
            "proyecto_id": primera_tarea['projectId'],
            "carpeta": nombre_carpeta,
            "etiquetas": etiquetas,
            "perfil_clinico": perfil_clinico
        },
        "tareas_ocultas": len(tareas_validas) - 1,
        "fase": "calentamiento" if necesita_calentamiento else "trabajo_profundo",
        "estadisticas": {
            "dias_ausente": dias_ausente,
            "intentos_hoy": intentos_hoy,
            "intentos_tarea": friccion_consecutiva 
        }
    }



# (Tus funciones de /liberar y /posponer siguen exactamente igual)
# --- RUTAS DE ACCIÓN ---

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
        
        # NUEVO: Guardamos que esta sesión terminó en éxito
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sesiones_tarea (tarea_id, bloqueo_inicial, intervencion_usada, resultado_final, energia) VALUES (?, ?, ?, ?, ?)",
              (tarea_id, bloqueo_previo, "Desglose IA" if bloqueo_previo != "Ninguno" else "Ninguna", "completada", energia))
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
    tarea['dueDate'] = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00+0000")
    requests.post(url_tarea, headers=headers, json=tarea)
    
    # Guardamos la interacción normal pero con el MOTIVO
    registrar_interaccion(tarea_id, datos.tarea_nombre, datos.energia, "pospuesta", datos.motivo_posponer, datos.carpeta)
    
    # Si el motivo dice "Avance Parcial", el resultado final es victoria, no abandono
    resultado_sesion = "avance_parcial" if "Avance Parcial" in datos.motivo_posponer else "abandono_consciente"
    
    # NUEVO: Registramos en la tabla de sesiones que esta batalla terminó en abandono/posposición
    conn = sqlite3.connect('atypical_data.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sesiones_tarea (tarea_id, bloqueo_inicial, intervencion_usada, resultado_final, energia) VALUES (?, ?, ?, ?, ?)",
              (tarea_id, datos.bloqueo_previo, "Desglose IA" if datos.bloqueo_previo != "Ninguno" else "Ninguna", resultado_sesion, datos.energia))
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
    
    # 1. Registrar que el usuario afrontó su fricción pidiendo ayuda
    registrar_interaccion(peticion.tarea_id, peticion.titulo_tarea, peticion.energia, "afronto_ansiedad", peticion.motivo, peticion.carpeta) 

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    url_gemini = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    motivo = peticion.motivo.lower()
    carpeta = peticion.carpeta.lower()
    etiquetas_texto = " ".join([t.lower() for t in peticion.etiquetas])
    
    # 🚨 DETECCIÓN DE PROTOCOLO CRÍTICO DE SALUD 🚨
    es_salud = "health" in carpeta or "salud" in carpeta or "medicina" in etiquetas_texto or "meds" in etiquetas_texto or "fluoxetina" in peticion.titulo_tarea.lower()

    plantilla_psicologica = ""
    nombre_intervencion = ""
    
    if es_salud:
        nombre_intervencion = "Plantilla Salud Crítica"
        plantilla_psicologica = "Paso 1: Remover fricción física. Paso 2: Acción preparatoria. Paso 3: Acción de consumo innegociable."
    # 🚨 NUEVO PROTOCOLO: PERFECCIONISMO 🚨
    elif "perfecto" in motivo or "listo" in motivo:
        nombre_intervencion = "Plantilla Perfeccionismo (Anti-parálisis)"
        plantilla_psicologica = "Paso 1: Hacer un 'borrador basura' intencionalmente malo durante 1 minuto. Paso 2: Identificar el requisito mínimo indispensable. Paso 3: Hacer solo ese requisito mínimo."
    elif "empezar" in motivo or "abruma" in motivo or "grande" in motivo:
        nombre_intervencion = "Plantilla TDAH (Inercia)"
        plantilla_psicologica = "Paso 1: Preparar el entorno. Paso 2: Hacer la acción de entrada más ridículamente pequeña posible. Paso 3: Completar UNA unidad mínima."
    elif "ansiedad" in motivo or "miedo" in motivo:
        nombre_intervencion = "Plantilla Ansiedad (Exposición)"
        plantilla_psicologica = "Paso 1: Acercamiento seguro. Paso 2: Observación pasiva sin expectativa (1 min). Paso 3: Micro-decisión libre."
    # 3. Depresión / Agotamiento (Con detección de falso agotamiento)
    elif "agotado" in motivo or "energía" in motivo:
        
        # MAGIA CLÍNICA: Si el usuario dice estar agotado, pero su historial dice "Ansiedad"
        historial = peticion.patron_historico.lower() if peticion.patron_historico else ""
        
        if "ansiedad" in historial or "miedo" in historial:
            nombre_intervencion = "Plantilla: Ansiedad Disfrazada de Agotamiento"
            plantilla_psicologica = """
            Paso 1: Validar que el cuerpo se siente pesado no por falta de sueño, sino por el estrés acumulado (la Amígdala drena energía). 
            Paso 2: Hacer 1 solo estiramiento físico para romper la parálisis. 
            Paso 3: Tocar el objeto/app de la tarea por 5 segundos y retirarse libremente.
            """
        else:
            nombre_intervencion = "Plantilla: Agotamiento Real"
            plantilla_psicologica = "Paso 1: Micro-acción desde donde el usuario esté. Paso 2: Iniciar la tarea sin compromiso de terminar. Paso 3: Mantener la acción 2 minutos y parar."

    elif "entiendo" in motivo or "claridad" in motivo:
        nombre_intervencion = "Plantilla Claridad"
        plantilla_psicologica = "Paso 1: Identificar dónde están las instrucciones. Paso 2: Leer solo el primer párrafo. Paso 3: Escribir la pregunta exacta."
    else: 
        nombre_intervencion = "Plantilla Estándar"
        plantilla_psicologica = "Paso 1: Preparar entorno, Paso 2: Acción mínima, Paso 3: Mantener 2 minutos."

    # --- NUEVO: OBTENEMOS TU HISTORIAL DE ÉXITO ---
    historial_datos = obtener_efectividad_historica(peticion.motivo, peticion.energia)

    prompt = f"""
    Eres un coach clínico experto en Activación Conductual y función ejecutiva.
    El paciente neurodivergente está bloqueado.
    
    - Tarea a realizar: "{peticion.titulo_tarea}"
    - Detalles/Instrucciones de la tarea: "{peticion.descripcion_tarea}" 
    - Contexto: Carpeta '{peticion.carpeta}'
    - Motivo del bloqueo: "{peticion.motivo}"
    
    === DATA HISTÓRICA DEL PACIENTE ===
    {historial_datos}
    ===================================
    
    INTERVENCIÓN ASIGNADA: {nombre_intervencion}
    Base de la intervención: {plantilla_psicologica}
    
    INSTRUCCIÓN CRÍTICA: 
    Si la 'Data Histórica' indica que esta intervención ha tenido una baja tasa de éxito en el pasado para este bloqueo, ADAPTA tus pasos para hacerlos AÚN MÁS minúsculos, perdonadores y fáciles. 
    Si la tasa de éxito es buena o no hay datos, aplica la intervención normalmente.
    
    Regla de oro: Escribe de forma muy empática, directa y corta.
    Devuelve la respuesta usando exactamente este formato JSON:
    {{"pasos": ["paso 1", "paso 2", "paso 3"]}}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    try:
        respuesta = requests.post(url_gemini, headers={"Content-Type": "application/json"}, json=payload)
        datos = respuesta.json()
        texto_ia = datos['candidates'][0]['content']['parts'][0]['text']
        return json.loads(texto_ia)
            
    except Exception as e:
        print("🚨 EXCEPCIÓN EN PYTHON:", e)
        return {"pasos": ["Toma un vaso de agua.", "Respira hondo 3 veces.", "Cierra la app y descansa sin culpa."]}

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

# ---------------------------------------------------------
# EL ESPEJO CONDUCTUAL (Analítica Psicológica Humana)
# ---------------------------------------------------------
@app.get("/api/espejo-conductual")
def espejo_conductual():
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()

        # 1. RESILIENCIA (Intentos a pesar de la fricción en los últimos 7 días)
        cursor.execute("SELECT COUNT(*) FROM interacciones WHERE accion IN ('intento', 'afronto_ansiedad', 'avance_parcial') AND timestamp >= datetime('now', '-7 days')")
        intentos = cursor.fetchone()[0]

        # 2. TOP BLOQUEOS (Los 2 motivos más frecuentes esta semana)
        cursor.execute("""
            SELECT emocion_motivo FROM interacciones 
            WHERE accion IN ('pidio_ayuda', 'pospuesta') AND emocion_motivo IS NOT NULL AND emocion_motivo != 'Sin motivo' 
            AND timestamp >= datetime('now', '-7 days') 
            GROUP BY emocion_motivo ORDER BY COUNT(*) DESC LIMIT 2
        """)
        top_bloqueos = [row[0] for row in cursor.fetchall()]

        # 3. ZONA DE FRICCIÓN (La carpeta que más cuesta)
        cursor.execute("""
            SELECT carpeta FROM interacciones 
            WHERE accion IN ('pidio_ayuda', 'pospuesta', 'abandono_consciente') 
            AND timestamp >= datetime('now', '-7 days') 
            GROUP BY carpeta ORDER BY COUNT(*) DESC LIMIT 1
        """)
        zona_friccion = cursor.fetchone()

        # 4. DÍA DE FLUJO (Día de la semana con más completadas en el historial global)
        cursor.execute("SELECT dia_semana FROM interacciones WHERE accion = 'completada' GROUP BY dia_semana ORDER BY COUNT(*) DESC LIMIT 1")
        dia_flujo = cursor.fetchone()

        # 5. PATRÓN DE LA IA (Dónde funciona mejor el desglose)
        cursor.execute("""
            SELECT bloqueo_inicial FROM sesiones_tarea 
            WHERE resultado_final IN ('completada', 'avance_parcial') AND bloqueo_inicial != 'Ninguno'
            GROUP BY bloqueo_inicial ORDER BY COUNT(*) DESC LIMIT 1
        """)
        ia_salvavidas = cursor.fetchone()

        conn.close()

        # --- CONSTRUCCIÓN DE LAS FRASES HUMANAS ---
        resiliencia_msg = f"Esta semana has vuelto a intentarlo {intentos} veces después de bloquearte. Tu capacidad de volver al ruedo es altísima." if intentos > 0 else "Esta semana estás tomando el descanso que necesitas. Eso también es avanzar."
        
        friccion_msg = f"Tus tareas de '{zona_friccion[0]}' te están exigiendo mucha más energía emocional que el resto." if zona_friccion else "No hay un patrón claro de fricción esta semana."
        
        flujo_msg = f"Históricamente, los {dia_flujo[0]} son tus días de mayor inercia y enfoque." if dia_flujo else "Aún estamos aprendiendo tus ritmos diarios."
        
        ia_msg = f"El desglose de la IA te destraba especialmente cuando sientes: '{ia_salvavidas[0]}'." if ia_salvavidas else "El sistema sigue aprendiendo cómo ayudarte mejor."

        return {
            "resiliencia": resiliencia_msg,
            "top_bloqueos": top_bloqueos,
            "zona_friccion": friccion_msg,
            "zona_flujo": flujo_msg,
            "patron_ia": ia_msg
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))