import os
import requests
from dotenv import load_dotenv
from ticktick.oauth2 import OAuth2

# Cargar variables desde .env
load_dotenv()

client_id = os.getenv("TICKTICK_CLIENT_ID")
client_secret = os.getenv("TICKTICK_CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URI")

print("Cargando tu llave de acceso secreta...")

auth_client = OAuth2(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri
)

headers = {
    "Authorization": f"Bearer {auth_client.get_access_token()}",
    "Accept": "application/json"
}

print("Pidiendo tus datos a TickTick...\n")

url_oficial = "https://api.ticktick.com/open/v1/project"
respuesta = requests.get(url_oficial, headers=headers)

if respuesta.status_code == 200:
    listas = respuesta.json()

    print("¡CONEXIÓN ESTABLECIDA CON ÉXITO! 🚀")
    print(f"Tienes {len(listas)} listas de tareas:")

    for lista in listas:
        print(f"📂 {lista['name']}")
else:
    print(f"Ups, algo pasó: {respuesta.status_code} - {respuesta.text}")