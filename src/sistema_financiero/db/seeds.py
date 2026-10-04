# seeds.py: Datos semilla de productos y tasa.
from decimal import Decimal

from sqlmodel import Session, select

from sistema_financiero.utils import (
    TIPO_VENTA_UNIDAD,
    clave_normalizada,
    hoy,
    normalizar_nombre_categoria,
)

from ..models import (
    Categoria,
    Producto,
    TasaCambio,
    obtener_sesion,
)


# Crea productos de ejemplo si no hay ninguno (con categorias unicas).
def seed_productos(session: Session | None = None) -> None:
    """Crea productos de ejemplo si no hay ninguno (con categorias unicas)."""
    with obtener_sesion(session) as s:
        if s.exec(select(Producto)).first() is not None:
            return

        ids_categoria: dict[str, int] = {}
        for nombre in ("Alimentos", "Lácteos", "Aseo Personal", "Limpieza"):
            clave = clave_normalizada(nombre)
            existente = s.exec(
                select(Categoria).where(Categoria.clave == clave),
            ).first()
            if existente is not None:
                ids_categoria[clave] = existente.id or 0
                continue
            nueva = Categoria(nombre=normalizar_nombre_categoria(nombre), clave=clave)
            s.add(nueva)
            s.flush()
            assert nueva.id is not None
            ids_categoria[clave] = nueva.id

        # Devuelve el id de la categoria semilla por su clave normalizada.
        def _id_categoria(nombre_semilla: str) -> int:
            return ids_categoria[clave_normalizada(nombre_semilla)]

        productos = [
            Producto(
                nombre_producto="Arroz Blanco 1kg",
                categoria_id=_id_categoria("Alimentos"),
                precio_compra=Decimal("1.20"),
                precio_venta_bs=Decimal("1.80"),
                precio_venta_usd=Decimal("0.05"),
                stock_actual=Decimal("50"),
                stock_minimo=Decimal("10"),
                tipo_venta=TIPO_VENTA_UNIDAD,
                unidad="UNIDAD",
            ),
            Producto(
                nombre_producto="Azúcar 1kg",
                categoria_id=_id_categoria("Alimentos"),
                precio_compra=Decimal("0.90"),
                precio_venta_bs=Decimal("1.50"),
                precio_venta_usd=Decimal("0.04"),
                stock_actual=Decimal("40"),
                stock_minimo=Decimal("10"),
                tipo_venta=TIPO_VENTA_UNIDAD,
                unidad="UNIDAD",
            ),
            Producto(
                nombre_producto="Harina PAN 1kg",
                categoria_id=_id_categoria("Alimentos"),
                precio_compra=Decimal("2.00"),
                precio_venta_bs=Decimal("3.00"),
                precio_venta_usd=Decimal("0.09"),
                stock_actual=Decimal("30"),
                stock_minimo=Decimal("15"),
                tipo_venta=TIPO_VENTA_UNIDAD,
                unidad="UNIDAD",
            ),
            Producto(
                nombre_producto="Aceite Vegetal 1L",
                categoria_id=_id_categoria("Alimentos"),
                precio_compra=Decimal("3.50"),
                precio_venta_bs=Decimal("5.50"),
                precio_venta_usd=Decimal("0.15"),
                stock_actual=Decimal("20"),
                stock_minimo=Decimal("8"),
                tipo_venta=TIPO_VENTA_UNIDAD,
                unidad="UNIDAD",
            ),
            Producto(
                nombre_producto="Leche Completa 1L",
                categoria_id=_id_categoria("Lácteos"),
                precio_compra=Decimal("1.50"),
                precio_venta_bs=Decimal("2.50"),
                precio_venta_usd=Decimal("0.07"),
                stock_actual=Decimal("25"),
                stock_minimo=Decimal("10"),
                tipo_venta=TIPO_VENTA_UNIDAD,
                unidad="UNIDAD",
            ),
            Producto(
                nombre_producto="Queso Amarillo 500g",
                categoria_id=_id_categoria("Lácteos"),
                precio_compra=Decimal("3.00"),
                precio_venta_bs=Decimal("5.00"),
                precio_venta_usd=Decimal("0.14"),
                stock_actual=Decimal("15"),
                stock_minimo=Decimal("5"),
                tipo_venta=TIPO_VENTA_UNIDAD,
                unidad="UNIDAD",
            ),
            Producto(
                nombre_producto="Jabón de Baño",
                categoria_id=_id_categoria("Aseo Personal"),
                precio_compra=Decimal("0.80"),
                precio_venta_bs=Decimal("1.50"),
                precio_venta_usd=Decimal("0.04"),
                stock_actual=Decimal("60"),
                stock_minimo=Decimal("20"),
                tipo_venta=TIPO_VENTA_UNIDAD,
                unidad="UNIDAD",
            ),
            Producto(
                nombre_producto="Detergente 500g",
                categoria_id=_id_categoria("Limpieza"),
                precio_compra=Decimal("1.80"),
                precio_venta_bs=Decimal("3.00"),
                precio_venta_usd=Decimal("0.08"),
                stock_actual=Decimal("35"),
                stock_minimo=Decimal("10"),
                tipo_venta=TIPO_VENTA_UNIDAD,
                unidad="UNIDAD",
            ),
            Producto(
                nombre_producto="Café Molido 250g",
                categoria_id=_id_categoria("Alimentos"),
                precio_compra=Decimal("2.50"),
                precio_venta_bs=Decimal("4.00"),
                precio_venta_usd=Decimal("0.11"),
                stock_actual=Decimal("3"),
                stock_minimo=Decimal("10"),
                tipo_venta=TIPO_VENTA_UNIDAD,
                unidad="UNIDAD",
            ),
            Producto(
                nombre_producto="Papel Higiénico x4",
                categoria_id=_id_categoria("Limpieza"),
                precio_compra=Decimal("2.00"),
                precio_venta_bs=Decimal("3.50"),
                precio_venta_usd=Decimal("0.10"),
                stock_actual=Decimal("0"),
                stock_minimo=Decimal("10"),
                tipo_venta=TIPO_VENTA_UNIDAD,
                unidad="UNIDAD",
            ),
        ]
        for p in productos:
            s.add(p)
        s.commit()


# Crea una tasa de cambio de ejemplo si no existe ninguna.
def seed_tasa_cambio(session: Session | None = None) -> None:
    """Crea una tasa de cambio de ejemplo si no existe ninguna."""
    with obtener_sesion(session) as s:
        if s.exec(select(TasaCambio)).first() is not None:
            return

        tasa = TasaCambio(
            fecha=hoy(),
            tasa_venta=Decimal("36.50"),
            tasa_compra=Decimal("36.00"),
            activa=True,
        )
        s.add(tasa)
        s.commit()


# Ejecuta todos los seeds en orden.
def ejecutar_todos(session: Session | None = None) -> None:
    """Ejecuta todos los seeds en orden."""
    seed_productos(session)
    seed_tasa_cambio(session)
