"""categoria_normalizada_y_fk_producto

Crea la tabla `categoria` (nombre UNICO por clave normalizada: sin
tildes y case-insensitive) y reemplaza la columna libre
`producto.categoria` por una FK `producto.categoria_id`.

Flujo (idempotente con Inspector, como las migraciones previas):
  1. Crea `categoria` si no existe (id, nombre, clave UNIQUE indexada).
  2. Agrega `producto.categoria_id` con FK a `categoria` si falta.
  3. DATA-MIGRACION: lee los valores DISTINTOS de `producto.categoria`,
     normaliza cada uno (clave sin tildes/minusculas; 'Limpieza' y
     'LIMPIEZA' → UNA sola fila) y backfillea `categoria_id`.
     Ninguna categoria existente se pierde (los productos sin
     categoria quedan con NULL).
  4. Elimina la columna legada `producto.categoria` + su indice.

Revision ID: c8d7e6f5a4b3
Revises: b7c1d2e3f4a5
Create Date: 2026-09-23 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op
from sistema_financiero.models.conexion import engine
from sistema_financiero.utils import clave_normalizada, normalizar_nombre_categoria

# revision identifiers, used by Alembic.
revision: str = "c8d7e6f5a4b3"
down_revision: str | Sequence[str] | None = "b7c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Crea categoria + FK y migra los datos existentes (idempotente).
def upgrade() -> None:
    """Crea categoria + FK y migra los datos existentes (idempotente)."""
    inspector = Inspector.from_engine(engine)
    tablas = inspector.get_table_names()

    # 1) Tabla categoria (si no existe).
    if "categoria" not in tablas:
        op.create_table(
            "categoria",
            sa.Column("id", sa.INTEGER(), nullable=False),
            sa.Column("nombre", sa.VARCHAR(length=100), nullable=False),
            sa.Column("clave", sa.VARCHAR(length=100), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_categoria_clave"), "categoria", ["clave"], unique=True)

    columnas_producto = [c["name"] for c in inspector.get_columns("producto")]

    # 2) Columna FK producto.categoria_id (si falta; SQLite recrea la tabla).
    # OJO: en modo batch SQLite el FK debe llevar nombre explicito.
    if "categoria_id" not in columnas_producto:
        with op.batch_alter_table("producto") as batch:
            batch.add_column(
                sa.Column(
                    "categoria_id",
                    sa.INTEGER(),
                    sa.ForeignKey("categoria.id", name="fk_producto_categoria_id"),
                    nullable=True,
                ),
            )
        op.create_index(
            op.f("ix_producto_categoria_id"),
            "producto",
            ["categoria_id"],
            unique=False,
        )

    # 3) DATA-MIGRACION: poblar categoria con los valores existentes y backfillear categoria_id.
    if "categoria" in columnas_producto:
        bind = op.get_bind()
        filas = bind.execute(
            sa.text(
                "SELECT DISTINCT categoria FROM producto "
                "WHERE categoria IS NOT NULL AND TRIM(categoria) <> ''",
            ),
        ).fetchall()

        claves_registradas = {
            fila[0] for fila in bind.execute(sa.text("SELECT clave FROM categoria")).fetchall()
        }
        for (valor,) in filas:
            clave = clave_normalizada(valor)
            if clave not in claves_registradas:
                bind.execute(
                    sa.text(
                        "INSERT INTO categoria (nombre, clave) VALUES (:nombre, :clave)",
                    ),
                    {"nombre": normalizar_nombre_categoria(valor), "clave": clave},
                )
                claves_registradas.add(clave)

        for (valor,) in filas:
            bind.execute(
                sa.text(
                    "UPDATE producto SET categoria_id = "
                    "(SELECT c.id FROM categoria c WHERE c.clave = :clave) "
                    "WHERE TRIM(categoria) = :valor AND categoria_id IS NULL",
                ),
                {"clave": clave_normalizada(valor), "valor": valor},
            )

        # 4) Eliminar la columna legada y su indice (SQLite: batch).
        with op.batch_alter_table("producto") as batch:
            batch.drop_index("ix_producto_categoria")
            batch.drop_column("categoria")


# Revierte: devuelve producto.
def downgrade() -> None:
    """Revierte: devuelve producto.categoria y elimina categoria."""
    inspector = Inspector.from_engine(engine)
    columnas_producto = [c["name"] for c in inspector.get_columns("producto")]
    bind = op.get_bind()

    # Reagregar la columna legada con los nombres actuales (best effort).
    if "categoria" not in columnas_producto:
        with op.batch_alter_table("producto") as batch:
            batch.add_column(sa.Column("categoria", sa.VARCHAR(length=100), nullable=True))
        op.create_index(op.f("ix_producto_categoria"), "producto", ["categoria"], unique=False)
        bind.execute(
            sa.text(
                "UPDATE producto SET categoria = "
                "(SELECT c.nombre FROM categoria c WHERE c.id = producto.categoria_id)",
            ),
        )

    if "categoria_id" in columnas_producto:
        op.drop_index(op.f("ix_producto_categoria_id"), table_name="producto")
        with op.batch_alter_table("producto") as batch:
            batch.drop_column("categoria_id")

    if "categoria" in inspector.get_table_names():
        op.drop_index(op.f("ix_categoria_clave"), table_name="categoria")
        op.drop_table("categoria")
