from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlmodel import Session

from sistema_financiero.core.reporte_service import ReporteService
from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.core.venta_controller import VentaController
from sistema_financiero.models import Producto
from sistema_financiero.utils import hoy


def _crear_producto(
    session: Session, nombre: str = "PROD", stock: Decimal = Decimal("20"),
    stock_minimo: Decimal = Decimal("5"), precio_bs: Decimal = Decimal("10.00"),
) -> Producto:
    producto = Producto(
        nombre_producto=nombre,
        precio_venta_bs=precio_bs,
        precio_venta_usd=Decimal("2.00"),
        stock_actual=stock,
        stock_minimo=stock_minimo,
    )
    session.add(producto)
    session.commit()
    session.refresh(producto)
    assert producto.idproducto is not None
    return producto


def _crear_tasa_y_venta(
    session: Session, producto_id: int, cantidad: int = 2,
    precio_bs: Decimal = Decimal("10.00"),
) -> VentaController:
    ts = TasaCambioService()
    ts.registrar(
        fecha=hoy(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("50.00"),
        activa=True,
        db_session=session,
    )
    vc = VentaController()
    vc.crear(
        productos=[{"idproducto": producto_id, "cantidad": cantidad}],
        metodo_pago={"efectivo_bs": Decimal(str(precio_bs * cantidad))},
        db_session=session,
    )
    return vc


def test_generar_reporte_sin_ventas(session: Session) -> None:
    rs = ReporteService()
    reporte = rs.generar_reporte(fecha_param=hoy(), db_session=session)

    assert reporte is not None
    assert reporte.total_ventas_bs == Decimal("0.00")
    assert reporte.total_ventas_usd == Decimal("0.00")
    assert reporte.cantidad_ventas == 0
    assert reporte.cantidad_productos_vendidos == 0


def test_generar_reporte_con_ventas(session: Session) -> None:
    producto = _crear_producto(session, precio_bs=Decimal("10.00"))
    assert producto.idproducto is not None
    _crear_tasa_y_venta(session, producto.idproducto, cantidad=3)

    rs = ReporteService()
    reporte = rs.generar_reporte(fecha_param=hoy(), db_session=session)

    assert reporte.cantidad_ventas == 1
    assert reporte.total_ventas_bs == Decimal("30.00")
    assert reporte.total_ventas_usd == Decimal("0.60")
    assert reporte.cantidad_productos_vendidos == 3
    assert reporte.efectivo_bs == Decimal("30.00")
    assert reporte.efectivo_usd == Decimal("0.00")
    assert reporte.tarjeta == Decimal("0.00")


def test_generar_reporte_con_varias_ventas(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("50"), precio_bs=Decimal("10.00"))
    ts = TasaCambioService()
    ts.registrar(
        fecha=hoy(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("50.00"),
        activa=True,
        db_session=session,
    )
    vc = VentaController()
    vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 2}],
        metodo_pago={"efectivo_bs": Decimal("20.00")},
        db_session=session,
    )
    vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 3}],
        metodo_pago={"efectivo_bs": Decimal("30.00")},
        db_session=session,
    )

    rs = ReporteService()
    reporte = rs.generar_reporte(fecha_param=hoy(), db_session=session)

    assert reporte.cantidad_ventas == 2
    assert reporte.total_ventas_bs == Decimal("50.00")
    assert reporte.cantidad_productos_vendidos == 5


def test_generar_reporte_stock_bajo_y_sin_stock(session: Session) -> None:
    _crear_producto(session, nombre="BAJO", stock=Decimal("3"), stock_minimo=Decimal("5"))
    _crear_producto(session, nombre="SIN", stock=Decimal("0"), stock_minimo=Decimal("5"))
    _crear_producto(session, nombre="NORMAL", stock=Decimal("20"), stock_minimo=Decimal("5"))

    rs = ReporteService()
    reporte = rs.generar_reporte(fecha_param=hoy(), db_session=session)

    assert reporte.productos_stock_bajo >= 1
    assert reporte.productos_sin_stock >= 1


def test_generar_reporte_regenerar(session: Session) -> None:
    rs = ReporteService()
    rs.generar_reporte(fecha_param=hoy(), db_session=session)
    rs.generar_reporte(fecha_param=hoy(), db_session=session)

    historial = rs.listar_por_rango(
        desde=hoy(), hasta=hoy(), db_session=session
    )
    assert len(historial) == 1


def test_obtener_por_fecha_exitoso(session: Session) -> None:
    rs = ReporteService()
    rs.generar_reporte(fecha_param=hoy(), db_session=session)

    reporte = rs.obtener_por_fecha(fecha_param=hoy(), db_session=session)
    assert reporte is not None
    assert reporte.fecha == hoy()


def test_obtener_por_fecha_inexistente(session: Session) -> None:
    rs = ReporteService()
    reporte = rs.obtener_por_fecha(fecha_param=date(2020, 1, 1), db_session=session)
    assert reporte is None


def test_listar_por_rango(session: Session) -> None:
    rs = ReporteService()
    rs.generar_reporte(fecha_param=hoy(), db_session=session)

    historial = rs.listar_por_rango(
        desde=date(2020, 1, 1),
        hasta=date(2030, 12, 31),
        db_session=session,
    )
    assert len(historial) >= 1


def test_exportar_excel(tmp_path: Path, session: Session) -> None:
    producto = _crear_producto(session, precio_bs=Decimal("10.00"))
    assert producto.idproducto is not None
    _crear_tasa_y_venta(session, producto.idproducto, cantidad=2)

    rs = ReporteService()
    reporte = rs.generar_reporte(fecha_param=hoy(), db_session=session)
    assert reporte.id is not None

    ruta = tmp_path / "test_reporte.xlsx"
    archivo = rs.exportar_excel(
        reporte_id=reporte.id,
        ruta_archivo=str(ruta),
        db_session=session,
    )

    assert Path(archivo).exists()
    assert Path(archivo).stat().st_size > 0


def test_exportar_excel_reporte_inexistente(session: Session) -> None:
    rs = ReporteService()
    with pytest.raises(ValueError, match="No existe el reporte"):
        rs.exportar_excel(reporte_id=9999, ruta_archivo="test.xlsx", db_session=session)
