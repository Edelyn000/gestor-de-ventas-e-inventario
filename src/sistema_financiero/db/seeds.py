
from decimal import Decimal

import bcrypt
from sqlmodel import Session, select

from sistema_financiero.utils import TIPO_VENTA_UNIDAD, hoy

from ..models import (
    Producto,
    TasaCambio,
    Usuario,
    obtener_sesion,
)


def seed_admin(session: Session | None = None) -> None:
    """Crea el usuario admin por defecto si no existe."""
    with obtener_sesion(session) as s:
        if s.exec(select(Usuario)).first() is None:
            admin = Usuario(
                usuario="admin",
                contrasena=bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode("utf-8"),
                nombre_completo="Administrador",
                rol="ADMINISTRADOR",
                activo=True,
            )
            s.add(admin)
            s.commit()


def seed_productos(session: Session | None = None) -> None:
    """Crea productos de ejemplo si no hay ninguno."""
    with obtener_sesion(session) as s:
        if s.exec(select(Producto)).first() is not None:
            return

        productos = [
            Producto(
                nombre_producto="Arroz Blanco 1kg",
                categoria="Alimentos",
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
                categoria="Alimentos",
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
                categoria="Alimentos",
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
                categoria="Alimentos",
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
                categoria="Lácteos",
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
                categoria="Lácteos",
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
                categoria="Aseo Personal",
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
                categoria="Limpieza",
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
                categoria="Alimentos",
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
                categoria="Limpieza",
                precio_compra=Decimal("2.00"),
                precio_venta_bs=Decimal("3.50"),
                precio_venta_usd=Decimal("0.10"),
                stock_actual=Decimal("0"),
                stock_minimo=Decimal("10"),
                tipo_venta=TIPO_VENTA_UNIDAD,
                unidad="PAQUETE",
            ),
        ]
        for p in productos:
            s.add(p)
        s.commit()


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


def ejecutar_todos(session: Session | None = None) -> None:
    """Ejecuta todos los seeds en orden."""
    seed_admin(session)
    seed_productos(session)
    seed_tasa_cambio(session)
