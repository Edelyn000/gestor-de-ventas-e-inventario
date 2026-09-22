# ============================================================
# IMPORTACIONES
# ============================================================
# datetime: la necesitamos para poner la fecha/hora actual en cada venta.
# Decimal: los precios y totales usan este tipo para evitar errores
#   de redondeo que darian float (ej: 0.1 + 0.2 = 0.30000000000000004).
# select: funcion de SQLModel para construir consultas SELECT.
#   Sin ella no podriamos buscar ventas en la BD.
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, col, select

from sistema_financiero.utils import (
    DECIMAL_CENTIMO,
    METODO_PAGO_EFECTIVO_USD,
    METODOS_PAGO,
    MONEDA_BS,
    MONEDA_USD,
    TOLERANCIA_REDONDEO,
    ahora,
)

# Venta y VentaDetalle son los modelos ORM que representan las tablas.
# Venta = la cabecera de la venta (fecha, totales, metodo de pago).
# VentaDetalle = cada producto que se vendio (cantidad, precio, subtotal).
# PagoVenta = desglose de cada pago (multi-pago) de la venta.
# obtener_sesion: context manager que acepta sesion opcional (BD en memoria para tests).
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

# CajaService: fuente unica de verdad del estado de caja.
#   La venta solo se registra si hay una caja ABIERTA (ver crear()).
from .caja_service import CajaService

# InventarioService: lo necesitamos para descontar el stock
#   de cada producto cuando se confirma la venta.
from .inventario_service import InventarioService

# ProductoController: lo necesitamos para obtener los precios
#   de los productos al momento de crear la venta.
from .producto_controller import ProductoController

# TasaCambioService: necesario para obtener la tasa de cambio
#   activa y poder calcular el total en USD.
from .tasa_cambio_service import TasaCambioService


def _a_centimos(valor: Decimal) -> Decimal:
    """Cuantiza un monto a centimos (redondeo comercial).

    La UI entrega numeros como float y los calculos pueden arrastrar
    fracciones de centimo; en dinero solo existen 2 decimales.
    """
    return valor.quantize(DECIMAL_CENTIMO, rounding=ROUND_HALF_UP)


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
    def __init__(self, caja_service: CajaService | None = None) -> None:
        # InventarioService: lo usaremos para descontar stock al vender
        #   y para devolver stock al anular una venta.
        self.inventario = InventarioService()

        # TasaCambioService: lo usaremos para obtener la tasa del dia
        #   y calcular el equivalente en USD de la venta.
        self.tasas = TasaCambioService()

        # CajaService: fuente unica de verdad del estado de caja.
        # La app lo inyecta (ui/interfaz.py) para que la venta valide
        # contra la MISMA instancia que usa la pagina "Caja".
        # Si es None (tests), crear() valida la caja dentro de la
        # sesion que recibe como db_session.
        self.caja_service = caja_service

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

        # Desglose multi-pago (opcional). Si llega, el detalle manda:
        # los montos por metodo se derivan de el, para que el resumen de
        # la venta y el desglose no puedan quedar descuadrados.
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
            # Regla de negocio: sin caja ABIERTA no se puede vender.
            if self.caja_service is not None and db_session is None:
                # App: valida contra la misma instancia compartida con la
                # pagina "Caja" (una sola fuente de verdad del estado).
                caja = self.caja_service.validar_caja_abierta()
            else:
                # Tests/llamadas con sesion propia: la caja se consulta
                # dentro de la misma sesion que recibe el metodo.
                caja = session.exec(select(Caja).where(Caja.estado == "ABIERTA")).first()
                if caja is None:
                    msg = "No hay caja abierta. Abra la caja antes de registrar ventas."
                    raise ValueError(msg)
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
        # El equivalente en Bs. del efectivo USD tambien se cuantiza:
        # el cajero teclea el USD redondeado a centimos que le muestra la UI.
        efectivo_usd_en_bs = (
            _a_centimos(efectivo_usd * tasa.tasa_venta) if tasa else Decimal("0.00")
        )
        suma_pagos = (
            efectivo_bs + efectivo_usd_en_bs + tarjeta + pago_movil + bio_pago + transferencia
        )
        # Se acepta una diferencia de 1 centimo por redondeo (ver
        # TOLERANCIA_REDONDEO); un faltante real sigue siendo un error.
        if suma_pagos < total_bs - TOLERANCIA_REDONDEO:
            msg = (
                f"La suma de los metodos de pago ({suma_pagos}) "
                f"no cubre el total de la venta ({total_bs})."
            )
            raise ValueError(msg)

        return efectivo_bs, efectivo_usd, tarjeta, pago_movil, bio_pago, transferencia

    @staticmethod
    def _normalizar_pagos(
        pagos: list[dict[str, object]] | None,
        total_bs: Decimal,
        tasa: TasaCambio | None,
    ) -> list[dict[str, object]] | None:
        """Valida y normaliza el desglose multi-pago de una venta.

        Cada pago llega como {"metodo", "monto", "referencia"}. Se registra
        SOLO el monto aplicado, asi que la suma en Bs. de todos los pagos
        debe cuadrar con el total de la venta (regla de negocio).
        Devuelve None cuando el llamador no usa multi-pago.
        """
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
                # El llamador puede mandar el monto APLICADO en bolivares
                # (la UI recorta un pago en USD al faltante exacto y el
                # sobrante es vuelto). Si no lo manda, se convierte aqui.
                aplicado = pago.get("monto_bs")
                monto_bs = (
                    _a_centimos(monto * tasa.tasa_venta)
                    if aplicado is None
                    else _a_centimos(Decimal(str(aplicado)))
                )
                # Guarda de integridad: el monto aplicado no puede alejarse
                # del equivalente del monto recibido por mas de un centimo
                # de la moneda pagada (un centavo USD = tasa / 100 Bs.).
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
                monto_bs = monto

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

    @staticmethod
    def _derivar_metodo_pago(
        pagos: list[dict[str, object]],
        metodo_pago: dict[str, object] | None,
    ) -> dict[str, object]:
        """Resume el desglose de pagos en los montos por metodo de Venta.

        Para efectivo_usd se resumen los USD (asi los guarda el modelo y
        los lee el arqueo de caja); el resto se resume en bolivares.
        Si ademas llega un resumen metodo_pago y no coincide, se rechaza
        la venta: nunca se guarda un resumen distinto al desglose.
        """
        acumulado: dict[str, Decimal] = dict.fromkeys(METODOS_PAGO, Decimal("0.00"))

        for pago in pagos:
            metodo = str(pago["metodo"])
            valor = pago["monto"] if metodo == METODO_PAGO_EFECTIVO_USD else pago["monto_bs"]
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

        # dict[str, object] explicito: evita el choque de invarianza de dict
        # al pasarlo a _procesar_pago(metodo_pago: dict[str, object] | None).
        derivado: dict[str, object] = {}
        for nombre, monto in acumulado.items():
            derivado[nombre] = monto
        return derivado

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

            # No se puede anular una venta de un turno de caja ya cerrado:
            # el arqueo y el reporte del dia ya se generaron con esa venta.
            if venta.caja_id is not None:
                caja = session.get(Caja, venta.caja_id)
                if caja is not None and caja.estado == "CERRADA":
                    msg = "No se puede anular: el turno de caja de esta venta ya esta cerrado."
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

    # ------------------------------------------------------------------
    # obtener_pagos(): devuelve el desglose de pagos de una venta
    # ------------------------------------------------------------------
    # Cada PagoVenta tiene: metodo, moneda, monto aplicado, su
    # equivalente en Bs. y la referencia (si la hubo).
    def obtener_pagos(
        self,
        idventa: int,
        db_session: Session | None = None,
    ) -> list[PagoVenta]:
        """Devuelve el desglose de pagos (multi-pago) de una venta.
        db_session: sesion opcional para tests con BD en memoria."""
        with obtener_sesion(db_session) as session:
            stmt = select(PagoVenta).where(PagoVenta.venta_id == idventa)
            return list(session.exec(stmt).all())
