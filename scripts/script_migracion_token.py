# script_migracion_token.py — correr una vez, luego borrar
import json
import os
import sys

# Necesario porque al correr "py scripts\script_migracion_token.py",
# Python solo agrega la carpeta scripts\ a sys.path (no la raíz del
# proyecto), y por eso "from services..." fallaba con
# ModuleNotFoundError. Esto agrega la raíz del proyecto explícitamente,
# sin importar desde qué carpeta se invoque el script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.auth_ticktick import guardar_token, init_tabla_tokens

init_tabla_tokens()

with open(".token-oauth", "r") as f:
    datos = json.load(f)

guardar_token(
    access_token=datos["access_token"],
    refresh_token=datos.get("refresh_token"),
    expires_in_seconds=datos.get("expires_in", 2592000),  # ajusta si tu token original no trae esto
)

print("Token migrado a la base de datos.")