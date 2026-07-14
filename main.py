# main.py - Backend de AtypicalTick con FastAPI
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from schemas.request_models import (
    PeticionAutocuidado,
    PeticionFeedbackDiscrepancia,
    PeticionCorreccion,
    PeticionRechazo,
    PeticionPosponer,
    TareaNueva,
    PeticionPrediccion,
    PeticionBloqueo,
)
from services.cierre_service import obtener_tareas_cierre

from services.auth_ticktick import (
    obtener_token
)
    
from services.enfoque_service import obtener_enfoque
from services.tareas_service import completar_retroactivo_service, liberar_tarea_service, posponer_cierre_service, posponer_tarea_service
from services.ticktick_service import (
    obtener_tarea,
    crear_tarea,
    posponer_para_manana,
    reprogramar_para_hoy,
)

from services.estadisticas_service import (
    calcular_dias_ausente,
)
from utils.fechas import (
    hace_n_dias_bogota,
)
import logging
from datetime import datetime, timedelta 
from dotenv import load_dotenv
import os
from db import db_connection
from scheduler import iniciar_scheduler
from db.interacciones import registrar_interaccion
from core.startup import inicializar_backend

logging.debug("Proceso backend iniciado con pid %s", os.getpid())

# --- Modulos clinicos separados ---
from core.deteccion_crisis import detectar_riesgo, respuesta_crisis
from core.siguiente_experimento import generar_siguiente_experimento
from core.feedback_discrepancia import registrar_feedback_discrepancia
from core.prediccion_vs_resultado import (
    registrar_prediccion,
    cerrar_prediccion_con_resultado, obtener_contrastes_recientes
)
from core.evidencia_acumulada import obtener_evidencia_acumulada
from core.correccion_decisiones import (
 registrar_correccion
)
from core.espejo_metricas import (
    calcular_latencia_activacion, calcular_desglose_aproximaciones,
    construir_anti_patron, construir_evidencia_retorno
)

from core.clasificacion_tareas import clasificar_tarea, calcular_ventana_visibilidad
from core.gestion_horario_estricto import (
    procesar_horario_estricto_vencido,
    es_horario_estricto_recurrente,
    contar_perdidas_consecutivas_salud,
    _es_critica_salud,
)

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

inicializar_backend(init_db)
    
load_dotenv()

app = FastAPI(title="AtypicalTick API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = iniciar_scheduler(registrar_interaccion)

@app.get("/api/enfoque")
def obtener_tarea_enfoque(
    energia: str = "alta",
):

    return obtener_enfoque(
        energia=energia,
    )

@app.post("/api/feedback-discrepancia")
def feedback_discrepancia(datos: PeticionFeedbackDiscrepancia):
    registrar_feedback_discrepancia(
        datos.motivo_declarado, datos.energia, datos.intervencion_sugerida, datos.respuesta
    )
    return {"estado": "exito"}

@app.post("/api/corregir-decision")
def corregir_decision(datos: PeticionCorreccion):
    registrar_correccion(datos.tarea_id, datos.tipo_decision, datos.valor_original, datos.correccion, datos.carpeta)
    return {"estado": "exito"}

@app.post("/api/corregir-perdon/{proyecto_id}/{tarea_id}")
def corregir_perdon(
    proyecto_id: str,
    tarea_id: str,
    tarea_nombre: str = "Desconocida",
    carpeta: str = "Inbox",
):
    reprogramar_para_hoy(
        proyecto_id,
        tarea_id,
    )

    registrar_correccion(
        tarea_id,
        "perdon_rutina",
        "perdonada",
        "era_critica",
        carpeta,
    )

    registrar_interaccion(
        tarea_id,
        tarea_nombre,
        "desconocida",
        "correccion_perdon_revertida",
        "Usuario corrigio auto-perdon",
        carpeta,
    )

    return {"estado": "exito"}


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


@app.post("/api/liberar/{proyecto_id}/{tarea_id}")
def liberar_tarea(
    proyecto_id: str,
    tarea_id: str,
    tarea_nombre: str = "Desconocida",
    energia: str = "desconocida",
    carpeta: str = "Inbox",
    bloqueo_previo: str = "Ninguno",
    intervencion_usada: str = "Ninguna",
):
    return liberar_tarea_service(
        proyecto_id=proyecto_id,
        tarea_id=tarea_id,
        tarea_nombre=tarea_nombre,
        energia=energia,
        carpeta=carpeta,
        bloqueo_previo=bloqueo_previo,
        intervencion_usada=intervencion_usada,
    )

@app.post("/api/posponer/{proyecto_id}/{tarea_id}")
def posponer_tarea(
    proyecto_id: str,
    tarea_id: str,
    datos: PeticionPosponer,
):
    if detectar_riesgo(datos.motivo_posponer):
        return respuesta_crisis()

    return posponer_tarea_service(
        proyecto_id,
        tarea_id,
        datos,
    )

@app.post("/api/captura")
def captura_rapida(tarea: TareaNueva):
    if detectar_riesgo(tarea.texto):
        return respuesta_crisis()

    crear_tarea(tarea.texto)

    return {
        "estado": "exito",
        "mensaje": "Capturada en el Inbox",
    }

@app.post("/api/prediccion")
def guardar_prediccion(datos: PeticionPrediccion):
    if detectar_riesgo(datos.prediccion):
        return respuesta_crisis()
    registrar_prediccion(datos.tarea_id, datos.tarea_nombre, datos.prediccion, datos.energia, datos.carpeta)
    return {"estado": "exito"}

@app.get("/api/contrastes")
def ver_contrastes():
    return {"contrastes": obtener_contrastes_recientes(limite=5)}

from services.desglose_service import generar_desglose_completo


@app.post("/api/desglose")
def desglose_magico(
    peticion: PeticionBloqueo,
):
    if detectar_riesgo(peticion.motivo):
        return respuesta_crisis()

    return generar_desglose_completo(peticion)

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
def cierre_diario():
    return obtener_tareas_cierre()

@app.post("/api/completar-retroactivo/{proyecto_id}/{tarea_id}")
def completar_retroactivo(
    proyecto_id: str,
    tarea_id: str,
    tarea_nombre: str = "Desconocida",
    carpeta: str = "Inbox",
):
    return completar_retroactivo_service(
        proyecto_id,
        tarea_id,
        tarea_nombre,
        carpeta,
    )

@app.post("/api/posponer-cierre/{proyecto_id}/{tarea_id}")
def posponer_cierre(
    proyecto_id: str,
    tarea_id: str,
    tarea_nombre: str = "Desconocida",
    carpeta: str = "Inbox",
):
    return posponer_cierre_service(
        proyecto_id,
        tarea_id,
        tarea_nombre,
        carpeta,
    )

@app.post("/api/olvido-cierre/{proyecto_id}/{tarea_id}")
def olvido_cierre(
    proyecto_id: str,
    tarea_id: str,
    tarea_nombre: str = "Desconocida",
    carpeta: str = "Inbox",
):
    """
    El usuario no recuerda si hizo la tarea.
    Se reprograma para mañana y se registra el olvido.
    """

    tarea = obtener_tarea(
        proyecto_id,
        tarea_id,
    )

    posponer_para_manana(
        proyecto_id,
        tarea,
    )

    registrar_interaccion(
        tarea_id=tarea_id,
        tarea_nombre=tarea_nombre,
        energia="desconocida",
        accion="no_recuerda",
        emocion_motivo="Cierre Diario",
        carpeta=carpeta,
    )

    return {
        "estado": "exito",
    }

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