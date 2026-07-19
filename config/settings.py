# settings.py
import os
from zoneinfo import ZoneInfo

# BUG CORREGIDO: antes, load_dotenv() se llamaba en otro archivo
# (services/auth_ticktick.py), importado DESPUÉS de que otros módulos
# ya habían importado `config` y leído os.getenv() con el .env todavía
# sin cargar (ej. cierre_service.py -> "from config import BOGOTA" se
# ejecutaba primero). Resultado: APP_PASSWORD_HASH, TOKEN_ENCRYPTION_KEY,
# ADMIN_TOKEN, etc. quedaban vacíos aunque el .env los tuviera bien
# puestos. Cargar el .env aquí, en la primera línea de config.py, evita
# depender del orden en que otros archivos se importen entre sí.
from dotenv import load_dotenv
load_dotenv()

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
# Autenticación general de la API (login con sesión, no API_KEY)
# ==========================================================
# ANTES: se usaba una API_KEY estática, expuesta al cliente via
# NEXT_PUBLIC_API_KEY. Cualquier variable NEXT_PUBLIC_* de Next.js
# queda incrustada en el JS que corre en el navegador -- cualquiera
# que abriera devtools podia leerla y llamar al backend directamente
# como si fuera el dueño de la cuenta. Ademas era la MISMA clave para
# siempre, sin expiracion ni forma de revocarla sin redeploy.
#
# AHORA: el usuario hace POST /api/login con una contraseña, el
# backend la valida contra APP_PASSWORD_HASH (un hash, nunca la
# contraseña en texto plano) y devuelve un token de sesión aleatorio
# que el cliente (web o app móvil) guarda en almacenamiento seguro
# (localStorage en el navegador, Keychain/Keystore en móvil) y manda
# como header "Authorization: Bearer <token>". El token se guarda en
# la base de datos solo como hash, expira solo (SESSION_TTL_DIAS) y
# se puede revocar (logout) sin tocar el codigo ni el .env.
#
# Para generar APP_PASSWORD_HASH corre: python scripts/generar_password_hash.py
APP_PASSWORD_HASH = os.getenv("APP_PASSWORD_HASH")

SESSION_TTL_DIAS = int(os.getenv("SESSION_TTL_DIAS", "90"))

# ==========================================================
# Cifrado de tokens OAuth de TickTick en reposo
# ==========================================================
# access_token / refresh_token de TickTick se guardan cifrados en
# SQLite (tabla tokens_oauth) usando Fernet (AES128 + HMAC). Si
# TOKEN_ENCRYPTION_KEY no esta configurada, se guardan en texto plano
# (comportamiento anterior) -- no recomendado fuera de desarrollo
# local. Para generar la clave corre: python scripts/generar_encryption_key.py
TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY")

# CORS: lista de origenes permitidos, separados por coma
# (ej. "http://localhost:3000,https://mi-app.vercel.app").
# Si no se configura, se usa "*" (cualquier origen) para no romper
# el desarrollo local por defecto -- pero en produccion se recomienda
# restringir esto a los origenes reales del frontend/app.
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS = (
    [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
    if _allowed_origins_env
    else ["*"]
)