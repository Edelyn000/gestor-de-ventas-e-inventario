# ============================================================
# ARCHIVO: tests/test_reporte_service.py
# Pruebas para el servicio de reportes (ReporteService).
#
# ¿QUE ES ReporteService?
#   Servicio que genera reportes diarios consolidando las
#   ventas de un dia. Tambien exporta a Excel.
#
# QUE HACE:
#   - generar_reporte() → Consolida ventas del dia en un ReporteDiario.
#   - obtener_por_fecha() → Busca un reporte existente por fecha.
#   - listar_por_rango() → Historial de reportes entre dos fechas.
#   - exportar_excel() → Crea un archivo .xlsx con formato profesional.
#
# ¿QUE VERIFICAN ESTOS TESTS?
#   - Generacion de reporte con/sin ventas.
#   - Totales consolidados correctos (VES, USD, metodos de pago).
#   - Conteo de productos vendidos, stock bajo, sin stock.
#   - Regeneracion del reporte (reemplazo).
#   - Busqueda por fecha y rango.
#   - Exportacion a Excel.
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from sistema_financiero.core.reporte_service import ReporteService
from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.core.venta_controller import VentaController
from sistema_financiero.models import Producto


# ============================================================
# FUNCION AUXILIAR: _crear_producto
# ============================================================
def _crear_producto(
    session, nombre="PROD", stock=20, stock_minimo=5, precio_bs=Decimal("10.00")
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
    return producto


# ============================================================
# FUNCION AUXILIAR: _crear_tasa_y_venta
# Crea una tasa activa y una venta para tener datos que reportar.
# ============================================================
def _crear_tasa_y_venta(session, producto_id, cantidad=2, precio_bs=Decimal("10.00")):
    """Crea una tasa activa y una venta. Retorna el VentaController."""
    ts = TasaCambioService()
    ts.registrar(
        fecha=datetime.now().date(),
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


# ============================================================
# TEST: test_generar_reporte_sin_ventas
# ¿QUE PRUEBA? Generar reporte cuando no hubo ventas en el dia.
# ============================================================
def test_generar_reporte_sin_ventas(session) -> None:
    """Sin ventas, el reporte debe tener totales en cero."""
    rs = ReporteService()
    reporte = rs.generar_reporte(fecha_param=date.today(), db_session=session)

    assert reporte is not None
    assert reporte.total_ventas_bs == Decimal("0.00")
    assert reporte.total_ventas_usd == Decimal("0.00")
    assert reporte.cantidad_ventas == 0
    assert reporte.cantidad_productos_vendidos == 0


# ============================================================
# TEST: test_generar_reporte_con_ventas
# ¿QUE PRUEBA? Generar reporte con 1 venta y verificar totales.
# ============================================================
def test_generar_reporte_con_ventas(session) -> None:
    """Vender 3 unidades a 10.00 c/u = 30.00 Bs, 0.60 USD."""
    producto = _crear_producto(session, precio_bs=Decimal("10.00"))
    _crear_tasa_y_venta(session, producto.idproducto, cantidad=3)  # type: ignore[arg-type]

    rs = ReporteService()
    reporte = rs.generar_reporte(fecha_param=date.today(), db_session=session)

    assert reporte.cantidad_ventas == 1
    assert reporte.total_ventas_bs == Decimal("30.00")
    assert reporte.total_ventas_usd == Decimal("0.60")  # 30 / 50
    assert reporte.cantidad_productos_vendidos == 3

    # Metodo de pago: efectivo_bs = 30.00
    assert reporte.efectivo_bs == Decimal("30.00")
    assert reporte.efectivo_usd == Decimal("0.00")
    assert reporte.tarjeta == Decimal("0.00")


# ============================================================
# TEST: test_generar_reporte_con_varias_ventas
# ¿QUE PRUEBA? Que consolide multiples ventas correctamente.
# ============================================================
def test_generar_reporte_con_varias_ventas(session) -> None:
    """2 ventas: 2*10=20 + 3*10=30 → total 50 Bs."""
    producto = _crear_producto(session, stock=50, precio_bs=Decimal("10.00"))
    ts = TasaCambioService()
    ts.registrar(
        fecha=datetime.now().date(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("50.00"),
        activa=True,
        db_session=session,
    )
    vc = VentaController()
    vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 2}],  # type: ignore[arg-type]
        metodo_pago={"efectivo_bs": Decimal("20.00")},
        db_session=session,
    )
    vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 3}],  # type: ignore[arg-type]
        metodo_pago={"efectivo_bs": Decimal("30.00")},
        db_session=session,
    )

    rs = ReporteService()
    reporte = rs.generar_reporte(fecha_param=date.today(), db_session=session)

    assert reporte.cantidad_ventas == 2
    assert reporte.total_ventas_bs == Decimal("50.00")
    assert reporte.cantidad_productos_vendidos == 5  # 2 + 3


# ============================================================
# TEST: test_generar_reporte_stock_bajo_y_sin_stock
# ¿QUE PRUEBA? Que cuente alertas de stock correctamente.
# ============================================================
def test_generar_reporte_stock_bajo_y_sin_stock(session) -> None:
    """Crear productos con stock bajo (1) y sin stock (0)."""
    _crear_producto(session, nombre="BAJO", stock=3, stock_minimo=5)  # stock bajo
    _crear_producto(session, nombre="SIN", stock=0, stock_minimo=5)   # sin stock
    _crear_producto(session, nombre="NORMAL", stock=20, stock_minimo=5)  # normal

    rs = ReporteService()
    reporte = rs.generar_reporte(fecha_param=date.today(), db_session=session)

    assert reporte.productos_stock_bajo >= 1
    assert reporte.productos_sin_stock >= 1


# ============================================================
# TEST: test_generar_reporte_regenerar
# ¿QUE PRUEBA? Que regenerar el reporte reemplace el anterior.
# ============================================================
def test_generar_reporte_regenerar(session) -> None:
    """Generar reporte dos veces no debe crear duplicados."""
    rs = ReporteService()
    rs.generar_reporte(fecha_param=date.today(), db_session=session)
    rs.generar_reporte(fecha_param=date.today(), db_session=session)

    # Solo debe haber 1 reporte para hoy.
    historial = rs.listar_por_rango(
        desde=date.today(), hasta=date.today(), db_session=session
    )
    assert len(historial) == 1


# ============================================================
# TEST: test_obtener_por_fecha_exitoso
# ============================================================
def test_obtener_por_fecha_exitoso(session) -> None:
    rs = ReporteService()
    rs.generar_reporte(fecha_param=date.today(), db_session=session)

    reporte = rs.obtener_por_fecha(fecha_param=date.today(), db_session=session)
    assert reporte is not None
    assert reporte.fecha == date.today()


# ============================================================
# TEST: test_obtener_por_fecha_inexistente
# ============================================================
def test_obtener_por_fecha_inexistente(session) -> None:
    rs = ReporteService()
    reporte = rs.obtener_por_fecha(fecha_param=date(2020, 1, 1), db_session=session)
    assert reporte is None


# ============================================================
# TEST: test_listar_por_rango
# ============================================================
def test_listar_por_rango(session) -> None:
    """Crear reportes en distintas fechas y verificar el rango."""
    rs = ReporteService()
    rs.generar_reporte(fecha_param=date.today(), db_session=session)

    historial = rs.listar_por_rango(
        desde=date(2020, 1, 1),
        hasta=date(2030, 12, 31),
        db_session=session,
    )
    assert len(historial) >= 1


# ============================================================
# TEST: test_exportar_excel
# ¿QUE PRUEBA? Que exportar_excel() cree un archivo .xlsx valido.
# ============================================================
def test_exportar_excel(tmp_path, session) -> None:
    """Generar reporte con datos y exportarlo a Excel."""
    producto = _crear_producto(session, precio_bs=Decimal("10.00"))
    _crear_tasa_y_venta(session, producto.idproducto, cantidad=2)  # type: ignore[arg-type]

    rs = ReporteService()
    reporte = rs.generar_reporte(fecha_param=date.today(), db_session=session)

    ruta = tmp_path / "test_reporte.xlsx"
    archivo = rs.exportar_excel(
        reporte_id=reporte.id,  # type: ignore[arg-type]
        ruta_archivo=str(ruta),
        db_session=session,
    )

    assert Path(archivo).exists()
    assert Path(archivo).stat().st_size > 0


# ============================================================
# TEST: test_exportar_excel_reporte_inexistente
# ============================================================
def test_exportar_excel_reporte_inexistente(session) -> None:
    rs = ReporteService()
    with pytest.raises(ValueError, match="No existe el reporte"):
        rs.exportar_excel(reporte_id=9999, ruta_archivo="test.xlsx", db_session=session)
