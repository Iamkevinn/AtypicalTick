# request_models.py
#
# max_length en los campos de texto libre: sin esto, cualquier campo
# aceptaba un string de tamaño arbitrario. El riesgo principal no es
# tanto seguridad (esta API ya exige sesión) sino costo/abuso -- los
# campos que terminan en un prompt de Gemini (PeticionBloqueo, sobre
# todo) significan tokens reales pagados por cada caracter de más, y
# los que van a SQLite (interacciones, correcciones, etc.) pueden
# inflar la base de datos sin límite. Los límites son generosos --
# muy por encima de lo que alguien escribiría a mano -- para no
# estorbar el uso normal.
from pydantic import BaseModel, Field
from typing import Optional

class PeticionAutocuidado(BaseModel):
    tipo: str = Field(..., max_length=200)

class PeticionFeedbackDiscrepancia(BaseModel):
    motivo_declarado: str = Field(..., max_length=2000)
    energia: str = Field(..., max_length=50)
    intervencion_sugerida: str = Field(..., max_length=500)
    respuesta: str = Field(..., max_length=500)

class PeticionCorreccion(BaseModel):
    tarea_id: str = Field(..., max_length=200)
    tipo_decision: str = Field(..., max_length=200)
    valor_original: str = Field(..., max_length=2000)
    correccion: str = Field(..., max_length=2000)
    carpeta: str = Field("Inbox", max_length=200)

class PeticionRechazo(BaseModel):
    tarea_nombre: str = Field("Desconocida", max_length=500)
    energia: str = Field("desconocida", max_length=50)
    carpeta: str = Field("Inbox", max_length=200)
    intencion: str = Field("Sin intencion", max_length=2000)

class PeticionPosponer(BaseModel):
    tarea_nombre: str = Field("Desconocida", max_length=500)
    energia: str = Field("desconocida", max_length=50)
    carpeta: str = Field("Inbox", max_length=200)
    motivo_posponer: str = Field("Sin motivo", max_length=2000)
    bloqueo_previo: str = Field("Ninguno", max_length=500)
    intervencion_usada: str = Field("Ninguna", max_length=500)

class TareaNueva(BaseModel):
    texto: str = Field(..., max_length=1000)

class PeticionPrediccion(BaseModel):
    tarea_id: str = Field(..., max_length=200)
    tarea_nombre: str = Field("Desconocida", max_length=500)
    prediccion: str = Field(..., max_length=2000)
    energia: str = Field("desconocida", max_length=50)
    carpeta: str = Field("Inbox", max_length=200)

class PeticionBloqueo(BaseModel):
    tarea_id: str = Field("ID_DESCONOCIDO", max_length=200)
    titulo_tarea: str = Field(..., max_length=500)
    descripcion_tarea: str = Field("", max_length=5000)
    motivo: str = Field(..., max_length=2000)
    energia: str = Field("desconocida", max_length=50)
    carpeta: str = Field("", max_length=200)
    etiquetas: list[str] = []
    patron_historico: Optional[str] = Field(None, max_length=2000)

class PeticionLogin(BaseModel):
    # Límite alto (no queremos rechazar contraseñas largas legítimas),
    # solo para que nadie mande megabytes de texto a pbkdf2_hmac.
    password: str = Field(..., max_length=1000)

class PeticionChequeoFidelidad(BaseModel):
    respuesta: str = Field(..., max_length=10)  # "si" o "no"
    tarea_nombre: str = Field("Desconocida", max_length=500)
    energia: str = Field("desconocida", max_length=50)
    carpeta: str = Field("Inbox", max_length=200)