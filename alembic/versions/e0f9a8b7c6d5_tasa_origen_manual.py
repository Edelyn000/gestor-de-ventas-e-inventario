"""tasa_origen_manual

Habilita la "Tasa Manual" del POS: la tasa de cambio pasa de ser
exclusivamente BCV a tener un ORIGEN (`BCV` | `MANUAL`).

- `TasaCambio.origen` (VARCHAR(20) NOT NULL, default `'BCV'`):
  quien registro la tasa. La manual (efimera del POS) nunca es la
  tasa "activa" global de otras pantallas (tasa_activa() filtra BCV).
- `TasaCambio.registrado_por` (VARCHAR(100) NULL): usuario que fijo
  la tasa manual.
- El indice UNIQUE sobre `fecha` se reemplaza por uno compuesto
  `(fecha, origen)`: el mismo dia puede tener una fila BCV y una
  manual sin colisionar.

Idempotente con Inspector (patron de las migraciones previas). Las
filas existentes se rellenan con origen='BCV' (server_default).

Nota: el backup pre-migracion de la BD real esta en
`%TEMP%\\opencode\\database.db.bak_tasa_manual`.

Revision ID: e0f9a8b7c6d5
Revises: d9f8e7d6c5b4
Create Date: 2026-09-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op
from sistema_financiero.models.conexion import engine

# revision identifiers, used by Alembic.
revision: str = "e0f9a8b7c6d5"
down_revision: str | Sequence[str] | None = "d9f8e7d6c5b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLA = "tasacambio"
_INDICE_COMPUESTO = "uq_tasacambio_fecha_origen"


def _indice_unico_sobre(inspector: Inspector, columnas: list[str]) -> list[str]:
    """Nombres de los indices UNIQUE que cubren exactamente `columnas`."""
    nombres: list[str] = []
    for indice in inspector.get_indexes(_TABLA):
        if indice.get("unique") and list(indice.get("column_names") or []) == columnas:
            nombres.append(str(indice["name"]))
    return nombres


def upgrade() -> None:
    """Agrega origen/registrado_por y el indice unico (fecha, origen)."""
    inspector = Inspector.from_engine(engine)
    columnas = [c["name"] for c in inspector.get_columns(_TABLA)]

    # 1) Columna origen (NOT NULL con default para las filas existentes).
    if "origen" not in columnas:
        with op.batch_alter_table(_TABLA) as batch:
            batch.add_column(
                sa.Column(
                    "origen",
                    sa.VARCHAR(length=20),
                    nullable=False,
                    server_default=sa.text("'BCV'"),
                ),
            )

    # 2) Columna registrado_por (solo tasa manual).
    if "registrado_por" not in columnas:
        with op.batch_alter_table(_TABLA) as batch:
            batch.add_column(
                sa.Column("registrado_por", sa.VARCHAR(length=100), nullable=True),
            )

    # Refrescar el inspector (el batch SQLite recrea la tabla).
    inspector = Inspector.from_engine(engine)

    # 3) El indice UNIQUE viejo sobre fecha se reemplaza por el compuesto.
    for nombre in _indice_unico_sobre(inspector, ["fecha"]):
        op.drop_index(op.f(nombre), table_name=_TABLA)

    # 4) Indice UNIQUE compuesto (fecha, origen) si no existe ya.
    inspector = Inspector.from_engine(engine)
    ya_existe = _indice_unico_sobre(inspector, ["fecha", "origen"])
    if not ya_existe:
        op.create_index(
            op.f(_INDICE_COMPUESTO),
            _TABLA,
            ["fecha", "origen"],
            unique=True,
        )


def downgrade() -> None:
    """Revierte: devuelve el UNIQUE sobre fecha y elimina las columnas."""
    inspector = Inspector.from_engine(engine)

    # 1) Eliminar el indice compuesto.
    for nombre in _indice_unico_sobre(inspector, ["fecha", "origen"]):
        op.drop_index(op.f(nombre), table_name=_TABLA)

    # 2) Eliminar las columnas (SQLite: batch).
    columnas = [c["name"] for c in inspector.get_columns(_TABLA)]
    with op.batch_alter_table(_TABLA) as batch:
        if "registrado_por" in columnas:
            batch.drop_column("registrado_por")
        if "origen" in columnas:
            batch.drop_column("origen")

    # 3) Restaurar el UNIQUE sobre fecha si no existe.
    inspector = Inspector.from_engine(engine)
    if not _indice_unico_sobre(inspector, ["fecha"]):
        op.create_index(
            op.f("ix_tasacambio_fecha"),
            _TABLA,
            ["fecha"],
            unique=True,
        )
