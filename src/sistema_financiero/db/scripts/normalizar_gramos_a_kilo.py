# normalizar_gramos_a_kilo.py: Script de datos: normaliza ventas GRAMOS a KILO.

import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from sqlmodel import Session, select

from sistema_financiero.models import Producto, conexion
from sistema_financiero.utils import (
    GRAMOS_POR_KILO,
    TIPO_VENTA_GRAMOS_LEGADO,
    TIPO_VENTA_PESO,
    normalizar_unidad,
    redondear_moneda,
)


# Productos con tipo de venta 'GRAMOS' de una version anterior.
def _productos_legados(sesion: Session) -> list[Producto]:
    """Productos con tipo de venta 'GRAMOS' de una version anterior."""
    return list(
        sesion.exec(
            select(Producto).where(Producto.tipo_venta == TIPO_VENTA_GRAMOS_LEGADO),
        ).all(),
    )


# Multiplica un precio por gramo por GRAMOS_POR_KILO (a 2 decimales).
def _escalar_precio(valor: Decimal | int | float | None) -> Decimal:
    """Multiplica un precio por gramo por GRAMOS_POR_KILO (a 2 decimales)."""
    return redondear_moneda(Decimal(str(valor or 0)) * GRAMOS_POR_KILO)


# Confirma que no queda ningun producto en la escala por gramo.
def _verificar(sesion: Session) -> None:
    """Confirma que no queda ningun producto en la escala por gramo."""
    restantes = _productos_legados(sesion)
    if restantes:
        print(
            f"ERROR: quedan {len(restantes)} productos GRAMOS: "
            f"{[p.nombre_producto for p in restantes]}"
        )
        return
    print("VERIFICACION: 0 productos con tipo_venta 'GRAMOS'.")


# Normaliza en la BD los productos GRAMOS/GR a KILO.
def main() -> None:
    ruta_bd = Path(conexion.DB_PATH)
    if not ruta_bd.exists():
        print(f"NO hay BD en {ruta_bd} - nada que normalizar.")
        return

    with Session(conexion.engine) as sesion:
        legados = _productos_legados(sesion)
        if not legados:
            print("No hay productos 'GRAMOS': la BD ya esta normalizada (no se escribe).")
            _verificar(sesion)
            return

        print(f"Productos 'GRAMOS' encontrados: {len(legados)}")

        backup_dir = Path(tempfile.gettempdir())
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / "database.db.bak_gramos"
        shutil.copy2(ruta_bd, backup)
        print(f"BACKUP creado: {backup}")

        for producto in legados:
            unidad_nueva = normalizar_unidad(producto.unidad)
            antes = (
                f"unidad={producto.unidad} tipo={producto.tipo_venta} "
                f"usd={producto.precio_venta_usd}"
            )
            producto.unidad = unidad_nueva
            producto.tipo_venta = TIPO_VENTA_PESO
            producto.precio_compra = _escalar_precio(producto.precio_compra)
            producto.precio_venta_bs = _escalar_precio(producto.precio_venta_bs)
            producto.precio_venta_usd = _escalar_precio(producto.precio_venta_usd)
            sesion.add(producto)
            print(
                f"  #{producto.idproducto} {producto.nombre_producto}: "
                f"{antes} -> unidad={unidad_nueva} tipo=PESO "
                f"usd={producto.precio_venta_usd} (stock sin cambios: "
                f"{producto.stock_actual} kg)",
            )

        sesion.commit()
        print(f"OK: {len(legados)} producto(s) normalizado(s).")
        _verificar(sesion)


if __name__ == "__main__":
    main()
