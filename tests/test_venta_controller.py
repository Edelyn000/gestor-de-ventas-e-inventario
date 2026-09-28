from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlmodel import Session, select

from sistema_financiero.core.caja_service import CajaService
from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.core.venta_controller import VentaController
from sistema_financiero.models import Producto, Usuario, Venta
from sistema_financiero.utils import a_local, ahora, hoy
from sistema_financiero.utils.fecha import rango_dia_utc

pytestmark = pytest.mark.integracion


def _crear_producto(
    session: Session,
    nombre: str = "PROD VENTA",
    stock: Decimal = Decimal("20"),
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


def _abrir_caja(session: Session, monto: Decimal = Decimal("100.00")) -> None:
    """Abre una caja en la sesion (requisito para registrar ventas)."""
    usuario = Usuario(
        usuario="admin_caja",
        contrasena="hash_falso",
        nombre_completo="Admin Caja",
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    assert usuario.id is not None
    caja_sk = CajaService(db_session=session)
    if caja_sk.obtener_caja_abierta() is None:
        caja_sk.abrir_caja(monto_apertura_bs=monto, usuario_id=usuario.id)


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
    _abrir_caja(session)
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
    assert venta.caja_id is not None

    session.refresh(producto)
    assert producto.stock_actual == 17


def test_crear_venta_usa_el_precio_bs_efectivo_del_pos(session: Session) -> None:
    """REGRESION (bug 367,00 vs 15.5000): el total usa el Bs. efectivo del POS."""
    producto = _crear_producto(
        session,
        nombre="PROD TASA VIEJA",
        stock=Decimal("10"),
        precio_bs=Decimal("15.50"),
    )
    _crear_tasa(session, tasa_valor=Decimal("100.00"))
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[
            {
                "idproducto": producto.idproducto,
                "cantidad": 1,
                "precio_bs": Decimal("200.00"),
                "subtotal_bs": Decimal("200.00"),
            }
        ],
        metodo_pago={"efectivo_bs": Decimal("200.00")},
        db_session=session,
    )

    assert venta.total_bs == Decimal("200.00")
    assert venta.idventa is not None
    detalle = vc.obtener_detalles(venta.idventa, db_session=session)[0]
    assert detalle.precio_unitario_bs == Decimal("200.00")
    assert detalle.subtotal_bs == Decimal("200.00")


def test_crear_venta_sin_precio_bs_usa_el_guardado(session: Session) -> None:
    """Sin precio_bs/subtotal_bs, se mantiene el Bs. guardado (compat)."""
    producto = _crear_producto(session, precio_bs=Decimal("10.00"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 2}],
        metodo_pago={"efectivo_bs": Decimal("20.00")},
        db_session=session,
    )
    assert venta.total_bs == Decimal("20.00")


def test_crear_venta_detalles(session: Session) -> None:
    producto = _crear_producto(session, precio_bs=Decimal("10.00"))
    _crear_tasa(session)
    _abrir_caja(session)
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
    _abrir_caja(session)
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


def test_crear_venta_sin_caja_abierta(session: Session) -> None:
    """Sin caja ABIERTA la venta debe ser rechazada."""
    producto = _crear_producto(session, precio_bs=Decimal("25.00"))
    _crear_tasa(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="No hay caja abierta"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
            metodo_pago={"efectivo_bs": Decimal("25.00")},
            db_session=session,
        )

    session.refresh(producto)
    assert producto.stock_actual == 20


def test_crear_venta_con_transferencia(session: Session) -> None:
    """Pago total por transferencia: se registra y no se mezcla con efectivo."""
    producto = _crear_producto(session, precio_bs=Decimal("50.00"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        metodo_pago={
            "efectivo_bs": Decimal("0.00"),
            "transferencia": Decimal("50.00"),
        },
        db_session=session,
    )

    assert venta.total_bs == Decimal("50.00")
    assert venta.efectivo_bs == Decimal("0.00")
    assert venta.transferencia == Decimal("50.00")


def test_anular_venta_caja_cerrada(session: Session) -> None:
    """No se puede anular una venta de un turno de caja YA cerrado."""
    producto = _crear_producto(session, stock=Decimal("10"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        metodo_pago={"efectivo_bs": Decimal("10.00")},
        db_session=session,
    )
    assert venta.idventa is not None
    assert venta.caja_id is not None

    caja_sk = CajaService(db_session=session)
    caja_sk.cerrar_caja(
        caja_id=venta.caja_id,
        billetes_bs=Decimal("0.00"),
        billetes_usd=Decimal("0.00"),
    )

    with pytest.raises(ValueError, match="turno de caja de esta venta"):
        vc.anular(venta.idventa, db_session=session)

    session.refresh(producto)
    assert producto.stock_actual == 9


def test_anular_venta(session: Session) -> None:
    producto = _crear_producto(session, stock=Decimal("10"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 3}],
        metodo_pago={"efectivo_bs": Decimal("30.00")},
        db_session=session,
    )
    assert venta.caja_id is not None

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


def test_anular_venta_guarda_motivo_y_usuario_que_autoriza(
    session: Session,
) -> None:
    """La anulacion persiste motivo_anulacion y anulado_por (auditoria)."""
    producto = _crear_producto(session, stock=Decimal("10"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 2}],
        metodo_pago={"efectivo_bs": Decimal("20.00")},
        db_session=session,
    )
    assert venta.idventa is not None

    anulada = vc.anular(
        venta.idventa,
        motivo_anulacion="Error de caja, se registro doble",
        anulado_por="jefa",
        db_session=session,
    )
    assert anulada is not None
    assert anulada.estado == "ANULADA"
    assert anulada.motivo_anulacion == "Error de caja, se registro doble"
    assert anulada.anulado_por == "jefa"

    session.refresh(producto)
    assert producto.stock_actual == 10


def test_anular_venta_sin_motivo_sigue_funcionando(session: Session) -> None:
    """Compatibilidad: anular sin motivo persiste la venta anulada igual."""
    producto = _crear_producto(session, stock=Decimal("5"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        metodo_pago={"efectivo_bs": Decimal("10.00")},
        db_session=session,
    )
    assert venta.idventa is not None

    anulada = vc.anular(venta.idventa, db_session=session)
    assert anulada is not None
    assert anulada.estado == "ANULADA"
    assert anulada.motivo_anulacion is None
    assert anulada.anulado_por is None


def test_anular_venta_ya_anulada(session: Session) -> None:
    producto = _crear_producto(session)
    _crear_tasa(session)
    _abrir_caja(session)
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
    _abrir_caja(session)
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
    _abrir_caja(session)
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
    _abrir_caja(session)
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


def test_historial_por_dia_local_incluye_venta_nocturna(session: Session) -> None:
    """Regresion del desfase de zona horaria: 'hoy' debe incluir las ventas de la noche."""
    producto = _crear_producto(session)
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        metodo_pago={"efectivo_bs": Decimal("10.00")},
        db_session=session,
    )

    venta = session.exec(select(Venta)).first()
    assert venta is not None
    venta.fecha_venta = datetime(2026, 1, 2, 0, 30, 0)
    session.commit()

    assert a_local(venta.fecha_venta) == datetime(2026, 1, 1, 20, 30, 0)

    desde, hasta = rango_dia_utc(date(2026, 1, 1))
    ventas_dia_1 = vc.historial_por_fecha(desde, hasta, db_session=session)
    assert venta.idventa in [v.idventa for v in ventas_dia_1]

    desde2, hasta2 = rango_dia_utc(date(2026, 1, 2))
    ventas_dia_2 = vc.historial_por_fecha(desde2, hasta2, db_session=session)
    assert venta.idventa not in [v.idventa for v in ventas_dia_2]


def test_obtener_detalles_sin_detalles(session: Session) -> None:
    vc = VentaController()
    detalles = vc.obtener_detalles(9999, db_session=session)
    assert detalles == []


def _pago(metodo: str, monto: str, referencia: str | None = None) -> dict[str, object]:
    """Helper: un pago del desglose tal como lo manda la UI."""
    return {"metodo": metodo, "monto": Decimal(monto), "referencia": referencia}


def test_crear_venta_con_desglose_de_pagos(session: Session) -> None:
    """Los montos por metodo de la venta se derivan del desglose de pagos."""
    producto = _crear_producto(session, precio_bs=Decimal("125.00"))
    _crear_tasa(session, Decimal("50.00"))
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        db_session=session,
        pagos=[
            _pago("efectivo_bs", "50.00"),
            _pago("tarjeta", "25.00"),
            _pago("efectivo_usd", "1.00"),
        ],
    )

    assert venta.total_bs == Decimal("125.00")
    assert venta.idventa is not None
    assert venta.efectivo_bs == Decimal("50.00")
    assert venta.tarjeta == Decimal("25.00")
    assert venta.efectivo_usd == Decimal("1.00")
    assert venta.pago_movil == Decimal("0.00")
    assert venta.bio_pago == Decimal("0.00")
    assert venta.transferencia == Decimal("0.00")

    pagos = vc.obtener_pagos(venta.idventa, db_session=session)
    assert [p.metodo for p in pagos] == ["efectivo_bs", "tarjeta", "efectivo_usd"]
    assert [p.moneda for p in pagos] == ["BS", "BS", "USD"]
    assert [p.monto_bs for p in pagos] == [
        Decimal("50.00"),
        Decimal("25.00"),
        Decimal("50.00"),
    ]
    assert [p.referencia for p in pagos] == [None, None, None]
    assert all(p.tasa_cambio == Decimal("50.00") for p in pagos)


def test_crear_venta_redondeo_efectivo_usd_un_centimo(session: Session) -> None:
    """Regresion: el pago en USD se acepta con 1 centimo de diferencia."""
    producto = _crear_producto(session, precio_bs=Decimal("100.01"))
    _crear_tasa(session, Decimal("1000.00"))
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        db_session=session,
        pagos=[_pago("efectivo_usd", "0.10")],
    )

    assert venta.total_bs == Decimal("100.01")
    assert venta.efectivo_usd == Decimal("0.10")
    assert venta.idventa is not None

    pagos = vc.obtener_pagos(venta.idventa, db_session=session)
    assert len(pagos) == 1
    assert pagos[0].monto_bs == Decimal("100.00")


def test_crear_venta_pago_insuficiente_con_desglose(session: Session) -> None:
    """Un faltante real (no un centimo de redondeo) sigue rechazandose."""
    producto = _crear_producto(session, precio_bs=Decimal("125.00"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="no coincide con el total"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
            db_session=session,
            pagos=[_pago("efectivo_bs", "95.00")],
        )


def test_crear_venta_pago_de_mas_con_desglose(session: Session) -> None:
    """Cobrar de mas tampoco cuadra: la suma debe cubrir el total exacto."""
    producto = _crear_producto(session, precio_bs=Decimal("100.00"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="no coincide con el total"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
            db_session=session,
            pagos=[_pago("efectivo_bs", "150.00")],
        )


def test_crear_venta_desglose_vacio(session: Session) -> None:
    """Una lista de pagos vacia se rechaza (no es lo mismo que omitirla)."""
    producto = _crear_producto(session, precio_bs=Decimal("10.00"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="al menos un pago"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
            db_session=session,
            pagos=[],
        )


def test_crear_venta_metodo_invalido(session: Session) -> None:
    """Un metodo de pago fuera de METODOS_PAGO se rechaza."""
    producto = _crear_producto(session, precio_bs=Decimal("10.00"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="Metodo de pago invalido"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
            db_session=session,
            pagos=[_pago("bitcoin", "10.00")],
        )


def test_crear_venta_metodo_pago_incoherente_con_desglose(session: Session) -> None:
    """Si el resumen por metodo no coincide con el desglose, no se guarda."""
    producto = _crear_producto(session, precio_bs=Decimal("125.00"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="no coincide con el detalle de pagos"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
            metodo_pago={"efectivo_bs": Decimal("10.00")},
            db_session=session,
            pagos=[_pago("efectivo_bs", "125.00")],
        )


def test_crear_venta_metodo_pago_coherente_con_desglose(session: Session) -> None:
    """Un resumen por metodo coherente con el desglose se acepta."""
    producto = _crear_producto(session, precio_bs=Decimal("125.00"))
    _crear_tasa(session, Decimal("50.00"))
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        metodo_pago={
            "efectivo_bs": Decimal("50.00"),
            "efectivo_usd": Decimal("1.50"),
        },
        db_session=session,
        pagos=[
            _pago("efectivo_bs", "50.00"),
            _pago("efectivo_usd", "1.50"),
        ],
    )

    assert venta.total_bs == Decimal("125.00")
    assert venta.efectivo_bs == Decimal("50.00")
    assert venta.efectivo_usd == Decimal("1.50")


def test_crear_venta_efectivo_usd_sin_tasa_con_desglose(session: Session) -> None:
    """Cobrar en USD sin tasa activa se rechaza (no se puede convertir)."""
    producto = _crear_producto(session, precio_bs=Decimal("100.00"))
    _abrir_caja(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="tasa de cambio activa"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
            db_session=session,
            pagos=[_pago("efectivo_usd", "10.00")],
        )


def test_crear_venta_sin_desglose_mantiene_comportamiento(session: Session) -> None:
    """Sin 'pagos' la venta se crea igual que antes y no guarda desglose."""
    producto = _crear_producto(session, precio_bs=Decimal("100.00"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        metodo_pago={
            "efectivo_bs": Decimal("60.00"),
            "tarjeta": Decimal("40.00"),
        },
        db_session=session,
    )

    assert venta.total_bs == Decimal("100.00")
    assert venta.efectivo_bs == Decimal("60.00")
    assert venta.tarjeta == Decimal("40.00")
    assert venta.idventa is not None
    assert vc.obtener_pagos(venta.idventa, db_session=session) == []


def test_crear_venta_honra_el_monto_aplicado_en_usd(session: Session) -> None:
    """Regresion: la UI manda el monto APLICADO en USD (recorte con vuelto)."""
    producto = _crear_producto(session, precio_bs=Decimal("100.00"))
    _crear_tasa(session, Decimal("30.00"))
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        db_session=session,
        pagos=[
            {
                "metodo": "efectivo_usd",
                "monto": Decimal("3.34"),
                "monto_bs": Decimal("100.00"),
            }
        ],
    )

    assert venta.total_bs == Decimal("100.00")
    assert venta.efectivo_usd == Decimal("3.34")
    assert venta.idventa is not None

    pagos = vc.obtener_pagos(venta.idventa, db_session=session)
    assert pagos[0].monto_bs == Decimal("100.00")


def test_crear_venta_rechaza_monto_aplicado_incoherente(session: Session) -> None:
    """Un monto aplicado que no se parece al equivalente se rechaza."""
    producto = _crear_producto(session, precio_bs=Decimal("100.00"))
    _crear_tasa(session, Decimal("30.00"))
    _abrir_caja(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="no coincide con su equivalente"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
            db_session=session,
            pagos=[
                {
                    "metodo": "efectivo_usd",
                    "monto": Decimal("3.34"),
                    "monto_bs": Decimal("50.00"),
                }
            ],
        )


def test_crear_venta_honra_el_monto_aplicado_en_bs(session: Session) -> None:
    """El POS cobra el RECIBIDO en Bs. y aplica el faltante (vuelto visible)."""
    producto = _crear_producto(session, precio_bs=Decimal("21648.20"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        db_session=session,
        pagos=[
            {
                "metodo": "efectivo_bs",
                "monto": Decimal("50000.00"),
                "monto_bs": Decimal("21648.20"),
            }
        ],
    )

    assert venta.total_bs == Decimal("21648.20")
    assert venta.efectivo_bs == Decimal("50000.00")
    assert venta.idventa is not None

    pagos = vc.obtener_pagos(venta.idventa, db_session=session)
    assert len(pagos) == 1
    assert pagos[0].metodo == "efectivo_bs"
    assert pagos[0].monto == Decimal("50000.00")
    assert pagos[0].monto_bs == Decimal("21648.20")


def test_crear_venta_rechaza_monto_aplicado_incoherente_en_bs(session: Session) -> None:
    """El aplicado en Bs. no puede superar lo recibido (guarda del POS)."""
    producto = _crear_producto(session, precio_bs=Decimal("100.00"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    with pytest.raises(ValueError, match="no coincide con su equivalente"):
        vc.crear(
            productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
            db_session=session,
            pagos=[
                {
                    "metodo": "efectivo_bs",
                    "monto": Decimal("500.00"),
                    "monto_bs": Decimal("1000.00"),
                }
            ],
        )


def test_crear_venta_pago_bs_sin_monto_aplicado_usa_el_recibido(session: Session) -> None:
    """Compat: sin 'monto_bs' el Bs. aplicado es el recibido (suma cuadra)."""
    producto = _crear_producto(session, precio_bs=Decimal("100.00"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        db_session=session,
        pagos=[_pago("efectivo_bs", "100.00")],
    )

    assert venta.total_bs == Decimal("100.00")
    assert venta.efectivo_bs == Decimal("100.00")


def test_crear_venta_referencia_se_guarda(session: Session) -> None:
    """La referencia del pago (nro. de operacion) se persiste."""
    producto = _crear_producto(session, precio_bs=Decimal("50.00"))
    _crear_tasa(session)
    _abrir_caja(session)
    vc = VentaController()

    venta = vc.crear(
        productos=[{"idproducto": producto.idproducto, "cantidad": 1}],
        db_session=session,
        pagos=[_pago("transferencia", "50.00", "1234")],
    )

    assert venta.idventa is not None
    pagos = vc.obtener_pagos(venta.idventa, db_session=session)
    assert len(pagos) == 1
    assert pagos[0].referencia == "1234"
    assert pagos[0].metodo == "transferencia"

