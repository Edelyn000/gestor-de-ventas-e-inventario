"""auditoria_anulacion_venta

Agrega a `venta` las columnas de auditoria de anulacion:
- `motivo_anulacion` (texto libre exigido por el dialogo de anulacion).
- `anulado_por` (usuario ADMINISTRADOR que autorizo con sus credenciales,
  NO el cajero que registro la venta).

Idempotente con Inspector (patron de las migraciones previas): si las
columnas ya existen (p. ej. el ORM las habia creado via create_db_and_tables)
no se toca nada.

Revision ID: d9f8e7d6c5b4
Revises: c8d7e6f5a4b3
Create Date: 2026-09-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op
from sistema_financiero.models.conexion import engine

# revision identifiers, used by Alembic.
revision: str = "d9f8e7d6c5b4"
down_revision: str | Sequence[str] | None = "c8d7e6f5a4b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Agrega motivo_anulacion y anulado_por a venta (idempotente).
def upgrade() -> None:
    """Agrega motivo_anulacion y anulado_por a venta (idempotente)."""
    inspector = Inspector.from_engine(engine)
    columnas_venta = [c["name"] for c in inspector.get_columns("venta")]

    if "motivo_anulacion" not in columnas_venta:
        with op.batch_alter_table("venta") as batch:
            batch.add_column(sa.Column("motivo_anulacion", sa.VARCHAR(length=255), nullable=True))
    if "anulado_por" not in columnas_venta:
        with op.batch_alter_table("venta") as batch:
            batch.add_column(sa.Column("anulado_por", sa.VARCHAR(length=100), nullable=True))


# Revierte: elimina las columnas de auditoria (SQLite: batch).
def downgrade() -> None:
    """Revierte: elimina las columnas de auditoria (SQLite: batch)."""
    inspector = Inspector.from_engine(engine)
    columnas_venta = [c["name"] for c in inspector.get_columns("venta")]

    with op.batch_alter_table("venta") as batch:
        if "anulado_por" in columnas_venta:
            batch.drop_column("anulado_por")
        if "motivo_anulacion" in columnas_venta:
            batch.drop_column("motivo_anulacion")
