"""agrega_microhabitos_y_pospuestas_hoy

Revision ID: 99d831b25e91
Revises: 542826e5466e
Create Date: 2026-08-06 21:32:41.087109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99d831b25e91'
down_revision: Union[str, Sequence[str], None] = '542826e5466e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "microhabitos_estado",
        sa.Column("categoria", sa.Text, primary_key=True),
        sa.Column("ultima_vez", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snooze_hasta", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "microhabitos_historial",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("categoria", sa.Text, nullable=False),
        sa.Column("hora", sa.Integer, nullable=False),
        sa.Column("dia_semana", sa.Integer, nullable=False),
        sa.Column("accion", sa.Text, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_microhabitos_historial_categoria_hora",
        "microhabitos_historial",
        ["categoria", "hora"],
    )

    op.create_table(
        "pospuestas_hoy",
        sa.Column("tarea_id", sa.Text, nullable=False),
        sa.Column("fecha", sa.Text, nullable=False),
        sa.Column("veces", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ultima_vez", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tarea_id", "fecha", name="uq_pospuestas_hoy_tarea_fecha"),
    )


def downgrade() -> None:
    op.drop_table("pospuestas_hoy")
    op.drop_index("ix_microhabitos_historial_categoria_hora", table_name="microhabitos_historial")
    op.drop_table("microhabitos_historial")
    op.drop_table("microhabitos_estado")