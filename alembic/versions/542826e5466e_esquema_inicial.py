"""esquema_inicial

Revision ID: 542826e5466e
Revises:
Create Date: 2026-07-20 21:33:30.715070

Esta migración reemplaza a los init_tabla_*()/CREATE TABLE IF NOT EXISTS
que antes vivían esparcidos en 7 archivos distintos (main.py,
auth_service.py, auth_ticktick.py, y en core/: feedback_discrepancia.py,
prediccion_vs_resultado.py, correccion_decisiones.py,
gestion_horario_estricto.py).

Se usa sa.Integer(primary_key=True) en vez de "INTEGER PRIMARY KEY
AUTOINCREMENT" (sintaxis exclusiva de SQLite) -- SQLAlchemy/Alembic
traduce esto automáticamente a la sintaxis correcta de cada motor
(AUTOINCREMENT en SQLite, GENERATED ALWAYS AS IDENTITY en Postgres).
Esto resuelve el punto de la Fase 3 sobre AUTOINCREMENT directamente
aquí, para el schema. El código que hace INSERT/SELECT/UPDATE ya fue
adaptado en la Fase 1 (repositories/db_repository.py) y no necesita
más cambios.

Las columnas que main.py agregaba con ALTER TABLE ADD COLUMN (etiquetas,
metadata_ia, dia_semana, carpeta en interacciones; energia, carpeta en
sesiones_tarea) se incluyen directamente en el CREATE TABLE aquí, ya que
esta es la migración fundacional para una base de datos nueva (Postgres)
-- no hace falta repetir el parche histórico.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '542826e5466e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "interacciones",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tarea_id", sa.Text),
        sa.Column("tarea_nombre", sa.Text),
        sa.Column("energia", sa.Text),
        sa.Column("emocion_motivo", sa.Text),
        sa.Column("accion", sa.Text),
        sa.Column("hora", sa.Integer),
        sa.Column("dia_semana", sa.Text),
        sa.Column("carpeta", sa.Text),
        sa.Column("etiquetas", sa.Text),
        sa.Column("metadata_ia", sa.Text),
        sa.Column("timestamp", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "sesiones_tarea",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tarea_id", sa.Text),
        sa.Column("bloqueo_inicial", sa.Text),
        sa.Column("intervencion_usada", sa.Text),
        sa.Column("resultado_final", sa.Text),
        sa.Column("energia", sa.Text),
        sa.Column("carpeta", sa.Text),
        sa.Column("timestamp", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "sesiones_auth",
        sa.Column("token_hash", sa.Text, primary_key=True),
        sa.Column("creado_en", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expira_en", sa.DateTime, nullable=False),
        sa.Column("ultimo_uso", sa.DateTime),
    )

    op.create_table(
        "intentos_login",
        sa.Column("ip", sa.Text, primary_key=True),
        sa.Column("intentos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("primer_intento", sa.DateTime, nullable=False),
        sa.Column("bloqueado_hasta", sa.DateTime),
    )

    op.create_table(
        "tokens_oauth",
        sa.Column("user_id", sa.Text, primary_key=True),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("refresh_token", sa.Text),
        sa.Column("expires_at", sa.DateTime),
        sa.Column("timestamp_actualizado", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "predicciones",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tarea_id", sa.Text),
        sa.Column("tarea_nombre", sa.Text),
        sa.Column("prediccion", sa.Text),
        sa.Column("energia", sa.Text),
        sa.Column("carpeta", sa.Text),
        sa.Column("resultado_real", sa.Text),
        sa.Column("timestamp_prediccion", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("timestamp_resultado", sa.DateTime),
    )

    op.create_table(
        "feedback_discrepancia",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("motivo_declarado", sa.Text),
        sa.Column("energia", sa.Text),
        sa.Column("intervencion_sugerida", sa.Text),
        sa.Column("respuesta", sa.Text),
        sa.Column("timestamp", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "correcciones_usuario",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tarea_id", sa.Text),
        sa.Column("tipo_decision", sa.Text),
        sa.Column("valor_original", sa.Text),
        sa.Column("correccion", sa.Text),
        sa.Column("carpeta", sa.Text),
        sa.Column("timestamp", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "lock_horario_estricto",
        sa.Column("tarea_id", sa.Text, nullable=False),
        sa.Column("due_date", sa.Text, nullable=False),
        sa.Column("timestamp", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("tarea_id", "due_date"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("lock_horario_estricto")
    op.drop_table("correcciones_usuario")
    op.drop_table("feedback_discrepancia")
    op.drop_table("predicciones")
    op.drop_table("tokens_oauth")
    op.drop_table("intentos_login")
    op.drop_table("sesiones_auth")
    op.drop_table("sesiones_tarea")
    op.drop_table("interacciones")
