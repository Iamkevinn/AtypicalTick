# settings.py
import os
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")

DATABASE_URL = os.getenv("DATABASE_URL")

SQLITE_DB_PATH = os.getenv(
    "SQLITE_DB_PATH",
    "atypical_data.db"
)

SQLITE_TIMEOUT_SECONDS = 30

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ==========================================================
# TickTick
# ==========================================================

TICKTICK_CLIENT_ID = os.getenv("TICKTICK_CLIENT_ID")

TICKTICK_CLIENT_SECRET = os.getenv("TICKTICK_CLIENT_SECRET")

TICKTICK_REDIRECT_URI = os.getenv("REDIRECT_URI")

# ==========================================================

SCHEDULER_INTERVAL_MINUTES = int(
    os.getenv("SCHEDULER_INTERVAL_MINUTES", "1")
)

# ==========================================================
# Endpoints internos / de debug
# ==========================================================
# Token compartido para proteger endpoints que no son para el
# frontend normal (ej. /api/test-horario), que disparan efectos
# reales sobre TickTick (completar tareas). Si no se configura,
# esos endpoints quedan deshabilitados por seguridad -- mejor que
# quedar abiertos por accidente.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

# ==========================================================
# Autenticación general de la API
# ==========================================================
# Antes NO existia ningun tipo de autenticacion: cualquiera que
# encontrara la URL del backend podia crear/completar/posponer
# tareas reales en la cuenta de TickTick del usuario. API_KEY, si
# se configura, se exige (header X-API-Key) en TODOS los endpoints
# via una dependencia global en main.py. Si no se configura (ej. en
# desarrollo local), el comportamiento es igual que antes: abierto.
# -> Antes de exponer el backend fuera de tu red local, configura
#    API_KEY tanto aqui (backend) como NEXT_PUBLIC_API_KEY en el
#    frontend (frontend-enfoque/.env.local), con el MISMO valor.
API_KEY = os.getenv("API_KEY")

# CORS: lista de origenes permitidos, separados por coma
# (ej. "http://localhost:3000,https://mi-app.vercel.app").
# Si no se configura, se usa "*" (cualquier origen) para no romper
# el desarrollo local por defecto -- pero en produccion, junto con
# API_KEY configurada, se recomienda restringir esto a los origenes
# reales del frontend.
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS = (
    [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
    if _allowed_origins_env
    else ["*"]
)