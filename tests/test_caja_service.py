from decimal import Decimal

import pytest
from sqlmodel import Session

from sistema_financiero.core.caja_service import CajaService
from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.models import PagoVenta, Usuario, Venta
from sistema_financiero.utils.constantes import (
    METODO_PAGO_EFECTIVO_USD,
    MONEDA_USD,
)
from sistema_financiero.utils.fecha import hoy


def _crear_usuario(session: Session, id: int = 1, nombre: str = "admin") -> Usuario:
    usuario = Usuario(
        id=id,
        usuario=nombre,
        contrasena="hash_falso",
        nombre_completo="Test User",
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


def _registrar_tasa(session: Session, valor: Decimal = Decimal("30.00")) -> None:
    TasaCambioService().registrar(
        fecha=hoy(),
        tasa_venta=valor,
        tasa_compra=valor,
        activa=True,
        db_session=session,
    )


def _venta_con_pago_usd_recortado(session: Session, caja_id: int | None) -> Venta:
    """Venta de 100.00 Bs. pagada con 3.34 USD (aplica 100.00 y da 0.20 de vuelto)."""
    venta = Venta(
        caja_id=caja_id,
        total_bs=Decimal("100.00"),
        total_usd=Decimal("3.33"),
        efectivo_usd=Decimal("3.34"),
        estado="COMPLETADA",
    )
    session.add(venta)
    session.commit()
    session.refresh(venta)
    assert venta.idventa is not None
    session.add(
        PagoVenta(
            venta_id=venta.idventa,
            metodo=METODO_PAGO_EFECTIVO_USD,
            moneda=MONEDA_USD,
            monto=Decimal("3.34"),
            monto_bs=Decimal("100.00"),
            tasa_cambio=Decimal("30.00"),
        )
    )
    session.commit()
    return venta


def test_abrir_caja_exitoso(session: Session) -> None:
    usuario = _crear_usuario(session)
    assert usuario.id is not None
    caja_sk = CajaService(db_session=session)

    caja = caja_sk.abrir_caja(
        monto_apertura_bs=Decimal("100.00"),
        usuario_id=usuario.id,
    )

    assert caja.id is not None
    assert caja.monto_apertura_bs == Decimal("100.00")
    assert caja.usuario_id == usuario.id
    assert caja.estado == "ABIERTA"
    assert caja.fecha_apertura is not None


def test_abrir_caja_error_caja_abierta(session: Session) -> None:
    usuario = _crear_usuario(session)
    assert usuario.id is not None
    caja_sk = CajaService(db_session=session)

    caja_sk.abrir_caja(
        monto_apertura_bs=Decimal("100.00"),
        usuario_id=usuario.id,
    )

    with pytest.raises(ValueError, match="Ya existe una caja abierta"):
        caja_sk.abrir_caja(
            monto_apertura_bs=Decimal("50.00"),
            usuario_id=usuario.id,
        )


def test_obtener_caja_abierta(session: Session) -> None:
    usuario = _crear_usuario(session)
    assert usuario.id is not None
    caja_sk = CajaService(db_session=session)

    assert caja_sk.obtener_caja_abierta() is None

    caja = caja_sk.abrir_caja(
        monto_apertura_bs=Decimal("100.00"),
        usuario_id=usuario.id,
    )

    caja_abierta = caja_sk.obtener_caja_abierta()
    assert caja_abierta is not None
    assert caja_abierta.id == caja.id


def test_validar_caja_abierta_sin_caja(session: Session) -> None:
    caja_sk = CajaService(db_session=session)

    with pytest.raises(ValueError, match="No hay caja abierta"):
        caja_sk.validar_caja_abierta()


def test_cerrar_caja_error_no_existe(session: Session) -> None:
    caja_sk = CajaService(db_session=session)

    with pytest.raises(ValueError, match="No existe una caja con ese ID"):
        caja_sk.cerrar_caja(
            caja_id=999,
            billetes_bs=Decimal("100.00"),
            billetes_usd=Decimal("10.00"),
        )


def test_cerrar_caja_abierta(session: Session) -> None:
    usuario = _crear_usuario(session)
    assert usuario.id is not None
    caja_sk = CajaService(db_session=session)

    caja = caja_sk.abrir_caja(
        monto_apertura_bs=Decimal("100.00"),
        usuario_id=usuario.id,
    )
    assert caja.id is not None

    caja_cerrada = caja_sk.cerrar_caja(
        caja_id=caja.id,
        billetes_bs=Decimal("100.00"),
        billetes_usd=Decimal("0.00"),
    )

    assert caja_cerrada.id == caja.id
    assert caja_cerrada.estado == "CERRADA"
    assert caja_cerrada.fecha_cierre is not None


def test_historial_caja(session: Session) -> None:
    usuario = _crear_usuario(session)
    assert usuario.id is not None
    caja_sk = CajaService(db_session=session)

    historial_vacio = caja_sk.historial()
    assert historial_vacio == []

    caja1 = caja_sk.abrir_caja(
        monto_apertura_bs=Decimal("100.00"),
        usuario_id=usuario.id,
    )
    assert caja1.id is not None
    caja_sk.cerrar_caja(
        caja_id=caja1.id,
        billetes_bs=Decimal("100.00"),
        billetes_usd=Decimal("0.00"),
    )

    historial = caja_sk.historial()
    assert len(historial) == 1
    assert historial[0].estado == "CERRADA"


def test_cerrar_caja_sin_ventas(session: Session) -> None:
    usuario = _crear_usuario(session)
    assert usuario.id is not None
    caja_sk = CajaService(db_session=session)

    caja = caja_sk.abrir_caja(
        monto_apertura_bs=Decimal("100.00"),
        usuario_id=usuario.id,
    )
    assert caja.id is not None

    caja_cerrada = caja_sk.cerrar_caja(
        caja_id=caja.id,
        billetes_bs=Decimal("100.00"),
        billetes_usd=Decimal("0.00"),
    )

    assert caja_cerrada.cantidad_ventas == 0
    assert caja_cerrada.total_ventas_bs == Decimal("0.00")
    # Sin tasas registradas la conversion usa tasa 1.00.
    # Arqueo SOLO de efectivo: sobrante = (100 + 0*1) - (fondo 100 + 0 + 0) = 0
    assert caja_cerrada.sobrante_faltante_bs == Decimal("0.00")


def test_cerrar_caja_con_ventas(session: Session) -> None:
    usuario = _crear_usuario(session)
    assert usuario.id is not None
    caja_sk = CajaService(db_session=session)

    caja = caja_sk.abrir_caja(
        monto_apertura_bs=Decimal("50.00"),
        usuario_id=usuario.id,
    )
    assert caja.id is not None

    # Venta pagada EN PARTE en efectivo y en parte por transferencia.
    venta1 = Venta(
        caja_id=caja.id,
        total_bs=Decimal("35.00"),
        total_usd=Decimal("7.00"),
        efectivo_bs=Decimal("25.00"),
        transferencia=Decimal("10.00"),
        estado="COMPLETADA",
    )
    session.add(venta1)
    session.commit()

    caja_cerrada = caja_sk.cerrar_caja(
        caja_id=caja.id,
        billetes_bs=Decimal("75.00"),
        billetes_usd=Decimal("5.00"),
        observaciones="Cierre con ventas",
    )

    assert caja_cerrada.cantidad_ventas == 1
    assert caja_cerrada.total_ventas_bs == Decimal("35.00")
    # La transferencia se consolida como metodo de pago del turno...
    assert caja_cerrada.transferencia == Decimal("10.00")
    # ...pero NO cuenta en el arqueo (no es efectivo del cajon).
    # Sin tasa registrada, conversion con tasa 1.00.
    # sobrante = (75 + 5*1) - (fondo 50 + efectivo 25 + usd 0*1) = 80 - 75 = 5
    assert caja_cerrada.sobrante_faltante_bs == Decimal("5.00")
    assert caja_cerrada.observaciones == "Cierre con ventas"


def test_cierre_descuenta_el_vuelto_entregado_en_bs(session: Session) -> None:
    """Regresion: el vuelto en Bs. salio del cajon y no debe contar esperado.

    Pago en USD con tasa que no divide el total (3.34 USD a 30.00 = 100.20):
    el POS registra solo lo aplicado (100.00) y entrega 0.20 de vuelto en Bs.
    Antes el arqueo esperaba 110.20 y reportaba un faltante fantasma de 0.20.
    """
    _registrar_tasa(session, Decimal("30.00"))
    usuario = _crear_usuario(session)
    assert usuario.id is not None
    caja_sk = CajaService(db_session=session)

    caja = caja_sk.abrir_caja(
        monto_apertura_bs=Decimal("10.00"),
        usuario_id=usuario.id,
    )
    assert caja.id is not None
    _venta_con_pago_usd_recortado(session, caja.id)

    assert caja_sk.vuelto_entregado_bs(caja.id) == Decimal("0.20")

    # El cajon queda con 9.80 Bs. (fondo 10.00 - vuelto 0.20) y los 3.34 USD.
    caja_cerrada = caja_sk.cerrar_caja(
        caja_id=caja.id,
        billetes_bs=Decimal("9.80"),
        billetes_usd=Decimal("3.34"),
    )

    # esperado = fondo 10.00 + 0 + (3.34 * 30 = 100.20) - vuelto 0.20 = 110.00
    # fisico   = 9.80 + 3.34 * 30 = 110.00  ->  cuadra
    assert caja_cerrada.sobrante_faltante_bs == Decimal("0.00")


def test_cierre_sin_pagos_registrados_no_descuenta_vuelto(session: Session) -> None:
    """Ventas viejas (sin filas en venta_pago): el arqueo no cambia."""
    usuario = _crear_usuario(session)
    assert usuario.id is not None
    caja_sk = CajaService(db_session=session)

    caja = caja_sk.abrir_caja(
        monto_apertura_bs=Decimal("50.00"),
        usuario_id=usuario.id,
    )
    assert caja.id is not None
    session.add(
        Venta(
            caja_id=caja.id,
            total_bs=Decimal("35.00"),
            total_usd=Decimal("7.00"),
            efectivo_bs=Decimal("35.00"),
            estado="COMPLETADA",
        )
    )
    session.commit()

    assert caja_sk.vuelto_entregado_bs(caja.id) == Decimal("0.00")

    caja_cerrada = caja_sk.cerrar_caja(
        caja_id=caja.id,
        billetes_bs=Decimal("85.00"),
        billetes_usd=Decimal("0.00"),
    )

    # sobrante = 85 - (fondo 50 + efectivo 35) = 0
    assert caja_cerrada.sobrante_faltante_bs == Decimal("0.00")
