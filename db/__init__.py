from repositories.db_repository import db_connection, execute, fetch_one, fetch_all
from .interacciones import registrar_interaccion

# NOTA (migración Supabase/Render):
# db_connection ya no viene de db/connection.py (que era SQLite puro).
# Ahora viene de repositories/db_repository.py, que decide entre SQLite
# y Postgres según si DATABASE_URL está configurada. Los 21 archivos que
# hacen `from db import db_connection` no necesitan ningún otro cambio
# para este paso -- siguen funcionando igual en desarrollo (SQLite).
#
# db/connection.py se deja intacto por ahora como referencia/rollback,
# se puede borrar una vez confirmemos que todo funciona con la nueva capa.