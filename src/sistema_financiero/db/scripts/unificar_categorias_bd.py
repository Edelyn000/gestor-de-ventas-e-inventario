# unificar_categorias_bd.py: Script de migracion: unifica categorias duplicadas.

import shutil
from pathlib import Path

from alembic.config import Config
from sqlmodel import Session, select

from alembic import command
from sistema_financiero.models import Categoria, Producto, conexion


def _verificar() -> None:
    """Comprueba que la migracion quedo aplicada correctamente."""
    with Session(conexion.engine) as sesion:
        categorias = sesion.exec(select(Categoria).order_by(Categoria.nombre)).all()
        total_productos = len(sesion.exec(select(Producto)).all())
        con_categoria = len(
            sesion.exec(
                select(Producto).where(Producto.categoria_id != None),  # noqa: E711
            ).all(),
        )
        print(f"CATEGORIAS ({len(categorias)}): {[c.nombre for c in categorias]}")
        print(f"PRODUCTOS: {total_productos} totales, {con_categoria} con categoria")
        duplicados = [c.nombre for c in categorias if c.clave != c.clave.lower()]
        if duplicados:
            print(f"ADVERTENCIA claves con mayusculas: {duplicados}")


def main() -> None:
    ruta_bd = Path(conexion.DB_PATH)
    if not ruta_bd.exists():
        print(f"NO hay BD en {ruta_bd} — nada que migrar.")
        return

    backup_dir = Path.home() / "AppData" / "Local" / "Temp" / "opencode"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / "database.db.bak_categorias"
    shutil.copy2(ruta_bd, backup)
    print(f"BACKUP creado: {backup}")

    cfg = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    command.upgrade(cfg, "head")
    print("MIGRACION alembic upgrade head aplicada.")

    _verificar()


if __name__ == "__main__":
    main()

