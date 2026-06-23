import sqlite3

def init_tabla_feedback():
    conn = sqlite3.connect('atypical_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback_discrepancia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            motivo_declarado TEXT,
            energia TEXT,
            intervencion_sugerida TEXT,
            respuesta TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def registrar_feedback_discrepancia(motivo_declarado: str, energia: str, intervencion_sugerida: str, respuesta: str):
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO feedback_discrepancia (motivo_declarado, energia, intervencion_sugerida, respuesta)
            VALUES (?, ?, ?, ?)
        ''', (motivo_declarado, energia, intervencion_sugerida, respuesta))
        conn.commit()
        conn.close()
    except Exception as e:
        print("🚨 Error al guardar feedback de discrepancia:", e)

def fue_rechazada_antes(motivo_declarado: str, energia: str, intervencion_sugerida: str) -> bool:
    try:
        conn = sqlite3.connect('atypical_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT respuesta FROM feedback_discrepancia
            WHERE motivo_declarado = ? AND energia = ? AND intervencion_sugerida = ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (motivo_declarado, energia, intervencion_sugerida))
        fila = cursor.fetchone()
        conn.close()
        
        # Si el último feedback para esta combinación fue "no_es_eso", respetamos el rechazo
        if fila and fila[0] == 'no_es_eso':
            return True
        return False
    except Exception:
        return False