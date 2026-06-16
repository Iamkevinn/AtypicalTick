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
            carpeta TEXT, -- NUEVO: Para saber el "Dominio" (Ej. Salud, Trabajo)
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Parche por si la tabla ya existía
    try: cursor.execute("ALTER TABLE interacciones ADD COLUMN dia_semana TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE interacciones ADD COLUMN carpeta TEXT")
    except: pass
    
    conn.commit()
    conn.close()

# Nueva función para registrar todo lo que hace el usuario
def registrar_interaccion(tarea_id: str, tarea_nombre: str, energia: str, accion: str, emocion: str = None, carpeta: str = "Inbox"):
    try:
        ahora = datetime.now()
        hora_actual = ahora.hour
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        dia_semana = dias[ahora.weekday()]

        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO interacciones (tarea_id, tarea_nombre, energia, emocion_motivo, accion, hora, dia_semana, carpeta) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tarea_id, tarea_nombre, energia, emocion, accion, hora_actual, dia_semana, carpeta))
        conn.commit()
        conn.close()
    except Exception as e:
        print("🚨 Error al guardar interacción:", e)
        
init_db()

# ---------------------------------------------------------
# MOTOR CLÍNICO: Cálculo de Resistencia Emocional
# ---------------------------------------------------------
def calcular_resistencia(carpeta: str) -> float:
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        # Ahora medimos la resistencia de TODA la carpeta (Ej. todo lo de "Inglés")
        cursor.execute("SELECT accion FROM interacciones WHERE carpeta = ?", (carpeta,))
        acciones = cursor.fetchall()
        conn.close()

        resistencia = 0.0
        for (accion,) in acciones:
            if accion == "pospuesta": resistencia += 2.0
            elif accion == "pidio_ayuda": resistencia += 1.0
            elif accion == "completada": resistencia -= 2.0
        
        return max(0.0, min(resistencia, 40.0)) # TOPAMOS LA RESISTENCIA EN 40 para evitar "evitación eterna"
    except: return 0.0
    
load_dotenv()

app = FastAPI(title="AtypicalTick API")

# Esto es VITAL para que tu futuro frontend en React pueda hablar con este backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción se cambia por localhost:3000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Añadimos un parámetro a la URL: ?energia=alta o ?energia=baja
@app.get("/api/enfoque")
def obtener_tarea_enfoque(energia: str = "alta"):
    token = obtener_token()
    if not token:
        raise HTTPException(status_code=401, detail="No hay token de acceso")

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    # 1. Traer tareas de TickTick
    url_listas = "https://api.ticktick.com/open/v1/project"
    resp_listas = requests.get(url_listas, headers=headers)
    if resp_listas.status_code != 200:
        raise HTTPException(status_code=500, detail="Error al conectar con TickTick")
        
    listas = resp_listas.json()

    # NUEVO: Creamos un diccionario mágico para saber el nombre real de cada carpeta
    mapa_carpetas = {lista['id']: lista['name'] for lista in listas}
    # TickTick guarda las tareas del Inbox sin projectId, le asignamos 'Inbox' por defecto
    mapa_carpetas['inbox'] = "Inbox"

    todas_las_tareas = []
    for lista in listas:
        url_tareas = f"https://api.ticktick.com/open/v1/project/{lista['id']}/data"
        resp_tareas = requests.get(url_tareas, headers=headers)
        if resp_tareas.status_code == 200:
            todas_las_tareas.extend(resp_tareas.json().get('tasks', []))

    # 2. SABER SI YA CALENTÓ HOY (Anti evitación)
    conn = sqlite3.connect('atypical_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM interacciones WHERE accion='completada' AND date(timestamp) = date('now')")
    completadas_hoy = cursor.fetchone()[0]
    conn.close()
    
    necesita_calentamiento = completadas_hoy == 0

    # 3. FILTRO CLÍNICO Y TIME-BLOCKING AMABLE
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

                    # Ocultar tareas del futuro (más de 1 hora de anticipación)
                    if hora_tarea.timestamp() > ahora.timestamp() + 3600:
                        mostrar_ahora = False

        if (not es_hoy_o_atrasada and tiene_fecha) or not mostrar_ahora:
            continue

        if energia == "baja":
            tags = tarea.get('tags', [])
            if tarea.get('priority', 0) == 5 or "baja-energia" in tags:
                tareas_validas.append(tarea)
        else:
            tareas_validas.append(tarea)

    # 4. ALGORITMO INTELIGENTE (Importancia + Urgencia + Energía - Resistencia)
    def calcular_peso_psicologico(t):
        prio = t.get('priority', 0)
        
        # Calculamos días de atraso (Urgencia Real)
        dias_atraso = 0
        if 'dueDate' in t:
            fecha_t = datetime.strptime(t['dueDate'][:10], "%Y-%m-%d").date()
            if fecha_t < hoy:
                dias_atraso = (hoy - fecha_t).days

        # Resistencia por DOMINIO (Carpeta)
        id_proy = t.get('projectId', 'inbox')
        nombre_carpeta_t = mapa_carpetas.get(id_proy, "Inbox")
        resistencia = calcular_resistencia(nombre_carpeta_t)
        
        score = 0
        
        if necesita_calentamiento and energia == "alta":
            score += prio * 10       
            score += resistencia * 15 # Reducimos el castigo de 50 a 15
            score -= dias_atraso * 5  # La urgencia tira hacia arriba para que no se esconda siempre
            
        elif not necesita_calentamiento and energia == "alta":
            score -= prio * 20        
            score += resistencia * 2  
            score -= dias_atraso * 10 # Las atrasadas toman mucha prioridad
            
        else: # Supervivencia
            score += prio * 5
            score += resistencia * 10
            if dias_atraso > 0 and prio == 5: score -= 50

        return score

    tareas_validas.sort(key=calcular_peso_psicologico)

    if not tareas_validas:
        return {"estado": "vacio", "mensaje": "✨ ¡Bandeja limpia por ahora!"}

    primera_tarea = tareas_validas[0]

     # Extraemos la información de contexto de TickTick
    id_proyecto = primera_tarea.get('projectId', 'inbox')
    nombre_carpeta = mapa_carpetas.get(id_proyecto, "Inbox")
    etiquetas = primera_tarea.get('tags', [])
    
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dia_hoy = dias[datetime.now().weekday()]

    # MAGIA CLÍNICA: Obtenemos resistencia y patrones históricos
    nivel_resistencia = calcular_resistencia(nombre_carpeta)
    patron_historico = obtener_patron_contextual(nombre_carpeta, dia_hoy)


    return {
        "estado": "enfoque",
        "tarea_actual": {
            "id": primera_tarea['id'],
            "titulo": primera_tarea['title'],
            "proyecto_id": primera_tarea['projectId'],
            "carpeta": nombre_carpeta,
            "etiquetas": etiquetas,
            "resistencia": nivel_resistencia,
            "patron_emocional": patron_historico # <-- ¡LA MEMORIA PSICOLÓGICA!
        },
        "tareas_ocultas": len(tareas_validas) - 1,
        "fase": "calentamiento" if necesita_calentamiento else "trabajo_profundo"
    }
# (Tus funciones de /liberar y /posponer siguen exactamente igual)

@app.post("/api/liberar/{proyecto_id}/{tarea_id}")
def liberar_tarea(proyecto_id: str, tarea_id: str, tarea_nombre: str = "Desconocida", energia: str = "desconocida", carpeta: str = "Inbox"):
    token = obtener_token()
    if not token: raise HTTPException(status_code=401)

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    respuesta = requests.post(f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}/complete", headers=headers)

    if respuesta.status_code == 200:
        registrar_interaccion(tarea_id, tarea_nombre, energia, "completada", None, carpeta)
        return {"estado": "exito"}
    raise HTTPException(status_code=500)
    
@app.post("/api/posponer/{proyecto_id}/{tarea_id}")
def posponer_tarea(proyecto_id: str, tarea_id: str, tarea_nombre: str = "Desconocida", energia: str = "desconocida", carpeta: str = "Inbox"):
    token = obtener_token()
    if not token: raise HTTPException(status_code=401)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url_tarea = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}"
    resp_tarea = requests.get(url_tarea, headers=headers)
    if resp_tarea.status_code != 200: raise HTTPException(status_code=500)
        
    tarea = resp_tarea.json()
    tarea['dueDate'] = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00+0000")
    respuesta_update = requests.post(url_tarea, headers=headers, json=tarea)

    if respuesta_update.status_code == 200:
        registrar_interaccion(tarea_id, tarea_nombre, energia, "pospuesta", None, carpeta)
        return {"estado": "exito"}
    raise HTTPException(status_code=500)
       
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
    motivo: str
    energia: str = "desconocida"
    carpeta: str = ""
    etiquetas: list[str] = []

@app.post("/api/desglose")
def desglose_magico(peticion: PeticionBloqueo):
    
    # NUEVO SENSOR
    registrar_interaccion(
        tarea_id=peticion.tarea_id,
        tarea_nombre=peticion.titulo_tarea, 
        energia=peticion.energia, 
        accion="pidio_ayuda", 
        emocion=peticion.motivo,
         carpeta=peticion.carpeta 
    ) 

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    url_gemini = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    motivo = peticion.motivo.lower()
    carpeta = peticion.carpeta.lower()
    etiquetas_texto = " ".join([t.lower() for t in peticion.etiquetas])
    
    # 🚨 DETECCIÓN DE PROTOCOLO CRÍTICO DE SALUD 🚨
    es_salud = "health" in carpeta or "salud" in carpeta or "medicina" in etiquetas_texto or "meds" in etiquetas_texto or "fluoxetina" in peticion.titulo_tarea.lower()

    plantilla_psicologica = ""
    
    if es_salud:
        plantilla_psicologica = """
        Plantilla Salud/Medicación (Adherencia Crítica):
        Esta es una tarea de salud INNEGOCIABLE. No es un proyecto que se pueda dividir y dejar a medias.
        Paso 1: Remover fricción física (ej. "Ve a la cocina y sirve un vaso de agua").
        Paso 2: Acción preparatoria (ej. "Saca la pastilla del blíster y ponla en tu mano").
        Paso 3: Acción de consumo (ej. "Tómatela ahora mismo. Es por tu cerebro, tú lo vales").
        """
    elif "empezar" in motivo or "abruma" in motivo or "grande" in motivo:
        plantilla_psicologica = """
        Plantilla TDAH (Inercia):
        Paso 1: Preparar el entorno físico/digital (ej. Sentarse, abrir la app).
        Paso 2: Hacer la acción de entrada más ridículamente pequeña posible.
        Paso 3: Completar UNA unidad mínima de la tarea (ej. Leer 1 oración, mover 1 cosa, hacer 1 ejercicio).
        """
    
    # 2. Ansiedad (Evitación / Miedo)
    elif "ansiedad" in motivo or "miedo" in motivo:
        plantilla_psicologica = """
        Plantilla Ansiedad (Exposición gradual):
        Paso 1: Acción de acercamiento seguro (ej. Acercarse al escritorio, abrir la carpeta).
        Paso 2: Observación pasiva sin expectativa (ej. Solo mirar los documentos por 1 minuto sin hacer nada).
        Paso 3: Micro-decisión (ej. Elegir por dónde empezar mañana o hacer solo un clic).
        """
        
    # 3. Depresión / Agotamiento
    elif "agotado" in motivo or "energía" in motivo:
        plantilla_psicologica = """
        Plantilla Agotamiento (Conservación de energía):
        Paso 1: Micro-acción desde donde el usuario esté (ej. Tomar agua, sentarse derecho).
        Paso 2: Iniciar la tarea sin compromiso de terminar.
        Paso 3: Mantener la acción por solo 2 minutos y parar intencionalmente.
        """
        
    # 4. Falta de Claridad (Parálisis por confusión)
    elif "entiendo" in motivo or "claridad" in motivo:
        plantilla_psicologica = """
        Plantilla Claridad:
        Paso 1: Identificar a quién preguntarle o dónde están las instrucciones.
        Paso 2: Leer solo el primer párrafo o identificar la duda exacta.
        Paso 3: Escribir la pregunta o buscar una sola referencia.
        """
    # 5. Fallback por si acaso
    else: 
        plantilla_psicologica = "Paso 1: Preparar entorno, Paso 2: Acción mínima, Paso 3: Mantener 2 minutos."

    prompt = f"""
    Eres un psicólogo clínico experto en Activación Conductual.
    El paciente neurodivergente está bloqueado.
    - Tarea: "{peticion.titulo_tarea}"
    - Contexto: Carpeta '{peticion.carpeta}', Etiquetas: {peticion.etiquetas}
    - Motivo del bloqueo: "{peticion.motivo}"
    
    Debes aplicar ESTRICTAMENTE esta plantilla:
    {plantilla_psicologica}
    
    Regla de oro: Escribe de forma muy empática, directa y corta.
    Devuelve la respuesta usando exactamente este formato JSON:
    {{"pasos": ["paso 1", "paso 2", "paso 3"]}}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    try:
        respuesta = requests.post(url_gemini, headers={"Content-Type": "application/json"}, json=payload)
        datos = respuesta.json()
        
        texto_ia = datos['candidates'][0]['content']['parts'][0]['text']
        return json.loads(texto_ia)
            
    except Exception as e:
        print("🚨 EXCEPCIÓN EN PYTHON:", e)
        return {"pasos": ["Toma un vaso de agua.", "Respira hondo 3 veces.", "Cierra la app y descansa."]}


# ---------------------------------------------------------
# NUEVA RUTA PARA VER EL HISTORIAL CLÍNICO
# ---------------------------------------------------------
@app.get("/api/historial")
def ver_historial():
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, tarea_id, tarea_nombre, energia, emocion_motivo, accion, hora, timestamp FROM interacciones ORDER BY timestamp DESC")
        filas = cursor.fetchall()
        conn.close()
        
        historial = []
        for fila in filas:
            historial.append({
                "id": fila[0],
                "tarea_id": fila[1],
                "tarea": fila[2],
                "energia": fila[3],
                "emocion": fila[4],
                "accion": fila[5],
                "hora_dia": f"{fila[6]}:00",
                "fecha_hora": fila[7]
            })
            
        return {"total_registros": len(historial), "registros": historial}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer la base de datos: {str(e)}")