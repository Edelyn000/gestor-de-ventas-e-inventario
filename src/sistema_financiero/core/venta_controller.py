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

from sqlmodel import Session, select

# Venta y VentaDetalle son los modelos ORM que representan las tablas.
# Venta = la cabecera de la venta (fecha, totales, metodo de pago).
# VentaDetalle = cada producto que se vendio (cantidad, precio, subtotal).
# obtener_sesion: context manager que acepta sesion opcional (BD en memoria para tests).
from ..models import (
    MovimientoInventario,
    Producto,
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

    # ------------------------------------------------------------------
    # crear(): metodo principal para registrar una venta nueva
    # ------------------------------------------------------------------
    # Parametros:
    #   - productos: lista de diccionarios con {idproducto, cantidad}
    #     Ej: [{"idproducto": 1, "cantidad": 2}, {"idproducto": 3, "cantidad": 1}]
    #   - metodo_pago: dict con montos de cada forma de pago.
    #     Ej: {"efectivo_bs": 10.00, "tarjeta": 5.50}
    #
    # Por que usar un diccionario para metodo_pago?
    #   - Porque es mas flexible que tener 5 parametros separados.
    #   - La UI puede enviar solo los metodos que se usaron.
    #
    # Retorna: el objeto Venta recien creado (con su ID y numero de factura).
    # ------------------------------------------------------------------
    def crear(  # noqa: PLR0912, PLR0915
        self,
        productos: list[dict[str, object]],
        metodo_pago: dict[str, object] | None = None,
        db_session: Session | None = None,
    ) -> Venta:
        """
        Crea una venta con sus detalles, calcula totales,
        aplica la tasa de cambio y descuenta del inventario.
        db_session: sesion opcional para tests con BD en memoria.
        """
        # ----------------------------------------------------------
        # PASO 1: Validar que la venta tenga al menos un producto.
        # ----------------------------------------------------------
        # Si productos esta vacio, no tiene sentido crear la venta.
        # Lanzamos ValueError para que la UI pueda atraparlo y mostrar
        # un mensaje de error al usuario.
        if not productos:
            raise ValueError("La venta debe tener al menos un producto.")

        # ----------------------------------------------------------
        # PASO 2: Obtener la tasa de cambio activa del dia.
        # ----------------------------------------------------------
        # Necesitamos la tasa para calcular el total en USD.
        # Si no hay tasa activa, la venta no puede registrar USD.
        # En ese caso, el total_usd quedara en 0.00.
        tasa = self.tasas.tasa_activa(db_session)

        # ----------------------------------------------------------
        # PASO 3: Inicializar acumuladores.
        # ----------------------------------------------------------
        # total_bs: sumara el subtotal de cada producto en bolivares.
        # total_usd: se calcula al final dividiendo total_bs / tasa.
        # detalles_lista: aqui guardaremos los VentaDetalle temporales
        #   antes de guardarlos en la BD.
        total_bs = Decimal("0.00")
        detalles_lista: list[dict[str, object]] = []

        # ----------------------------------------------------------
        # PASO 4: Recorrer cada producto de la venta.
        # ----------------------------------------------------------
        # Por cada producto: validar stock, calcular subtotal,
        #   y guardar en la lista temporal.
        for item in productos:
            # Extraer datos del diccionario.
            # .get() evita KeyError si falta la clave (devuelve 0 por defecto).
            # Usamos int() para convertir de object a int (mypy strict).
            producto_id = int(str(item.get("idproducto", 0)))
            cantidad = int(str(item.get("cantidad", 1)))

            # Validar cantidad positiva.
            if cantidad <= 0:
                raise ValueError(
                    f"La cantidad del producto ID {producto_id} debe ser mayor a cero."
                )

            # ----------------------------------------------------------
            # PASO 4a: Validar stock suficiente antes de vender.
            # ----------------------------------------------------------
            # Usamos InventarioService.stock_disponible() que ya
            # implementamos antes. Si no hay stock, cancelamos toda
            # la venta (no solo ese producto).
            if not self.inventario.stock_disponible(producto_id, cantidad, db_session):
                raise ValueError(
                    f"Stock insuficiente para el producto ID {producto_id}. Solicito: {cantidad}"
                )

            # ----------------------------------------------------------
            # PASO 4b: Obtener el producto para conocer su precio.
            # ----------------------------------------------------------
            # Necesitamos el precio_venta_bs del producto para
            # calcular el subtotal. Usamos el controlador de productos.
            pc = ProductoController()
            producto = pc.obtener_por_id(producto_id, db_session)
            if not producto:
                raise ValueError(f"El producto ID {producto_id} no existe.")

            # ----------------------------------------------------------
            # PASO 4c: Calcular el subtotal del producto.
            # ----------------------------------------------------------
            # subtotal = precio_unitario * cantidad
            # Ej: si cuesta 2.50 y llevan 3, subtotal = 7.50
            # Usamos el precio_venta_bs del producto.
            precio_unitario = producto.precio_venta_bs
            subtotal = precio_unitario * Decimal(str(cantidad))

            # ----------------------------------------------------------
            # PASO 4d: Guardar en la lista temporal para procesar despues.
            # ----------------------------------------------------------
            # No creamos el VentaDetalle ORM aun porque no tenemos
            # el ID de la venta (se genera al guardar).
            detalles_lista.append(
                {
                    "producto_id": producto_id,
                    "cantidad": cantidad,
                    "precio_unitario_bs": precio_unitario,
                    "subtotal_bs": subtotal,
                }
            )

            # Acumular al total general.
            total_bs += subtotal

        # ----------------------------------------------------------
        # PASO 5: Calcular total en USD si hay tasa activa.
        # ----------------------------------------------------------
        # Si tasa existe y es > 0, convertimos total_bs a USD.
        # Si no, total_usd queda en 0.00.
        if tasa and tasa.tasa_venta > 0:
            total_usd = (total_bs / tasa.tasa_venta).quantize(Decimal("0.01"))
        else:
            total_usd = Decimal("0.00")

        # ----------------------------------------------------------
        # PASO 6: Preparar los montos de metodo de pago.
        # ----------------------------------------------------------
        # Si no se envio metodo_pago, asumimos que todo fue en efectivo_bs.
        if metodo_pago is None:
            metodo_pago = {}

        # Extraer cada metodo con .get() para evitar errores si falta.
        efectivo_bs = Decimal(str(metodo_pago.get("efectivo_bs", total_bs)))
        efectivo_usd = Decimal(str(metodo_pago.get("efectivo_usd", "0.00")))
        tarjeta = Decimal(str(metodo_pago.get("tarjeta", "0.00")))
        pago_movil = Decimal(str(metodo_pago.get("pago_movil", "0.00")))
        bio_pago = Decimal(str(metodo_pago.get("bio_pago", "0.00")))

        # Validar que la suma de los metodos de pago cubra el total.
        # Esto evita que se registre una venta como pagada parcialmente.
        # IMPORTANTE: efectivo_usd esta en dolares, hay que convertirlo a Bs
        # antes de sumarlo con los demas montos que estan en bolivares.
        if efectivo_usd > 0 and tasa is None:
            raise ValueError(
                "No hay una tasa de cambio activa registrada.\n"
                "Para cobrar en USD debe existir una tasa del dia.\n"
                "Vaya al Dashboard para que se cargue automaticamente."
            )
        efectivo_usd_en_bs = efectivo_usd * tasa.tasa_venta if tasa else Decimal("0.00")
        suma_pagos = efectivo_bs + efectivo_usd_en_bs + tarjeta + pago_movil + bio_pago
        if suma_pagos < total_bs:
            raise ValueError(
                f"La suma de los metodos de pago ({suma_pagos}) "
                f"no cubre el total de la venta ({total_bs})."
            )

        # ----------------------------------------------------------
        # PASO 7: Generar numero de factura automatico.
        # ----------------------------------------------------------
        # Formato: FAC-YYYYMMDD-NNN
        # Donde NNN es un numero secuencial del dia.
        # Ej: FAC-20250520-001 para la primera venta del 20/05/2026
        # Esto facilita la busqueda de facturas por fecha.
        hoy = datetime.now()
        fecha_str = hoy.strftime("%Y%m%d")

        # Buscar cuantas ventas se hicieron hoy para generar el correlativo.
        with obtener_sesion(db_session) as session:
            ventas_hoy = session.exec(
                select(Venta).where(
                    Venta.fecha_venta >= datetime(hoy.year, hoy.month, hoy.day),  # type: ignore[operator]
                    Venta.fecha_venta < datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59),  # type: ignore[operator]
                )
            ).all()
            # El correlativo es la cantidad de ventas de hoy + 1.
            # .zfill(3) asegura que sea de 3 digitos (001, 002, etc.).
            correlativo = str(len(ventas_hoy) + 1).zfill(3)
            numero_factura = f"FAC-{fecha_str}-{correlativo}"

            # ----------------------------------------------------------
            # PASO 8: Crear el objeto Venta (cabecera).
            # ----------------------------------------------------------
            # Aqui armamos el registro de la venta con todos los datos.
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
            # Hacemos flush() en lugar de commit() para obtener el ID
            # de la venta sin cerrar la transaccion. Asi podemos
            # agregar los detalles antes del commit final.
            session.flush()

            # Guardar el ID de la venta en una variable local.
            # Aunque hicimos flush(), mypy ve el tipo como int | None,
            # por eso usamos assert para asegurar que no sea None.
            venta_id = venta.idventa
            assert venta_id is not None, "No se pudo generar el ID de la venta"

            # ----------------------------------------------------------
            # PASO 9: Crear los detalles de la venta.
            # ----------------------------------------------------------
            # Ahora que venta tiene ID, creamos los VentaDetalle
            # y los vinculamos a la venta mediante venta_id.
            for det in detalles_lista:
                detalle = VentaDetalle(
                    venta_id=venta_id,
                    producto_id=int(str(det["producto_id"])),
                    cantidad=int(str(det["cantidad"])),
                    precio_unitario_bs=Decimal(str(det["precio_unitario_bs"])),
                    subtotal_bs=Decimal(str(det["subtotal_bs"])),
                )
                session.add(detalle)

            # ----------------------------------------------------------
            # PASO 10: Descontar del inventario (misma transaccion).
            # ----------------------------------------------------------
            for det in detalles_lista:
                producto = session.get(Producto, int(str(det["producto_id"])))
                if not producto:
                    raise ValueError(f"Producto ID {det['producto_id']} no existe.")
                cantidad_det = int(str(det["cantidad"]))
                if producto.stock_actual < cantidad_det:
                    raise ValueError(
                        f"Stock insuficiente para {producto.nombre_producto}. "
                        f"Disponible: {producto.stock_actual}, solicitado: {cantidad_det}"
                    )
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
                    fecha_movimiento=datetime.now(),
                )
                session.add(movimiento)

            # ----------------------------------------------------------
            # PASO 11: Confirmar todo en la BD (venta + inventario).
            # ----------------------------------------------------------
            session.commit()
            session.refresh(venta)

        return venta

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
                raise ValueError("La venta ya esta anulada.")

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
                select(VentaDetalle).where(VentaDetalle.venta_id == idventa)
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
            return session.exec(select(Venta).where(Venta.numero_factura == numero_factura)).first()

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
                .where(Venta.fecha_venta >= desde, Venta.fecha_venta <= hasta)  # type: ignore[operator]
                .order_by(Venta.fecha_venta.desc())  # type: ignore[union-attr]
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
