# taras.py
import json
import requests

print("Leyendo tu llave mágica...")

try:
    with open(".token-oauth", "r") as archivo:
        datos_token = json.load(archivo)
        llave_acceso = datos_token["access_token"]
except FileNotFoundError:
    print("No se encontró el archivo .token-oauth.")
    exit()

# Cabeceras de autorización
headers = {
    "Authorization": f"Bearer {llave_acceso}",
    "Accept": "application/json"
}

print("Conectando con TickTick...")

# 1. Pedimos las listas para saber sus IDs
url_listas = "https://api.ticktick.com/open/v1/project"
respuesta_listas = requests.get(url_listas, headers=headers)

if respuesta_listas.status_code == 200:
    listas = respuesta_listas.json()
    
    if listas:
        # Tomamos la primera lista de tu cuenta (👽Personal)
        mi_lista = listas[0]
        id_lista = mi_lista['id']
        nombre_lista = mi_lista['name']
        
        print(f"\nConectado a la lista: {nombre_lista}")
        print("Consultando tareas pendientes...")
        
        # 2. Pedimos las tareas de esa lista específica
        url_tareas = f"https://api.ticktick.com/open/v1/project/{id_lista}/data"
        respuesta_tareas = requests.get(url_tareas, headers=headers)
        
        if respuesta_tareas.status_code == 200:
            datos_proyecto = respuesta_tareas.json()
            # Extraemos el arreglo de tareas
            tareas = datos_proyecto.get('tasks', [])
            
            # 3. Aplicamos el concepto de diseño para TDAH / Ansiedad
            if tareas:
                # Mostramos únicamente la primera tarea para evitar la parálisis por acumulación
                primera_tarea = tareas[0]
                
                print("\n=========================================")
                print("       🌟 MODO ENFOQUE (Una a la vez)     ")
                print("=========================================")
                print("No pienses en el resto de tu día. Concéntrate solo en esto:\n")
                print(f"   👉 {primera_tarea['title']} 👈")
                print("\n=========================================")
                print(f"*(Tienes {len(tareas) - 1} tareas más ocultas para evitar distracciones)*")
            else:
                print("\n✨ ¡Bandeja limpia! No tienes tareas pendientes aquí. Disfruta tu paz mental. ✨")
                
        else:
            print(f"Error al obtener tareas: {respuesta_tareas.status_code}")
else:
    print(f"Error al conectar: {respuesta_listas.status_code}")