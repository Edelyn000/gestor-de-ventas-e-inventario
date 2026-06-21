from datetime import datetime

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from ..models import MovimientoInventario, Producto, obtener_sesion


# ============================================================
# SERVICIO: InventarioService
# Control de inventario: registra movimientos de stock
# (entradas, salidas, ajustes) y actualiza el stock actual
# del producto. Cada movimiento crea un registro de
# auditoría con el stock anterior y nuevo (snapshot).
#
# Metodos:
#   registrar_entrada()    → Suma stock (compra, devolucion)
#   registrar_salida()     → Resta stock (venta, merma)
#   registrar_ajuste()     → Stock exacto (físico vs sistema)
#   historial_por_producto() → Movimientos de un producto
#   stock_disponible()     → Verifica si hay stock suficiente
#   movimientos_recientes()→ Últimos movimientos globales
# ============================================================
class InventarioService:
    def registrar_entrada(
        self,
        producto_id: int,
        cantidad: int,
        motivo: str,
        referencia_id: int | None = None,
        observaciones: str | None = None,
        db_session: Session | None = None,
    ) -> MovimientoInventario:
        """Registra una entrada de stock (compra, devolucion, etc.).
        Incrementa el stock_actual del producto y crea un movimiento de auditoria."""
        # Validar cantidad positiva.
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")

        # Abrir sesión y recuperar el producto.
        with obtener_sesion(db_session) as session:
            producto = session.get(Producto, producto_id)
            if not producto:
                raise ValueError("El producto no existe.")

            # Guardar el stock anterior.
            stock_anterior = producto.stock_actual

            # Actualizar el stock del producto.
            producto.stock_actual += cantidad

            # Crear el movimiento de auditoría.
            movimiento = MovimientoInventario(
                producto_id=producto_id,
                tipo="ENTRADA",
                motivo=motivo.upper(),
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_nuevo=producto.stock_actual,
                referencia_id=referencia_id,
                observaciones=observaciones,
                fecha_movimiento=datetime.now(),
            )

            # Guardar todo en la base de datos.
            session.add(producto)
            session.add(movimiento)
            session.commit()
            session.refresh(movimiento)

        return movimiento

    def registrar_salida(
        self,
        producto_id: int,
        cantidad: int,
        motivo: str,
        referencia_id: int | None = None,
        observaciones: str | None = None,
        db_session: Session | None = None,
    ) -> MovimientoInventario:
        """Registra una salida de stock (venta, merma, etc.).
        Decrementa el stock_actual del producto. Valida que haya stock suficiente."""
        # Validar cantidad positiva.
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")

        # Abrir sesión y recuperar el producto.
        with obtener_sesion(db_session) as session:
            producto = session.get(Producto, producto_id)
            if not producto:
                raise ValueError("El producto no existe.")

            # Validar stock suficiente.
            if producto.stock_actual < cantidad:
                raise ValueError(
                    f"Stock insuficiente. Disponible: {producto.stock_actual},"
                    f" solicitado: {cantidad}"
                )

            # Guardar el stock anterior.
            stock_anterior = producto.stock_actual

            # Actualizar el stock del producto.
            producto.stock_actual -= cantidad

            # Crear el movimiento de auditoría.
            movimiento = MovimientoInventario(
                producto_id=producto_id,
                tipo="SALIDA",
                motivo=motivo.upper(),
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_nuevo=producto.stock_actual,
                referencia_id=referencia_id,
                observaciones=observaciones,
                fecha_movimiento=datetime.now(),
            )

            # Guardar todo en la base de datos.
            session.add(producto)
            session.add(movimiento)
            session.commit()
            session.refresh(movimiento)

        return movimiento

    def registrar_ajuste(
        self,
        producto_id: int,
        stock_fisico: int,
        motivo: str = "AJUSTE",
        observaciones: str | None = None,
        db_session: Session | None = None,
    ) -> MovimientoInventario:
        """Ajusta el stock al valor fisico real (inventario fisico).
        Calcula automaticamente la diferencia y crea el movimiento."""
        if stock_fisico < 0:
            raise ValueError("El stock fisico no puede ser negativo.")

        with obtener_sesion(db_session) as session:
            producto = session.get(Producto, producto_id)
            if not producto:
                raise ValueError("El producto no existe.")

            stock_anterior = producto.stock_actual
            diferencia = stock_fisico - stock_anterior

            if diferencia == 0:
                raise ValueError("El stock fisico es igual al actual. No hay nada que ajustar.")

            producto.stock_actual = stock_fisico

            movimiento = MovimientoInventario(
                producto_id=producto_id,
                tipo="AJUSTE",
                motivo=motivo.upper(),
                cantidad=abs(diferencia),
                stock_anterior=stock_anterior,
                stock_nuevo=producto.stock_actual,
                observaciones=observaciones,
                fecha_movimiento=datetime.now(),
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
        cantidad: int,
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
