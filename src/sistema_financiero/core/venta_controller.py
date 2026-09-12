# ============================================================
# IMPORTACIONES
# ============================================================
# datetime: la necesitamos para poner la fecha/hora actual en cada venta.
# Decimal: los precios y totales usan este tipo para evitar errores
#   de redondeo que darian float (ej: 0.1 + 0.2 = 0.30000000000000004).
# select: funcion de SQLModel para construir consultas SELECT.
#   Sin ella no podriamos buscar ventas en la BD.
from datetime import datetime
from decimal import Decimal

from sqlmodel import Session, col, select

from sistema_financiero.utils import ahora

# Venta y VentaDetalle son los modelos ORM que representan las tablas.
# Venta = la cabecera de la venta (fecha, totales, metodo de pago).
# VentaDetalle = cada producto que se vendio (cantidad, precio, subtotal).
# obtener_sesion: context manager que acepta sesion opcional (BD en memoria para tests).
from ..models import (
    MovimientoInventario,
    Producto,
    TasaCambio,
    Venta,
    VentaDetalle,
    obtener_sesion,
)

# InventarioService: lo necesitamos para descontar el stock
#   de cada producto cuando se confirma la venta.
from .inventario_service import InventarioService

# ProductoController: lo necesitamos para obtener los precios
#   de los productos al momento de crear la venta.
from .producto_controller import ProductoController

# TasaCambioService: necesario para obtener la tasa de cambio
#   activa y poder calcular el total en USD.
from .tasa_cambio_service import TasaCambioService


# ============================================================
# CONTROLADOR: VentaController
# ============================================================
# Este controlador maneja todo el flujo de una venta:
#   1. Crear la venta con sus productos (detalles)
#   2. Validar que haya stock suficiente
#   3. Calcular totales en VES y USD
#   4. Descontar del inventario
#   5. Consultar historial de ventas
#   6. Anular ventas (devolver el stock)
#
# Por que un controlador y no un servicio?
#   - Porque orquesta varios servicios (inventario + tasas).
#   - Un controlador COORDINA, un servicio EJECUTA una tarea especifica.
# ============================================================
class VentaController:
    # ------------------------------------------------------------------
    # __init__: constructor de la clase
    # ------------------------------------------------------------------
    # Aqui creamos las instancias de los servicios que vamos a usar.
    # Podriamos crearlas dentro de cada metodo, pero si las guardamos
    # en self.* se crean UNA SOLA VEZ cuando se crea el controlador,
    # en lugar de crearse cada vez que llamamos a un metodo.
    # Esto ahorra memoria y es mas limpio.
    def __init__(self) -> None:
        # InventarioService: lo usaremos para descontar stock al vender
        #   y para devolver stock al anular una venta.
        self.inventario = InventarioService()

        # TasaCambioService: lo usaremos para obtener la tasa del dia
        #   y calcular el equivalente en USD de la venta.
        self.tasas = TasaCambioService()

    def crear(
        self,
        productos: list[dict[str, object]],
        metodo_pago: dict[str, object] | None = None,
        db_session: Session | None = None,
    ) -> Venta:
        self._validar_productos_no_vacios(productos)
        tasa = self.tasas.tasa_activa(db_session)
        detalles_lista, total_bs = self._procesar_detalles(productos, db_session)
        total_usd = self._calcular_total_usd(total_bs, tasa)
        efectivo_bs, efectivo_usd, tarjeta, pago_movil, bio_pago = self._procesar_pago(
            metodo_pago, total_bs, tasa
        )
        numero_factura = self._generar_numero_factura(db_session)

        with obtener_sesion(db_session) as session:
            hoy = ahora()
            venta = Venta(
                numero_factura=numero_factura,
                fecha_venta=hoy,
                total_bs=total_bs,
                total_usd=total_usd,
                tasa_cambio=tasa.tasa_venta if tasa else None,
                efectivo_bs=efectivo_bs,
                efectivo_usd=efectivo_usd,
                tarjeta=tarjeta,
                pago_movil=pago_movil,
                bio_pago=bio_pago,
                estado="COMPLETADA",
            )
            session.add(venta)
            session.flush()

            venta_id = venta.idventa
            if venta_id is None:
                msg = "No se pudo generar el ID de la venta"
                raise RuntimeError(msg)

            self._crear_detalles(session, venta_id, detalles_lista)
            self._descontar_inventario(session, detalles_lista, venta_id, numero_factura)

            session.commit()
            session.refresh(venta)

        return venta

    @staticmethod
    def _validar_productos_no_vacios(
        productos: list[dict[str, object]],
    ) -> None:
        if not productos:
            msg = "La venta debe tener al menos un producto."
            raise ValueError(msg)

    def _procesar_detalles(
        self,
        productos: list[dict[str, object]],
        db_session: Session | None = None,
    ) -> tuple[list[dict[str, object]], Decimal]:
        total_bs = Decimal("0.00")
        detalles_lista: list[dict[str, object]] = []

        for item in productos:
            producto_id = int(str(item.get("idproducto", 0)))
            cantidad = Decimal(str(item.get("cantidad", 1)))

            if cantidad <= 0:
                msg = f"La cantidad del producto ID {producto_id} debe ser mayor a cero."
                raise ValueError(msg)

            if not self.inventario.stock_disponible(producto_id, cantidad, db_session):
                msg = f"Stock insuficiente para el producto ID {producto_id}. Solicito: {cantidad}"
                raise ValueError(msg)

            pc = ProductoController()
            producto = pc.obtener_por_id(producto_id, db_session)
            if not producto:
                msg = f"El producto ID {producto_id} no existe."
                raise ValueError(msg)

            precio_unitario = producto.precio_venta_bs
            subtotal = precio_unitario * Decimal(str(cantidad))

            detalles_lista.append(
                {
                    "producto_id": producto_id,
                    "cantidad": cantidad,
                    "precio_unitario_bs": precio_unitario,
                    "subtotal_bs": subtotal,
                }
            )
            total_bs += subtotal

        return detalles_lista, total_bs

    @staticmethod
    def _calcular_total_usd(
        total_bs: Decimal,
        tasa: TasaCambio | None,
    ) -> Decimal:
        if tasa and tasa.tasa_venta > 0:
            return (total_bs / tasa.tasa_venta).quantize(Decimal("0.01"))
        return Decimal("0.00")

    @staticmethod
    def _procesar_pago(
        metodo_pago: dict[str, object] | None,
        total_bs: Decimal,
        tasa: TasaCambio | None,
    ) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
        if metodo_pago is None:
            metodo_pago = {}

        efectivo_bs = Decimal(str(metodo_pago.get("efectivo_bs", total_bs)))
        efectivo_usd = Decimal(str(metodo_pago.get("efectivo_usd", "0.00")))
        tarjeta = Decimal(str(metodo_pago.get("tarjeta", "0.00")))
        pago_movil = Decimal(str(metodo_pago.get("pago_movil", "0.00")))
        bio_pago = Decimal(str(metodo_pago.get("bio_pago", "0.00")))

        if efectivo_usd > 0 and tasa is None:
            msg = (
                "No hay una tasa de cambio activa registrada.\n"
                "Para cobrar en USD debe existir una tasa del dia.\n"
                "Vaya al Dashboard para que se cargue automaticamente."
            )
            raise ValueError(msg)
        efectivo_usd_en_bs = efectivo_usd * tasa.tasa_venta if tasa else Decimal("0.00")
        suma_pagos = efectivo_bs + efectivo_usd_en_bs + tarjeta + pago_movil + bio_pago
        if suma_pagos < total_bs:
            msg = (
                f"La suma de los metodos de pago ({suma_pagos}) "
                f"no cubre el total de la venta ({total_bs})."
            )
            raise ValueError(msg)

        return efectivo_bs, efectivo_usd, tarjeta, pago_movil, bio_pago

    @staticmethod
    def _generar_numero_factura(
        db_session: Session | None = None,
    ) -> str:
        hoy = ahora()
        fecha_str = hoy.strftime("%Y%m%d")

        with obtener_sesion(db_session) as session:
            ventas_hoy = session.exec(
                select(Venta).where(
                    Venta.fecha_venta >= datetime(hoy.year, hoy.month, hoy.day),
                    Venta.fecha_venta < datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59),
                ),
            ).all()
            correlativo = str(len(ventas_hoy) + 1).zfill(3)

        return f"FAC-{fecha_str}-{correlativo}"

    @staticmethod
    def _crear_detalles(
        session: Session,
        venta_id: int,
        detalles_lista: list[dict[str, object]],
    ) -> None:
        for det in detalles_lista:
            detalle = VentaDetalle(
                venta_id=venta_id,
                producto_id=int(str(det["producto_id"])),
                cantidad=Decimal(str(det["cantidad"])),
                precio_unitario_bs=Decimal(str(det["precio_unitario_bs"])),
                subtotal_bs=Decimal(str(det["subtotal_bs"])),
            )
            session.add(detalle)

    @staticmethod
    def _descontar_inventario(
        session: Session,
        detalles_lista: list[dict[str, object]],
        venta_id: int,
        numero_factura: str,
    ) -> None:
        for det in detalles_lista:
            producto = session.get(Producto, int(str(det["producto_id"])))
            if not producto:
                msg = f"Producto ID {det['producto_id']} no existe."
                raise ValueError(msg)
            cantidad_det = Decimal(str(det["cantidad"]))
            if producto.stock_actual < cantidad_det:
                msg = (
                    f"Stock insuficiente para {producto.nombre_producto}. "
                    f"Disponible: {producto.stock_actual}, solicitado: {cantidad_det}"
                )
                raise ValueError(msg)
            stock_anterior = producto.stock_actual
            producto.stock_actual -= cantidad_det
            session.add(producto)

            movimiento = MovimientoInventario(
                producto_id=int(str(det["producto_id"])),
                tipo="SALIDA",
                motivo="VENTA",
                cantidad=cantidad_det,
                stock_anterior=stock_anterior,
                stock_nuevo=producto.stock_actual,
                referencia_id=venta_id,
                observaciones=f"Factura {numero_factura}",
                fecha_movimiento=ahora(),
            )
            session.add(movimiento)

    # ------------------------------------------------------------------
    # anular(): marca una venta como ANULADA y devuelve el stock
    # ------------------------------------------------------------------
    # Cuando se anula una venta:
    #   1. Cambiamos el estado a "ANULADA"
    #   2. Devolvemos el stock de cada producto (entrada de inventario)
    #   3. Guardamos el cambio en la BD
    #
    # Por que devolver el stock?
    #   - Porque si no lo hacemos, el inventario queda inconsistente.
    #   - Los productos que se "vendieron" pero se devolvieron deben
    #     volver a estar disponibles.
    # ------------------------------------------------------------------
    def anular(
        self,
        idventa: int,
        db_session: Session | None = None,
    ) -> Venta | None:
        """Anula una venta y devuelve el stock de cada producto.
        db_session: sesion opcional para tests con BD en memoria."""
        with obtener_sesion(db_session) as session:
            # Buscar la venta por ID.
            venta = session.get(Venta, idventa)
            if not venta:
                return None

            # No se puede anular una venta ya anulada.
            if venta.estado == "ANULADA":
                msg = "La venta ya esta anulada."
                raise ValueError(msg)

            # Cambiar el estado.
            venta.estado = "ANULADA"
            session.add(venta)
            session.commit()
            session.refresh(venta)

        # Devolver el stock de cada producto.
        # Necesitamos los detalles de la venta. Como ya cerramos la
        # sesion anterior, abrimos una nueva para consultar los detalles.
        with obtener_sesion(db_session) as session:
            detalles = session.exec(
                select(VentaDetalle).where(VentaDetalle.venta_id == idventa),
            ).all()

        # ADVERTENCIA: venta está DETACHED (obtenida en la sesión anterior).
        # venta.numero_factura es columna directa (segura). NO accedas a
        # venta.detalles aquí (relación lazy) sin selectinload().
        for det in detalles:
            self.inventario.registrar_entrada(
                producto_id=det.producto_id,
                cantidad=det.cantidad,
                motivo="DEVOLUCION",
                referencia_id=idventa,
                observaciones=f"Anulacion factura {venta.numero_factura}",
                db_session=db_session,
            )

        return venta

    # ------------------------------------------------------------------
    # obtener_por_id(): busca una venta por su ID
    # ------------------------------------------------------------------
    def obtener_por_id(
        self,
        idventa: int,
        db_session: Session | None = None,
    ) -> Venta | None:
        """Busca una venta por su ID.
        db_session: sesion opcional para tests con BD en memoria."""
        with obtener_sesion(db_session) as session:
            return session.get(Venta, idventa)

    # ------------------------------------------------------------------
    # buscar_por_factura(): busca una venta por su numero de factura
    # ------------------------------------------------------------------
    # El numero de factura es unico (unique=True en el modelo).
    # Por eso usamos .first() porque solo puede haber una.
    def buscar_por_factura(
        self,
        numero_factura: str,
        db_session: Session | None = None,
    ) -> Venta | None:
        """Busca una venta por su numero de factura.
        db_session: sesion opcional para tests con BD en memoria."""
        with obtener_sesion(db_session) as session:
            return session.exec(
                select(Venta).where(col(Venta.numero_factura) == numero_factura)
            ).first()

    # ------------------------------------------------------------------
    # historial_por_fecha(): ventas de un rango de fechas
    # ------------------------------------------------------------------
    # Parametros:
    #   - desde: fecha de inicio (incluida)
    #   - hasta: fecha de fin (incluida)
    # Retorna: lista de ventas ordenadas de la mas reciente a la mas antigua.
    #
    # Por que orden descendente?
    #   - Porque el usuario normalmente quiere ver las ventas mas recientes
    #     primero, igual que en un sistema de punto de venta real.
    # ------------------------------------------------------------------
    def historial_por_fecha(
        self,
        desde: datetime,
        hasta: datetime,
        db_session: Session | None = None,
    ) -> list[Venta]:
        """Devuelve las ventas en un rango de fechas.
        db_session: sesion opcional para tests con BD en memoria."""
        with obtener_sesion(db_session) as session:
            stmt = (
                select(Venta)
                .where(Venta.fecha_venta >= desde, Venta.fecha_venta <= hasta)
                .order_by(Venta.fecha_venta.desc())  # type: ignore[attr-defined]
            )
            return list(session.exec(stmt).all())

    # ------------------------------------------------------------------
    # obtener_detalles(): devuelve los productos de una venta
    # ------------------------------------------------------------------
    # Cada VentaDetalle tiene un producto_id, cantidad, precio y subtotal.
    # Esto se usa para mostrar el detalle de la venta en la UI.
    def obtener_detalles(
        self,
        idventa: int,
        db_session: Session | None = None,
    ) -> list[VentaDetalle]:
        """Devuelve los detalles (productos) de una venta.
        db_session: sesion opcional para tests con BD en memoria."""
        with obtener_sesion(db_session) as session:
            stmt = select(VentaDetalle).where(VentaDetalle.venta_id == idventa)
            return list(session.exec(stmt).all())
