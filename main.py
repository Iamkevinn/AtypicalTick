# main.py - Backend de AtypicalTick con FastAPI
from fastapi import FastAPI, Header, HTTPException, Depends
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
    PeticionChequeoFidelidad,
)
from services.cierre_service import obtener_tareas_cierre

from services.auth_ticktick import (
    obtener_token
)
    
from services.debug_service import obtener_sesiones_debug_service
from services.enfoque_service import obtener_enfoque
from services.espejo_service import obtener_espejo_conductual
from services.historial_service import obtener_historial_service
from services.metricas_service import obtener_metricas_clinicas_service
from services.tareas_service import completar_retroactivo_service, liberar_tarea_service, olvido_cierre_service, posponer_cierre_service, posponer_tarea_service
from services.ticktick_service import (
    crear_tarea,
    reprogramar_para_hoy,
)

import logging
from dotenv import load_dotenv
import os
from db import db_connection
from scheduler import iniciar_scheduler
from db.interacciones import registrar_interaccion
from core.startup import inicializar_backend
from config import ADMIN_TOKEN, API_KEY, ALLOWED_ORIGINS

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


def verificar_api_key(x_api_key: str = Header(default=None)):
    """
    Dependencia global de autenticación.

    ANTES: ningún endpoint tenía autenticación. Con CORS abierto a
    "*" y sin ninguna llave, cualquiera que encontrara la URL del
    backend podía crear, completar o posponer tareas reales en la
    cuenta de TickTick conectada.

    Si API_KEY no está configurada (ej. desarrollo local), esta
    función no hace nada -- el comportamiento es igual que antes.
    Si SÍ está configurada, todas las rutas la exigen vía el header
    X-API-Key (ver `dependencies=[Depends(verificar_api_key)]` más
    abajo), porque se aplica a nivel de app, no por endpoint.
    """
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida o faltante")


app = FastAPI(
    title="AtypicalTick API",
    dependencies=[Depends(verificar_api_key)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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

@app.post("/api/chequeo-fidelidad/{tarea_id}")
def chequeo_fidelidad(tarea_id: str, datos: PeticionChequeoFidelidad):
    accion = (
        "fidelidad_confirmada"
        if datos.respuesta == "si"
        else "fidelidad_no_confirmada"
    )
    registrar_interaccion(
        tarea_id=tarea_id,
        tarea_nombre=datos.tarea_nombre,
        energia=datos.energia,
        accion=accion,
        emocion=None,
        carpeta=datos.carpeta,
    )
    return {"estado": "exito"}

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
    return obtener_historial_service()

@app.get("/api/debug-sesiones")
def ver_sesiones():
    return obtener_sesiones_debug_service()

@app.get("/api/metricas-clinicas")
def obtener_metricas_clinicas():
    return obtener_metricas_clinicas_service()

@app.get("/api/espejo-conductual")
def espejo_conductual():
    return obtener_espejo_conductual()

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
    return olvido_cierre_service(
        proyecto_id,
        tarea_id,
        tarea_nombre,
        carpeta,
    )

@app.post("/api/test-horario")
def test_horario(x_admin_token: str = Header(default=None)):
    """
    Endpoint de DEBUG/mantenimiento manual: dispara el mismo proceso
    que corre el scheduler en background (auto-saltar rutinas vencidas
    de horario estricto). Tiene efectos reales sobre TickTick, por eso:

    - Es POST, no GET (un GET no deberia tener efectos secundarios;
      antes, cualquier prefetch de navegador, bot, o monitor de salud
      podia disparar auto-completados sin que el usuario lo pidiera).
    - Requiere el header X-Admin-Token, que debe coincidir con la
      variable de entorno ADMIN_TOKEN. Si ADMIN_TOKEN no esta
      configurado, el endpoint queda deshabilitado (no hay forma de
      "adivinar" un token vacio).
    """
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=404, detail="No encontrado")

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