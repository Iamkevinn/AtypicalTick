# gestion_horario_estricto.py
import requests
import sqlite3
import re
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from clasificacion_tareas import clasificar_tarea
import traceback

# --- Zona horaria centralizada (ver main.py) ---
# tarea_es_horario_estricto_vencida() se llama desde /api/enfoque SIN
# pasarle "ahora", asi que el default que usaba (datetime.now(), hora
# naive del servidor) nunca coincidia con la hora Bogota que usa el
# resto del sistema (incluido el scheduler en background). Eso hacia
# que una tarea pudiera verse "vencida" o "vigente" segun en que
# funcion se evaluara, dependiendo de la diferencia entre la hora del
# servidor y la hora real de Bogota.
BOGOTA = ZoneInfo("America/Bogota")

print("########################################")
print(__file__)
print("########################################")

# --- NUEVO: exclusion dura de salud del auto-completado del scheduler ---
# Carpetas/etiquetas que marcan una tarea como "critica de salud". Estas
# tareas (ej. "Aplicar acido en espalda", cualquier medicamento) NUNCA
# deben ser completadas o saltadas automaticamente por el scheduler en
# background, sin importar que sean recurrentes con hora fija. El
# usuario prefiere verlas vencidas en TickTick y decidir el mismo, en
# vez de que el sistema asuma silenciosamente que las hizo.
CARPETAS_SALUD = ["health", "salud"]
ETIQUETAS_SALUD = ["medicine", "medicina"]


def _es_critica_salud(tarea: dict, carpeta: str) -> bool:
    carpeta_lower = (carpeta or "").lower()
    tags_lower = [t.lower() for t in tarea.get('tags', [])]
    return (
        any(c in carpeta_lower for c in CARPETAS_SALUD)
        or any(t in tags_lower for t in ETIQUETAS_SALUD)
    )


def _parsear_fecha_ticktick(fecha_str: str):
    try:
        fecha_limpia = re.sub(r'\.\d+', '', fecha_str)
        return datetime.strptime(fecha_limpia, "%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        return None

def _esta_fuera_de_margen(tarea: dict, carpeta: str, ahora) -> bool:
    print("TAREA:", tarea.get("title"))
    print("DUE:", tarea.get("dueDate"))
    print("AHORA:", ahora)
    if tarea.get('isAllDay', True):
        return False
    if 'dueDate' not in tarea:
        return False

    hora_tarea = _parsear_fecha_ticktick(tarea['dueDate'])
    print("RAW:", tarea["dueDate"])
    print("PARSEADA:", hora_tarea)
    print("BOGOTA:", hora_tarea.astimezone(ZoneInfo("America/Bogota")))
    print("UTC:", hora_tarea.astimezone(ZoneInfo("UTC")))
    print("timeZone:", tarea.get("timeZone"))
    if not hora_tarea:
        return False

    restricciones = clasificar_tarea(
        titulo=tarea.get('title', ''),
        etiquetas=tarea.get('tags', []),
        carpeta=carpeta,
        tiene_hora_especifica=True
    )
    margen_minutos = restricciones.get('margen_minutos', 120)
    
    limite = hora_tarea + timedelta(minutes=margen_minutos)

    print("FUERA:", ahora.timestamp() > limite.timestamp())
    return ahora.timestamp() > limite.timestamp()

def es_horario_estricto_recurrente(tarea: dict, carpeta: str) -> bool:
    """
    ¿Esta tarea es una rutina recurrente con hora fija ("Tipo A")?

    OJO: esta funcion se usa en DOS lugares con propositos distintos:
      1. main.py -> calcular_peso_psicologico(): decide si se PERDONA
         el atraso (dias_atraso=0) en el score. Las rutinas de salud
         SI deben seguir perdonandose aqui (no acumular culpa numerica
         visible dia tras dia, ver discusion clinica con el usuario).
      2. (ANTES) este mismo archivo -> procesar_horario_estricto_vencido():
         decidia si el scheduler podia auto-completar/saltar la tarea.
         Esto CAMBIO: ahora ese segundo uso pasa por puede_auto_completarse()
         (mas abajo), que añade la excepcion de salud. Esta funcion
         original se mantiene intacta para no romper el perdon de atraso.
    """

    print("=== CLASIFICACION ===")
    print("Titulo:", tarea.get('title'))
    print("RepeatFlag:", tarea.get('repeatFlag'))

    if not tarea.get('repeatFlag'):
        return False

    restricciones = clasificar_tarea(
        titulo=tarea.get('title', ''),
        etiquetas=tarea.get('tags', []),
        carpeta=carpeta,
        tiene_hora_especifica=not tarea.get('isAllDay', True)
    )

    print("Restricciones:", restricciones)

    return bool(
        restricciones.get('hora_importa')
        and not restricciones.get('ventana')
    )


def puede_auto_completarse(tarea: dict, carpeta: str) -> bool:
    """
    Variante de es_horario_estricto_recurrente() especifica para decidir
    si el SCHEDULER en background puede auto-completar/saltar esta
    ocurrencia vencida.

    Misma logica de "recurrente + hora fija", PERO con una excepcion
    dura: las tareas criticas de salud (carpeta health/salud, o
    etiqueta medicine/medicina) NUNCA se auto-completan, sin importar
    que sean recurrentes. Esto es justo el bug reportado: "Aplicar
    acido en espalda" se estaba completando sola sin que el usuario la
    viera ni decidiera nada.
    """
    if _es_critica_salud(tarea, carpeta):
        return False
    return es_horario_estricto_recurrente(tarea, carpeta)

def tarea_es_horario_estricto_vencida(tarea: dict, carpeta: str, ahora=None) -> bool:
    ahora = ahora or datetime.now(BOGOTA)

    if not es_horario_estricto_recurrente(tarea, carpeta):
        return False

    return _esta_fuera_de_margen(tarea, carpeta, ahora)


def contar_perdidas_consecutivas_salud(tarea_id: str, dias_hacia_atras: int = 7) -> int:
    """
    Cuenta cuantos dias CONSECUTIVOS, mirando hacia atras desde hoy
    (sin incluir hoy), esta tarea de salud NO tuvo ninguna interaccion
    positiva ('completada', 'avance_parcial', 'paso1_realizado') a
    pesar de tener registro de actividad ese dia.

    Esto NO es para mostrar culpa numerica al usuario (no se expone
    "llevas N dias sin hacerlo" en el frontend) -- es una señal interna
    para que main.py decida si subir la prioridad/boost al dia
    siguiente, sin acumular dias_atraso como si fuera un evento unico.

    Implementacion: miramos, dia por dia hacia atras, si hubo alguna
    accion de movimiento ('completada', 'avance_parcial',
    'paso1_realizado') para esa tarea_id. Contamos dias sin movimiento
    hasta el primer dia que SI tuvo movimiento (ahi se rompe la racha).
    Si no hay ningun registro en absoluto para esa tarea_id, devolvemos
    0 (no podemos asumir perdidas sin evidencia de que la tarea estuviera
    activa esos dias).
    """
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        limite = (datetime.now(BOGOTA) - timedelta(days=dias_hacia_atras)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            SELECT date(timestamp) as dia, accion FROM interacciones
            WHERE tarea_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        """, (tarea_id, limite))
        filas = cursor.fetchall()
        conn.close()

        if not filas:
            return 0

        acciones_por_dia = {}
        for dia, accion in filas:
            acciones_por_dia.setdefault(dia, []).append(accion)

        hoy_str = datetime.now(BOGOTA).strftime("%Y-%m-%d")
        dias_ordenados = sorted(acciones_por_dia.keys(), reverse=True)

        ACCIONES_MOVIMIENTO = ('completada', 'avance_parcial', 'paso1_realizado')
        perdidas = 0
        for dia in dias_ordenados:
            if dia == hoy_str:
                continue  # no contamos el dia actual, solo dias pasados completos
            acciones_del_dia = acciones_por_dia[dia]
            tuvo_movimiento = any(a in ACCIONES_MOVIMIENTO for a in acciones_del_dia)
            if tuvo_movimiento:
                break
            perdidas += 1

        return perdidas
    except Exception:
        return 0

def _ya_fue_marcada_desconocida(tarea_id: str, due_date: str) -> bool:
    """
    CLAVE LÓGICA: tarea_id + dueDate
    Comprobamos si ESTA ocurrencia exacta ya fue neutralizada.
    """
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        # Buscamos en metadata_ia la coincidencia exacta de la fecha
        cursor.execute('''
            SELECT COUNT(*) FROM interacciones
            WHERE tarea_id = ?
            AND accion IN ('omitida_auto')
            AND metadata_ia LIKE ?
        ''', (tarea_id, f'%"{due_date}"%'))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False

def procesar_horario_estricto_vencido(headers: dict, mapa_carpetas: dict, registrar_interaccion_fn):
    
    print("="*80)
    traceback.print_stack(limit=6)
    print("="*80)

    print(">>> procesar_horario_estricto_vencido EJECUTANDOSE")
    
    ahora = datetime.now(BOGOTA)
    procesadas = 0

    try:
        url_listas = "https://api.ticktick.com/open/v1/project"
        resp_listas = requests.get(url_listas, headers=headers, timeout=10)
        if resp_listas.status_code != 200:
            return procesadas
        listas = resp_listas.json()
    except requests.exceptions.RequestException as e:
        print(f"[horario_estricto] No se pudo listar proyectos: {e}")
        return procesadas

    for lista in listas:
        if lista.get('closed') or lista.get('isClosed'):
            continue

        nombre_carpeta = lista.get('name', 'Inbox')
        url_tareas = f"https://api.ticktick.com/open/v1/project/{lista['id']}/data"

        try:
            resp_tareas = requests.get(url_tareas, headers=headers, timeout=10)
            if resp_tareas.status_code != 200:
                continue
            tareas = resp_tareas.json().get('tasks', [])
        except requests.exceptions.RequestException as e:
            continue

        for tarea in tareas:
            print(tarea.get("title"))
            if "aplicar acido" in tarea.get("title", "").lower():
                print("\n=== TAREA ENCONTRADA ===")
                print(json.dumps(tarea, indent=2, ensure_ascii=False))
                print("========================\n")
            if tarea.get('status', 0) != 0:
                continue

            # SOLO actuamos sobre rutinas (Tipo A) que NO sean criticas de
            # salud. Los vuelos, citas medicas, Y AHORA TAMBIEN cualquier
            # rutina de salud (ej. "Aplicar acido en espalda") nunca
            # entran aqui: se quedan vencidas/rojas para que el usuario
            # gestione el momento el mismo, sin que el sistema asuma que
            # ya lo hizo.
            if not puede_auto_completarse(tarea, nombre_carpeta):
                continue
            
            print("ANTES DEL IF")

            if not _esta_fuera_de_margen(tarea, nombre_carpeta, ahora):
                continue
            
            print("DESPUES DEL IF")
            
            due_date_str = tarea.get('dueDate')
            if not due_date_str:
                continue

            if not _reclamar_procesamiento(tarea['id'], due_date_str):
                continue
            
            print("CHECK BD")
            print(tarea["title"])
            print(due_date_str)

            ya = _ya_fue_marcada_desconocida(
                tarea["id"],
                due_date_str
            )

            print("YA REGISTRADA:", ya)

            if _ya_fue_marcada_desconocida(tarea['id'], due_date_str):
                continue

            proyecto_id = tarea.get('projectId', lista['id'])
            tarea_id = tarea['id']
            url_complete = f"https://api.ticktick.com/open/v1/project/{proyecto_id}/task/{tarea_id}/complete"

            try:
                print("VA A COMPLETAR")
                print(url_complete)
                # 1. MECÁNICA NECESARIA: Completamos la tarea en TickTick para "saltar" 
                # la instancia perdida y forzar a que TickTick genere la siguiente.
                resp = requests.post(url_complete, headers=headers, timeout=10)
                print("STATUS:", resp.status_code)
                print(resp.text)
                if resp.status_code != 200:
                    continue

                # 2. HISTORIAL REAL: Aunque en TickTick se marcó "completada", en nuestra
                # base de datos clínica sabemos la verdad: el sistema la omitió por vencimiento.
                metadata = json.dumps({"due_date": due_date_str})
                registrar_interaccion_fn(
                    tarea_id=tarea_id,
                    tarea_nombre=tarea.get('title', 'Desconocida'),
                    energia="desconocida",
                    accion="omitida_auto", # Nueva etiqueta para saber que fue el bot
                    emocion=None,
                    carpeta=nombre_carpeta,
                    etiquetas=",".join(tarea.get('tags', [])),
                    metadata_ia=metadata
                )
                print("INTERACCION REGISTRADA")
                procesadas += 1
                print(f"[horario_estricto] Cíclica vencida auto-saltada: '{tarea.get('title')}' (Instancia: {due_date_str})")
            except Exception as e:
                print(f"[horario_estricto] Error registrando '{tarea.get('title')}': {e}")

    return procesadas

def init_tabla_lock_horario_estricto():
    conn = sqlite3.connect('atypical_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lock_horario_estricto (
            tarea_id TEXT NOT NULL,
            due_date TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (tarea_id, due_date)
        )
    ''')
    conn.commit()
    conn.close()


def _reclamar_procesamiento(tarea_id: str, due_date: str) -> bool:
    """
    Reserva, de forma ATOMICA, el derecho a procesar esta ocurrencia
    (tarea_id + due_date) de una tarea de horario estricto. Devuelve
    True solo si este proceso gano la reserva. Si dos procesos del
    scheduler corren en paralelo, el segundo recibira un
    IntegrityError (la fila ya existe) y devolvera False — sin haber
    tocado TickTick todavia. Eso es justo lo que evita la duplicacion:
    antes se chequeaba con un SELECT y LUEGO se actuaba, dejando una
    ventana en la que dos procesos podian pasar el chequeo a la vez.
    """
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO lock_horario_estricto (tarea_id, due_date) VALUES (?, ?)",
            (tarea_id, due_date)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception:
        return False