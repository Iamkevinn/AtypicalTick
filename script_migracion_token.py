# script_migracion_token.py — correr una vez, luego borrar
import json
from auth_ticktick import guardar_token, init_tabla_tokens

init_tabla_tokens()

with open(".token-oauth", "r") as f:
    datos = json.load(f)

guardar_token(
    access_token=datos["access_token"],
    refresh_token=datos.get("refresh_token"),
    expires_in_seconds=datos.get("expires_in", 2592000),  # ajusta si tu token original no trae esto
)

print("Token migrado a la base de datos.")