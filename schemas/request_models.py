from pydantic import BaseModel

class PeticionAutocuidado(BaseModel):
    tipo: str

class PeticionFeedbackDiscrepancia(BaseModel):
    motivo_declarado: str
    energia: str
    intervencion_sugerida: str
    respuesta: str

class PeticionCorreccion(BaseModel):
    tarea_id: str
    tipo_decision: str
    valor_original: str
    correccion: str
    carpeta: str = "Inbox"

class PeticionRechazo(BaseModel):
    tarea_nombre: str = "Desconocida"
    energia: str = "desconocida"
    carpeta: str = "Inbox"
    intencion: str = "Sin intencion"

class PeticionPosponer(BaseModel):
    tarea_nombre: str = "Desconocida"
    energia: str = "desconocida"
    carpeta: str = "Inbox"
    motivo_posponer: str = "Sin motivo"
    bloqueo_previo: str = "Ninguno"
    intervencion_usada: str = "Ninguna"

class TareaNueva(BaseModel):
    texto: str

class PeticionPrediccion(BaseModel):
    tarea_id: str
    tarea_nombre: str = "Desconocida"
    prediccion: str
    energia: str = "desconocida"
    carpeta: str = "Inbox"

class PeticionBloqueo(BaseModel):
    tarea_id: str = "ID_DESCONOCIDO"
    titulo_tarea: str
    descripcion_tarea: str = ""
    motivo: str
    energia: str = "desconocida"
    carpeta: str = ""
    etiquetas: list[str] = []
    patron_historico: str = None