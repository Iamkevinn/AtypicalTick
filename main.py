# main.py - Backend de AtypicalTick con FastAPI
import secrets

from fastapi import FastAPI, APIRouter, Header, HTTPException, Depends, Request
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
    PeticionLogin,
)
from services.cierre_service import obtener_tareas_cierre

from services.auth_ticktick import (
    obtener_token
)

from services.auth_service import (
    verificar_password,
    crear_sesion,
    validar_sesion,
    revocar_sesion,
    ip_bloqueada,
    registrar_intento_login,
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
from scheduler import iniciar_scheduler
from db.interacciones import registrar_interaccion
from core.startup import inicializar_backend
from config import ADMIN_TOKEN, ALLOWED_ORIGINS

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
    # DEPRECATED (Fase 3 - migración Supabase/Render): esta función ya
    # no crea ninguna tabla. El schema completo (incluyendo esta tabla)
    # ahora lo maneja Alembic -- ver alembic/versions/542826e5466e_esquema_inicial.py
    # y core/startup.py::inicializar_backend(), que corre
    # "alembic upgrade head" en vez de llamar a init_db().
    #
    # Se deja esta función (en vez de borrarla) por si algún script
    # externo todavía la importa, para que no rompa con un
    # ImportError -- pero ya no ejecuta el CREATE TABLE con
    # AUTOINCREMENT (sintaxis SQLite que no es portable a Postgres).
    logging.warning(
        "init_db() esta obsoleta y ya no hace nada -- el schema lo "
        "maneja Alembic (alembic upgrade head). Ver core/startup.py."
    )

inicializar_backend(init_db)
    
load_dotenv()


def verificar_sesion(authorization: str = Header(default=None)):
    """
    Dependencia de autenticación para todas las rutas "normales" del
    frontend/app (todo lo que va colgado de `router`, no de `app`
    directamente).

    ANTES: ningún endpoint tenía autenticación, y luego se usó una
    API_KEY estática expuesta al cliente via NEXT_PUBLIC_API_KEY (que
    Next.js incrusta en el JS público del navegador -- cualquiera con
    devtools podía leerla).

    AHORA: el cliente (web o app móvil) primero hace POST /api/login
    con una contraseña y recibe un token de sesión aleatorio, que
    guarda en almacenamiento seguro (no en un build público) y manda
    en cada request como "Authorization: Bearer <token>". El token
    vive en la base de datos solo como hash, expira solo y se puede
    revocar (logout) sin redeploy.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")

    token = authorization.removeprefix("Bearer ").strip()

    if not validar_sesion(token):
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")


app = FastAPI(title="AtypicalTick API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _ip_cliente(request: Request) -> str:
    """
    Resuelve la IP real del cliente para el rate limiting de login.

    Si el backend corre detrás de un proxy/CDN (Render, Railway, Fly,
    Vercel, etc. -- lo normal en producción), request.client.host es
    la IP del proxy, no la del usuario, y X-Forwarded-For trae la IP
    real como primer valor de la lista. En local (sin proxy) no hay
    ese header y se usa request.client.host directamente.

    Nota: X-Forwarded-For lo puede mandar cualquiera si no hay un
    proxy real de por medio filtrándolo -- esto es "mejor esfuerzo"
    para frenar fuerza bruta simple, no una defensa perfecta contra
    un atacante que además controla sus propios headers y no pasa
    por tu proxy.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


# Rutas públicas (sin sesión): solo login. Todo lo demás cuelga de
# `router`, que exige una sesión válida.
@app.post("/api/login")
def login(datos: PeticionLogin, request: Request):
    ip = _ip_cliente(request)

    segundos_restantes = ip_bloqueada(ip)
    if segundos_restantes > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos. Intenta de nuevo en {segundos_restantes // 60 + 1} minuto(s).",
        )

    if not verificar_password(datos.password):
        registrar_intento_login(ip, exitoso=False)
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    registrar_intento_login(ip, exitoso=True)
    token, expira = crear_sesion()

    return {
        "token": token,
        "expira_en": expira.isoformat(),
    }


router = APIRouter(dependencies=[Depends(verificar_sesion)])


@router.post("/api/logout")
def logout(authorization: str = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        revocar_sesion(authorization.removeprefix("Bearer ").strip())
    return {"estado": "exito"}


scheduler = iniciar_scheduler(registrar_interaccion)

@router.get("/api/enfoque")
def obtener_tarea_enfoque(
    energia: str = "alta",
):

    return obtener_enfoque(
        energia=energia,
    )

@router.post("/api/feedback-discrepancia")
def feedback_discrepancia(datos: PeticionFeedbackDiscrepancia):
    registrar_feedback_discrepancia(
        datos.motivo_declarado, datos.energia, datos.intervencion_sugerida, datos.respuesta
    )
    return {"estado": "exito"}

@router.post("/api/corregir-decision")
def corregir_decision(datos: PeticionCorreccion):
    registrar_correccion(datos.tarea_id, datos.tipo_decision, datos.valor_original, datos.correccion, datos.carpeta)
    return {"estado": "exito"}

@router.post("/api/corregir-perdon/{proyecto_id}/{tarea_id}")
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


@router.post("/api/rechazar/{tarea_id}")
def rechazar_tarea(tarea_id: str, datos: PeticionRechazo):
    if detectar_riesgo(datos.intencion):
        return respuesta_crisis()
    registrar_interaccion(tarea_id, datos.tarea_nombre, datos.energia, "rechazada", datos.intencion, datos.carpeta)
    return {"estado": "exito"}

@router.post("/api/intento/{tarea_id}")
def registrar_intento_valiente(tarea_id: str, accion: str = "intento", tarea_nombre: str = "", energia: str = "desconocida", carpeta: str = "Inbox"):
    registrar_interaccion(tarea_id, tarea_nombre, energia, accion, None, carpeta)
    if accion in ('paso1_realizado', 'avance_parcial'):
        cerrar_prediccion_con_resultado(tarea_id, accion)
    return {"estado": "exito"}


@router.post("/api/liberar/{proyecto_id}/{tarea_id}")
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

@router.post("/api/chequeo-fidelidad/{tarea_id}")
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

@router.post("/api/posponer/{proyecto_id}/{tarea_id}")
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

@router.post("/api/captura")
def captura_rapida(tarea: TareaNueva):
    if detectar_riesgo(tarea.texto):
        return respuesta_crisis()

    crear_tarea(tarea.texto)

    return {
        "estado": "exito",
        "mensaje": "Capturada en el Inbox",
    }

@router.post("/api/prediccion")
def guardar_prediccion(datos: PeticionPrediccion):
    if detectar_riesgo(datos.prediccion):
        return respuesta_crisis()
    registrar_prediccion(datos.tarea_id, datos.tarea_nombre, datos.prediccion, datos.energia, datos.carpeta)
    return {"estado": "exito"}

@router.get("/api/contrastes")
def ver_contrastes():
    return {"contrastes": obtener_contrastes_recientes(limite=5)}

from services.desglose_service import generar_desglose_completo


@router.post("/api/desglose")
def desglose_magico(
    peticion: PeticionBloqueo,
):
    if detectar_riesgo(peticion.motivo):
        return respuesta_crisis()

    return generar_desglose_completo(peticion)

@router.get("/api/historial")
def ver_historial():
    return obtener_historial_service()

@router.get("/api/debug-sesiones")
def ver_sesiones():
    return obtener_sesiones_debug_service()

@router.get("/api/metricas-clinicas")
def obtener_metricas_clinicas():
    return obtener_metricas_clinicas_service()

@router.get("/api/espejo-conductual")
def espejo_conductual():
    return obtener_espejo_conductual()

@router.post("/api/autocuidado")
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

@router.get("/api/cierre-diario")
def cierre_diario():
    return obtener_tareas_cierre()

@router.post("/api/completar-retroactivo/{proyecto_id}/{tarea_id}")
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

@router.post("/api/posponer-cierre/{proyecto_id}/{tarea_id}")
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

@router.post("/api/olvido-cierre/{proyecto_id}/{tarea_id}")
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

# Registra todas las rutas protegidas por sesión definidas arriba.
# /api/login queda fuera (vive directo en `app`, sin exigir sesión) y
# /api/test-horario también queda fuera (vive directo en `app`, con
# su propia protección por ADMIN_TOKEN más abajo).
app.include_router(router)


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
    - La comparación usa secrets.compare_digest (tiempo constante) en
      vez de "!=", para que el tiempo de respuesta no filtre, byte a
      byte, cuánto del token adivinó un atacante.
    """
    if not ADMIN_TOKEN or not secrets.compare_digest(x_admin_token or "", ADMIN_TOKEN):
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