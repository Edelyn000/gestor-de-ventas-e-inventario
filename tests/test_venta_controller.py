from datetime import datetime
from decimal import Decimal

import pytest
from sqlmodel import Session

from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.core.venta_controller import VentaController
from sistema_financiero.models import Producto
from sistema_financiero.utils import ahora, hoy


def _crear_producto(
    session: Session, nombre: str = "PROD VENTA", stock: Decimal = Decimal("20"),
    precio_bs: Decimal = Decimal("10.00"),
) -> Producto:
    producto = Producto(
        nombre_producto=nombre,
        precio_venta_bs=precio_bs,
        precio_venta_usd=Decimal("2.00"),
        stock_actual=stock,
        stock_minimo=Decimal("5"),
    )
    session.add(producto)
    session.commit()
    session.refresh(producto)
    assert producto.idproducto is not None
    return producto


def _crear_tasa(session: Session, tasa_valor: Decimal = Decimal("50.00")) -> None:
    ts = TasaCambioService()
    ts.registrar(
        fecha=hoy(),
        tasa_venta=tasa_valor,
        tasa_compra=tasa_valor,
        activa=True,
        db_session=session,
    )


def test_crear_venta_exitoso(session: Session) -> None:
    producto = _crear_producto(session, precio_bs=Decimal("25.00"))
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 3}],
        metodo_pago={"efectivo_bs": Decimal("75.00")},
        db_session=session,
    )

    assert venta is not None
    assert venta.idventa is not None
    assert venta.numero_factura is not None
    assert venta.numero_factura.startswith("FAC-")
    assert venta.estado == "COMPLETADA"
    assert venta.total_bs == Decimal("75.00")
    assert venta.total_usd == Decimal("1.50")

    session.refresh(producto)
    assert producto.stock_actual == 17


def test_crear_venta_detalles(session: Session) -> None:
    producto = _crear_producto(session, precio_bs=Decimal("10.00"))
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 2}],
        metodo_pago={"efectivo_bs": Decimal("20.00")},
        db_session=session,
    )
    assert venta.idventa is not None

    detalles = vc.obtener_detalles(venta.idventa, db_session=session)
    assert len(detalles) == 1
    detalle = detalles[0]
    assert detalle.producto_id == producto.idproducto
    assert detalle.cantidad == 2
    assert detalle.precio_unitario_bs == Decimal("10.00")
    assert detalle.subtotal_bs == Decimal("20.00")
    assert detalle.venta_id == venta.idventa


def test_crear_venta_sin_productos(session: Session) -> None:
    vc = VentaController()
    with pytest.raises(ValueError, match="debe tener al menos un producto"):
        vc.crear(productos=[], db_session=session)


def test_crear_venta_cantidad_cero(session: Session) -> None:
    producto = _crear_producto(session)
    _crear_tasa(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="debe ser mayor a cero"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 0}],
            db_session=session,
        )


def test_crear_venta_stock_insuficiente(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("2"))
    _crear_tasa(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="Stock insuficiente"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 10}],
            db_session=session,
        )

    session.refresh(producto)
    assert producto.stock_actual == 2


def test_crear_venta_pago_insuficiente(session: Session) -> None:
    producto = _crear_producto(session, precio_bs=Decimal("100.00"))
    _crear_tasa(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="no cubre el total"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
            metodo_pago={"efectivo_bs": Decimal("50.00")},
            db_session=session,
        )


def test_crear_venta_con_varios_productos(session: Session) -> None:
    prod1 = _crear_producto(session, nombre="PROD A", precio_bs=Decimal("10.00"))
    prod2 = _crear_producto(session, nombre="PROD B", precio_bs=Decimal("20.00"))
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[
            {"idproducto": prod1.idproducto, "cantidad": 2},
            {"idproducto": prod2.idproducto, "cantidad": 3},
        ],
        metodo_pago={"efectivo_bs": Decimal("80.00")},
        db_session=session,
    )

    assert venta.total_bs == Decimal("80.00")
    assert venta.idventa is not None
    detalles = vc.obtener_detalles(venta.idventa, db_session=session)
    assert len(detalles) == 2


def test_anular_venta(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("10"))
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 3}],
        metodo_pago={"efectivo_bs": Decimal("30.00")},
        db_session=session,
    )

    session.refresh(producto)
    assert producto.stock_actual == 7
    assert venta.idventa is not None

    anulada = vc.anular(venta.idventa, db_session=session)
    assert anulada is not None
    assert anulada is not None
    assert anulada.estado == "ANULADA"

    session.refresh(producto)
    assert producto.stock_actual == 10


def test_anular_venta_inexistente(session: Session) -> None:
    vc = VentaController()
    resultado = vc.anular(9999, db_session=session)
    assert resultado is None


def test_anular_venta_ya_anulada(session: Session) -> None:
    producto = _crear_producto(session)
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        metodo_pago={"efectivo_bs": Decimal("10.00")},
        db_session=session,
    )
    assert venta.idventa is not None

    vc.anular(venta.idventa, db_session=session)

    with pytest.raises(ValueError, match="ya esta anulada"):
        vc.anular(venta.idventa, db_session=session)


def test_obtener_por_id(session: Session) -> None:
    producto = _crear_producto(session)
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        metodo_pago={"efectivo_bs": Decimal("10.00")},
        db_session=session,
    )
    assert venta.idventa is not None

    encontrada = vc.obtener_por_id(venta.idventa, db_session=session)
    assert encontrada is not None
    assert encontrada.idventa == venta.idventa


def test_obtener_por_id_inexistente(session: Session) -> None:
    vc = VentaController()
    resultado = vc.obtener_por_id(9999, db_session=session)
    assert resultado is None


def test_buscar_por_factura(session: Session) -> None:
    producto = _crear_producto(session)
    _crear_tasa(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        metodo_pago={"efectivo_bs": Decimal("10.00")},
        db_session=session,
    )
    assert venta.numero_factura is not None

    encontrada = vc.buscar_por_factura(venta.numero_factura, db_session=session)
    assert encontrada is not None
    assert encontrada.idventa == venta.idventa


def test_buscar_por_factura_inexistente(session: Session) -> None:
    vc = VentaController()
    resultado = vc.buscar_por_factura("FAC-99999999-999", db_session=session)
    assert resultado is None


def test_historial_por_fecha(session: Session) -> None:
    producto = _crear_producto(session)
    _crear_tasa(session)
    vc = VentaController()

    vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        metodo_pago={"efectivo_bs": Decimal("10.00")},
        db_session=session,
    )
    vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 2}],
        metodo_pago={"efectivo_bs": Decimal("20.00")},
        db_session=session,
    )

    hoy_dt = ahora()
    desde = datetime(hoy_dt.year, hoy_dt.month, hoy_dt.day, 0, 0, 0)
    hasta = datetime(hoy_dt.year, hoy_dt.month, hoy_dt.day, 23, 59, 59)
    ventas = vc.historial_por_fecha(desde, hasta, db_session=session)
    assert len(ventas) == 2
    assert ventas[0].total_bs == Decimal("20.00")


def test_obtener_detalles_sin_detalles(session: Session) -> None:
    vc = VentaController()
    detalles = vc.obtener_detalles(9999, db_session=session)
    assert detalles == []
