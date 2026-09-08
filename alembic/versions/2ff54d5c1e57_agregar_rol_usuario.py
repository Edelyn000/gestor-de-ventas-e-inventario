"""agregar_rol_usuario

Revision ID: 2ff54d5c1e57
Revises: ab3fe2c913aa
Create Date: 2026-07-09 12:30:50.422042

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '2ff54d5c1e57'
down_revision: str | Sequence[str] | None = 'ab3fe2c913aa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'usuario',
        sa.Column('rol', sa.String(length=20), nullable=False, server_default='VENDEDOR'),
    )


def downgrade() -> None:
    op.drop_column('usuario', 'rol')
