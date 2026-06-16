import requests
from ticktick.oauth2 import OAuth2

# 1. Tus credenciales oficiales
client_id = "Mc6Or82CRM6shnQ5dU"
client_secret = "d4BN2MhE3547yJbFzx88lfHl1vnsTvrE"
redirect_uri = "http://127.0.0.1:8080"

print("Cargando tu llave de acceso secreta...")

# 2. Esto leerá tu archivo .token-oauth automáticamente (¡sin pedirte login de nuevo!)
auth_client = OAuth2(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

# 3. Preparamos el sobre con tu llave para TickTick
headers = {
    "Authorization": f"Bearer {auth_client.get_access_token()}",
    "Accept": "application/json"
}

print("Pidiendo tus datos a TickTick...\n")

# 4. Llamamos a la API 100% Oficial de TickTick
url_oficial = "https://api.ticktick.com/open/v1/project"
respuesta = requests.get(url_oficial, headers=headers)

if respuesta.status_code == 200:
    listas = respuesta.json()
    print("¡CONEXIÓN ESTABLECIDA CON ÉXITO! 🚀")
    print(f"Tienes {len(listas)} listas de tareas en tu cuenta. Aquí están:")
    
    for lista in listas:
        print(f" 📂 {lista['name']}")
else:
    print(f"Ups, algo pasó: {respuesta.status_code} - {respuesta.text}")