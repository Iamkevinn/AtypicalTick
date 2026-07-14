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