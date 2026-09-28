from decimal import Decimal

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from sistema_financiero.utils import ahora

from ..models import MovimientoInventario, Producto, obtener_sesion


# InventarioService: Entrada, salida y ajuste de stock con auditoria.
class InventarioService:
    def registrar_entrada(
        self,
        producto_id: int,
        cantidad: Decimal,
        motivo: str,
        referencia_id: int | None = None,
        observaciones: str | None = None,
        db_session: Session | None = None,
    ) -> MovimientoInventario:
        """Registra una entrada de stock (compra, devolucion, etc.)."""
        if cantidad <= Decimal("0"):
            msg = "La cantidad debe ser mayor a cero."
            raise ValueError(msg)

        with obtener_sesion(db_session) as session:
            producto = session.get(Producto, producto_id)
            if not producto:
                msg = "El producto no existe."
                raise ValueError(msg)

            stock_anterior = producto.stock_actual

            producto.stock_actual += cantidad

            movimiento = MovimientoInventario(
                producto_id=producto_id,
                tipo="ENTRADA",
                motivo=motivo.upper(),
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_nuevo=producto.stock_actual,
                referencia_id=referencia_id,
                observaciones=observaciones,
                fecha_movimiento=ahora(),
            )

            session.add(producto)
            session.add(movimiento)
            session.commit()
            session.refresh(movimiento)

        return movimiento

    def registrar_salida(
        self,
        producto_id: int,
        cantidad: Decimal,
        motivo: str,
        referencia_id: int | None = None,
        observaciones: str | None = None,
        db_session: Session | None = None,
    ) -> MovimientoInventario:
        """Registra una salida de stock (venta, merma, etc.)."""
        if cantidad <= 0:
            msg = "La cantidad debe ser mayor a cero."
            raise ValueError(msg)

        with obtener_sesion(db_session) as session:
            producto = session.get(Producto, producto_id)
            if not producto:
                msg = "El producto no existe."
                raise ValueError(msg)

            if producto.stock_actual < cantidad:
                msg = (
                    f"Stock insuficiente. Disponible: {producto.stock_actual},"
                    f" solicitado: {cantidad}"
                )
                raise ValueError(msg)

            stock_anterior = producto.stock_actual

            producto.stock_actual -= cantidad

            movimiento = MovimientoInventario(
                producto_id=producto_id,
                tipo="SALIDA",
                motivo=motivo.upper(),
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_nuevo=producto.stock_actual,
                referencia_id=referencia_id,
                observaciones=observaciones,
                fecha_movimiento=ahora(),
            )

            session.add(producto)
            session.add(movimiento)
            session.commit()
            session.refresh(movimiento)

        return movimiento

    def registrar_ajuste(
        self,
        producto_id: int,
        stock_fisico: Decimal,
        motivo: str = "AJUSTE",
        observaciones: str | None = None,
        db_session: Session | None = None,
    ) -> MovimientoInventario:
        """Ajusta el stock al valor fisico real (inventario fisico)."""
        if stock_fisico < 0:
            msg = "El stock fisico no puede ser negativo."
            raise ValueError(msg)

        with obtener_sesion(db_session) as session:
            producto = session.get(Producto, producto_id)
            if not producto:
                msg = "El producto no existe."
                raise ValueError(msg)

            stock_anterior = producto.stock_actual
            diferencia = stock_fisico - stock_anterior

            if diferencia == 0:
                msg = "El stock fisico es igual al actual. No hay nada que ajustar."
                raise ValueError(msg)

            producto.stock_actual = stock_fisico

            movimiento = MovimientoInventario(
                producto_id=producto_id,
                tipo="AJUSTE",
                motivo=motivo.upper(),
                cantidad=abs(diferencia),
                stock_anterior=stock_anterior,
                stock_nuevo=producto.stock_actual,
                observaciones=observaciones,
                fecha_movimiento=ahora(),
            )

            session.add(producto)
            session.add(movimiento)
            session.commit()
            session.refresh(movimiento)

        return movimiento

    def historial_por_producto(
        self,
        producto_id: int,
        db_session: Session | None = None,
    ) -> list[MovimientoInventario]:
        """Movimientos de un producto del mas reciente al mas antiguo."""
        with obtener_sesion(db_session) as session:
            stmt = (
                select(MovimientoInventario)
                .options(selectinload(MovimientoInventario.producto))  # type: ignore[arg-type]
                .where(MovimientoInventario.producto_id == producto_id)
                .order_by(MovimientoInventario.fecha_movimiento.desc())  # type: ignore[union-attr]
            )
            return list(session.exec(stmt).all())

    def stock_disponible(
        self,
        producto_id: int,
        cantidad: Decimal,
        db_session: Session | None = None,
    ) -> bool:
        """Verifica si hay stock suficiente para una cantidad dada."""
        with obtener_sesion(db_session) as session:
            producto = session.get(Producto, producto_id)
            if not producto:
                return False
            return producto.stock_actual >= cantidad

    def movimientos_recientes(
        self,
        limite: int = 50,
        db_session: Session | None = None,
    ) -> list[MovimientoInventario]:
        """Devuelve los ultimos movimientos globales (todos los productos)."""
        with obtener_sesion(db_session) as session:
            stmt = (
                select(MovimientoInventario)
                .options(selectinload(MovimientoInventario.producto))  # type: ignore[arg-type]
                .order_by(MovimientoInventario.fecha_movimiento.desc())  # type: ignore[union-attr]
                .limit(limite)
            )
            return list(session.exec(stmt).all())

