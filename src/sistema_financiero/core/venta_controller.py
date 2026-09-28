from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, col, select

from sistema_financiero.utils import (
    DECIMAL_CENTIMO,
    METODO_PAGO_EFECTIVO_BS,
    METODO_PAGO_EFECTIVO_USD,
    METODOS_PAGO,
    MONEDA_BS,
    MONEDA_USD,
    MOTIVO_DEVOLUCION_ANULACION,
    TOLERANCIA_REDONDEO,
    ahora,
    hoy,
)
from sistema_financiero.utils.fecha import rango_dia_utc

from ..models import (
    Caja,
    MovimientoInventario,
    PagoVenta,
    Producto,
    TasaCambio,
    Venta,
    VentaDetalle,
    obtener_sesion,
)
from .caja_service import CajaService
from .inventario_service import InventarioService
from .producto_controller import ProductoController
from .tasa_cambio_service import TasaCambioService


# Cuantiza un monto a centimos (redondeo comercial).
def _a_centimos(valor: Decimal) -> Decimal:
    """Cuantiza un monto a centimos (redondeo comercial)."""
    return valor.quantize(DECIMAL_CENTIMO, rounding=ROUND_HALF_UP)


# VentaController: Crear y anular ventas con facturacion y pagos.
class VentaController:
    # Conecta los servicios de inventario y tasas; la caja es opcional.
    def __init__(self, caja_service: CajaService | None = None) -> None:
        self.inventario = InventarioService()

        self.tasas = TasaCambioService()

        self.caja_service = caja_service

    # Registra la venta con sus detalles, pagos y descuento de inventario.
    def crear(
        self,
        productos: list[dict[str, object]],
        metodo_pago: dict[str, object] | None = None,
        db_session: Session | None = None,
        pagos: list[dict[str, object]] | None = None,
    ) -> Venta:
        self._validar_productos_no_vacios(productos)
        tasa = self.tasas.tasa_activa(db_session)
        detalles_lista, total_bs = self._procesar_detalles(productos, db_session)
        total_usd = self._calcular_total_usd(total_bs, tasa)

        pagos_normalizados = self._normalizar_pagos(pagos, total_bs, tasa)
        if pagos_normalizados is not None:
            metodo_pago = self._derivar_metodo_pago(pagos_normalizados, metodo_pago)

        (
            efectivo_bs,
            efectivo_usd,
            tarjeta,
            pago_movil,
            bio_pago,
            transferencia,
        ) = self._procesar_pago(metodo_pago, total_bs, tasa)
        numero_factura = self._generar_numero_factura(db_session)

        with obtener_sesion(db_session) as session:
            hoy = ahora()
            if self.caja_service is not None and db_session is None:
                caja = self.caja_service.validar_caja_abierta()
            else:
                caja_en_sesion = session.exec(select(Caja).where(Caja.estado == "ABIERTA")).first()
                if caja_en_sesion is None:
                    msg = "No hay caja abierta. Abra la caja antes de registrar ventas."
                    raise ValueError(msg)
                caja = caja_en_sesion
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
                transferencia=transferencia,
                estado="COMPLETADA",
                caja_id=caja.id,
            )
            session.add(venta)
            session.flush()

            venta_id = venta.idventa
            if venta_id is None:
                msg = "No se pudo generar el ID de la venta"
                raise RuntimeError(msg)

            self._crear_detalles(session, venta_id, detalles_lista)
            if pagos_normalizados:
                self._crear_pagos(session, venta_id, pagos_normalizados, tasa)
            self._descontar_inventario(session, detalles_lista, venta_id, numero_factura)

            session.commit()
            session.refresh(venta)

        return venta

    # Rechaza la venta si la lista de productos esta vacia.
    @staticmethod
    def _validar_productos_no_vacios(
        productos: list[dict[str, object]],
    ) -> None:
        if not productos:
            msg = "La venta debe tener al menos un producto."
            raise ValueError(msg)

    # Construye los detalles y el total en Bs desde los items del carrito.
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

            precio_bs_dado = item.get("precio_bs")
            subtotal_bs_dado = item.get("subtotal_bs")
            if precio_bs_dado is not None:
                precio_unitario = Decimal(str(precio_bs_dado))
                subtotal = (
                    Decimal(str(subtotal_bs_dado))
                    if subtotal_bs_dado is not None
                    else precio_unitario * cantidad
                )
            else:
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

    # Convierte el total en Bs a USD con la tasa activa.
    @staticmethod
    def _calcular_total_usd(
        total_bs: Decimal,
        tasa: TasaCambio | None,
    ) -> Decimal:
        if tasa and tasa.tasa_venta > 0:
            return (total_bs / tasa.tasa_venta).quantize(Decimal("0.01"))
        return Decimal("0.00")

    # Distribuye el pago en los seis campos de metodo y devuelve el desglose.
    @staticmethod
    def _procesar_pago(
        metodo_pago: dict[str, object] | None,
        total_bs: Decimal,
        tasa: TasaCambio | None,
    ) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
        if metodo_pago is None:
            metodo_pago = {}

        efectivo_bs = _a_centimos(Decimal(str(metodo_pago.get("efectivo_bs", total_bs))))
        efectivo_usd = _a_centimos(Decimal(str(metodo_pago.get("efectivo_usd", "0.00"))))
        tarjeta = _a_centimos(Decimal(str(metodo_pago.get("tarjeta", "0.00"))))
        pago_movil = _a_centimos(Decimal(str(metodo_pago.get("pago_movil", "0.00"))))
        bio_pago = _a_centimos(Decimal(str(metodo_pago.get("bio_pago", "0.00"))))
        transferencia = _a_centimos(Decimal(str(metodo_pago.get("transferencia", "0.00"))))

        if efectivo_usd > 0 and tasa is None:
            msg = (
                "No hay una tasa de cambio activa registrada.\n"
                "Para cobrar en USD debe existir una tasa del dia.\n"
                "Vaya al Dashboard para que se cargue automaticamente."
            )
            raise ValueError(msg)
        efectivo_usd_en_bs = (
            _a_centimos(efectivo_usd * tasa.tasa_venta) if tasa else Decimal("0.00")
        )
        suma_pagos = (
            efectivo_bs + efectivo_usd_en_bs + tarjeta + pago_movil + bio_pago + transferencia
        )
        if suma_pagos < total_bs - TOLERANCIA_REDONDEO:
            msg = (
                f"La suma de los metodos de pago ({suma_pagos}) "
                f"no cubre el total de la venta ({total_bs})."
            )
            raise ValueError(msg)

        return efectivo_bs, efectivo_usd, tarjeta, pago_movil, bio_pago, transferencia

    # Valida y normaliza el desglose multi-pago de una venta.
    @staticmethod
    def _normalizar_pagos(
        pagos: list[dict[str, object]] | None,
        total_bs: Decimal,
        tasa: TasaCambio | None,
    ) -> list[dict[str, object]] | None:
        """Valida y normaliza el desglose multi-pago de una venta."""
        if pagos is None:
            return None
        if not pagos:
            msg = "La venta debe tener al menos un pago registrado."
            raise ValueError(msg)

        normalizados: list[dict[str, object]] = []
        suma_bs = Decimal("0.00")

        for pago in pagos:
            metodo = str(pago.get("metodo", ""))
            if metodo not in METODOS_PAGO:
                msg = f"Metodo de pago invalido: '{metodo}'."
                raise ValueError(msg)

            moneda = MONEDA_USD if metodo == METODO_PAGO_EFECTIVO_USD else MONEDA_BS
            monto = _a_centimos(Decimal(str(pago.get("monto", "0.00"))))
            if monto <= 0:
                msg = f"El monto del pago con metodo '{metodo}' debe ser mayor a cero."
                raise ValueError(msg)

            if moneda == MONEDA_USD:
                if tasa is None or tasa.tasa_venta <= 0:
                    msg = (
                        "No hay una tasa de cambio activa registrada.\n"
                        "Para cobrar en USD debe existir una tasa del dia.\n"
                        "Vaya al Dashboard para que se cargue automaticamente."
                    )
                    raise ValueError(msg)
                aplicado = pago.get("monto_bs")
                monto_bs = (
                    _a_centimos(monto * tasa.tasa_venta)
                    if aplicado is None
                    else _a_centimos(Decimal(str(aplicado)))
                )
                desvio_maximo = _a_centimos(tasa.tasa_venta / Decimal("100")) + TOLERANCIA_REDONDEO
                if monto_bs <= 0 or abs(monto_bs - monto * tasa.tasa_venta) > desvio_maximo:
                    msg = (
                        "El monto en bolivares del pago en USD no coincide con "
                        f"su equivalente (recibido {monto} USD = "
                        f"{_a_centimos(monto * tasa.tasa_venta)} Bs., "
                        f"aplicado {monto_bs} Bs.)."
                    )
                    raise ValueError(msg)
            else:
                aplicado_bs = pago.get("monto_bs")
                monto_bs = (
                    _a_centimos(Decimal(str(aplicado_bs))) if aplicado_bs is not None else monto
                )
                if monto_bs <= 0 or monto_bs > monto + TOLERANCIA_REDONDEO:
                    msg = (
                        "El monto en bolivares del pago no coincide con su "
                        f"equivalente (recibido {monto} Bs., aplicado "
                        f"{monto_bs} Bs.)."
                    )
                    raise ValueError(msg)

            referencia = pago.get("referencia")
            normalizados.append(
                {
                    "metodo": metodo,
                    "moneda": moneda,
                    "monto": monto,
                    "monto_bs": monto_bs,
                    "referencia": str(referencia) if referencia else None,
                },
            )
            suma_bs += monto_bs

        if abs(suma_bs - total_bs) > TOLERANCIA_REDONDEO:
            msg = (
                f"La suma de los pagos ({suma_bs}) no coincide con el "
                f"total de la venta ({total_bs})."
            )
            raise ValueError(msg)

        return normalizados

    # Resume el desglose de pagos en los montos por metodo de Venta.
    @staticmethod
    def _derivar_metodo_pago(
        pagos: list[dict[str, object]],
        metodo_pago: dict[str, object] | None,
    ) -> dict[str, object]:
        """Resume el desglose de pagos en los montos por metodo de Venta."""
        acumulado: dict[str, Decimal] = dict.fromkeys(METODOS_PAGO, Decimal("0.00"))

        for pago in pagos:
            metodo = str(pago["metodo"])
            valor = (
                pago["monto"]
                if metodo in (METODO_PAGO_EFECTIVO_BS, METODO_PAGO_EFECTIVO_USD)
                else pago["monto_bs"]
            )
            acumulado[metodo] += Decimal(str(valor))

        if metodo_pago:
            for nombre, esperado in acumulado.items():
                recibido = _a_centimos(Decimal(str(metodo_pago.get(nombre, "0.00"))))
                if abs(recibido - esperado) > TOLERANCIA_REDONDEO:
                    msg = (
                        "El resumen por metodo de pago no coincide con el "
                        f"detalle de pagos ('{nombre}': {recibido} vs {esperado})."
                    )
                    raise ValueError(msg)

        derivado: dict[str, object] = {}
        for nombre, monto in acumulado.items():
            derivado[nombre] = monto
        return derivado

    # Guarda el desglose de pagos (tabla venta_pago) de una venta.
    @staticmethod
    def _crear_pagos(
        session: Session,
        venta_id: int,
        pagos: list[dict[str, object]],
        tasa: TasaCambio | None,
    ) -> None:
        """Guarda el desglose de pagos (tabla venta_pago) de una venta."""
        for pago in pagos:
            referencia = pago.get("referencia")
            session.add(
                PagoVenta(
                    venta_id=venta_id,
                    metodo=str(pago["metodo"]),
                    moneda=str(pago["moneda"]),
                    monto=Decimal(str(pago["monto"])),
                    monto_bs=Decimal(str(pago["monto_bs"])),
                    tasa_cambio=tasa.tasa_venta if tasa else None,
                    referencia=str(referencia) if referencia else None,
                    fecha_pago=ahora(),
                ),
            )

    # Genera el numero de factura del dia local segun el conteo de hoy.
    @staticmethod
    def _generar_numero_factura(
        db_session: Session | None = None,
    ) -> str:
        fecha_local = hoy()
        fecha_str = fecha_local.strftime("%Y%m%d")
        desde_hoy, hasta_hoy = rango_dia_utc(fecha_local)

        with obtener_sesion(db_session) as session:
            ventas_hoy = session.exec(
                select(Venta).where(
                    Venta.fecha_venta >= desde_hoy,
                    Venta.fecha_venta <= hasta_hoy,
                ),
            ).all()
            correlativo = str(len(ventas_hoy) + 1).zfill(3)

        return f"FAC-{fecha_str}-{correlativo}"

    # Persiste los VentaDetalle de la venta recien creada.
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

    # Descarta el stock vendido y registra el movimiento de salida.
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

    # Anula una venta y devuelve el stock de cada producto.
    def anular(
        self,
        idventa: int,
        motivo_anulacion: str | None = None,
        anulado_por: str | None = None,
        db_session: Session | None = None,
    ) -> Venta | None:
        """Anula una venta y devuelve el stock de cada producto."""
        with obtener_sesion(db_session) as session:
            venta = session.get(Venta, idventa)
            if not venta:
                return None

            if venta.estado == "ANULADA":
                msg = "La venta ya esta anulada."
                raise ValueError(msg)

            if venta.caja_id is not None:
                caja = session.get(Caja, venta.caja_id)
                if caja is not None and caja.estado == "CERRADA":
                    msg = "No se puede anular: el turno de caja de esta venta ya esta cerrado."
                    raise ValueError(msg)

            venta.estado = "ANULADA"
            venta.motivo_anulacion = motivo_anulacion
            venta.anulado_por = anulado_por
            session.add(venta)
            session.commit()
            session.refresh(venta)

        with obtener_sesion(db_session) as session:
            detalles = session.exec(
                select(VentaDetalle).where(VentaDetalle.venta_id == idventa),
            ).all()

        observaciones = f"Anulacion factura {venta.numero_factura}"
        if motivo_anulacion:
            observaciones += f" ({motivo_anulacion})"
        for det in detalles:
            self.inventario.registrar_entrada(
                producto_id=det.producto_id,
                cantidad=det.cantidad,
                motivo=MOTIVO_DEVOLUCION_ANULACION,
                referencia_id=idventa,
                observaciones=observaciones,
                db_session=db_session,
            )

        return venta

    # Busca una venta por su ID.
    def obtener_por_id(
        self,
        idventa: int,
        db_session: Session | None = None,
    ) -> Venta | None:
        """Busca una venta por su ID."""
        with obtener_sesion(db_session) as session:
            return session.get(Venta, idventa)

    # Busca una venta por su numero de factura.
    def buscar_por_factura(
        self,
        numero_factura: str,
        db_session: Session | None = None,
    ) -> Venta | None:
        """Busca una venta por su numero de factura."""
        with obtener_sesion(db_session) as session:
            return session.exec(
                select(Venta).where(col(Venta.numero_factura) == numero_factura)
            ).first()

    # Devuelve las ventas en un rango de fechas.
    def historial_por_fecha(
        self,
        desde: datetime,
        hasta: datetime,
        db_session: Session | None = None,
    ) -> list[Venta]:
        """Devuelve las ventas en un rango de fechas."""
        with obtener_sesion(db_session) as session:
            stmt = (
                select(Venta)
                .where(Venta.fecha_venta >= desde, Venta.fecha_venta <= hasta)
                .order_by(Venta.fecha_venta.desc())  # type: ignore[attr-defined]
            )
            return list(session.exec(stmt).all())

    # Devuelve los detalles (productos) de una venta.
    def obtener_detalles(
        self,
        idventa: int,
        db_session: Session | None = None,
    ) -> list[VentaDetalle]:
        """Devuelve los detalles (productos) de una venta."""
        with obtener_sesion(db_session) as session:
            stmt = select(VentaDetalle).where(VentaDetalle.venta_id == idventa)
            return list(session.exec(stmt).all())

    # Devuelve el desglose de pagos (multi-pago) de una venta.
    def obtener_pagos(
        self,
        idventa: int,
        db_session: Session | None = None,
    ) -> list[PagoVenta]:
        """Devuelve el desglose de pagos (multi-pago) de una venta."""
        with obtener_sesion(db_session) as session:
            stmt = select(PagoVenta).where(PagoVenta.venta_id == idventa)
            return list(session.exec(stmt).all())

