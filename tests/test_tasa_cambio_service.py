
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session, select

from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.models import TasaCambio
from sistema_financiero.utils import ORIGEN_TASA_BCV, ORIGEN_TASA_MANUAL, hoy

pytestmark = pytest.mark.unitarias


def test_registrar_exitoso(session: Session) -> None:
    """Registrar una tasa para hoy y verificar sus valores."""
    ts = TasaCambioService()
    hoy_date = hoy()

    tasa = ts.registrar(
        fecha=hoy_date,
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.50"),
        activa=True,
        db_session=session,
    )

    assert tasa is not None
    assert tasa.id is not None
    assert tasa.fecha == hoy_date
    assert tasa.tasa_venta == Decimal("50.00")
    assert tasa.tasa_compra == Decimal("49.50")
    assert tasa.activa is True
    assert tasa.fecha_registro is not None


def test_registrar_tasa_invalida(session: Session) -> None:
    ts = TasaCambioService()

    with pytest.raises(ValueError, match="deben ser mayores a cero"):
        ts.registrar(
            fecha=hoy(),
            tasa_venta=Decimal("0"),
            tasa_compra=Decimal("50.00"),
            db_session=session,
        )

    with pytest.raises(ValueError, match="deben ser mayores a cero"):
        ts.registrar(
            fecha=hoy(),
            tasa_venta=Decimal("50.00"),
            tasa_compra=Decimal("-1.00"),
            db_session=session,
        )


def test_registrar_tasa_duplicada(session: Session) -> None:
    ts = TasaCambioService()
    ts.registrar(
        fecha=hoy(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.50"),
        db_session=session,
    )

    with pytest.raises(ValueError, match="Ya existe una tasa"):
        ts.registrar(
            fecha=hoy(),
            tasa_venta=Decimal("55.00"),
            tasa_compra=Decimal("54.50"),
            db_session=session,
        )


def test_tasa_activa_exitoso(session: Session) -> None:
    """Registrar una tasa activa y verificar que tasa_activa() la encuentre."""
    ts = TasaCambioService()
    ts.registrar(
        fecha=hoy(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.50"),
        activa=True,
        db_session=session,
    )

    tasa = ts.tasa_activa(db_session=session)
    assert tasa is not None
    assert tasa.tasa_venta == Decimal("50.00")
    assert tasa.activa is True


def test_tasa_activa_sin_tasas(session: Session) -> None:
    ts = TasaCambioService()
    tasa = ts.tasa_activa(db_session=session)
    assert tasa is None


def test_tasa_activa_con_varias_tasas(session: Session) -> None:
    """Registrar tasas en dias distintos y verificar que retorne la mas reciente."""
    ts = TasaCambioService()
    ts.registrar(
        fecha=date(2024, 1, 1),
        tasa_venta=Decimal("40.00"),
        tasa_compra=Decimal("39.00"),
        activa=True,
        db_session=session,
    )
    ts.registrar(
        fecha=date(2025, 1, 1),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.00"),
        activa=True,
        db_session=session,
    )

    tasa = ts.tasa_activa(db_session=session)
    assert tasa is not None
    assert tasa.fecha == date(2025, 1, 1)
    assert tasa.tasa_venta == Decimal("50.00")


def test_obtener_por_fecha(session: Session) -> None:
    ts = TasaCambioService()
    ts.registrar(
        fecha=date(2025, 6, 1),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.50"),
        db_session=session,
    )

    tasa = ts.obtener_por_fecha(fecha=date(2025, 6, 1), db_session=session)
    assert tasa is not None
    assert tasa.tasa_venta == Decimal("50.00")


def test_obtener_por_fecha_inexistente(session: Session) -> None:
    ts = TasaCambioService()
    tasa = ts.obtener_por_fecha(fecha=date(2020, 1, 1), db_session=session)
    assert tasa is None


def test_historial(session: Session) -> None:
    """Registrar 2 tasas y verificar que el historial las incluya."""
    ts = TasaCambioService()
    ts.registrar(
        fecha=date(2025, 1, 1),
        tasa_venta=Decimal("40.00"),
        tasa_compra=Decimal("39.00"),
        db_session=session,
    )
    ts.registrar(
        fecha=date(2026, 1, 1),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.00"),
        db_session=session,
    )

    historial = ts.historial(db_session=session)
    assert len(historial) == 2
    assert historial[0].fecha == date(2026, 1, 1)
    assert historial[1].fecha == date(2025, 1, 1)


def test_desactivar_tasa(session: Session) -> None:
    """Desactivar una tasa y verificar que ya no aparezca como activa."""
    ts = TasaCambioService()
    tasa = ts.registrar(
        fecha=hoy(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.50"),
        activa=True,
        db_session=session,
    )

    assert tasa.id is not None
    resultado = ts.desactivar_tasa(tasa_id=tasa.id, db_session=session)
    assert resultado is True

    activa = ts.tasa_activa(db_session=session)
    assert activa is None or activa.id != tasa.id

    tasa_refrescada = ts.obtener_por_fecha(fecha=hoy(), db_session=session)
    assert tasa_refrescada is not None
    assert tasa_refrescada.activa is False


def test_desactivar_tasa_inexistente(session: Session) -> None:
    ts = TasaCambioService()
    resultado = ts.desactivar_tasa(tasa_id=9999, db_session=session)
    assert resultado is False


def test_obtener_desde_bcv_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """obtener_desde_bcv() con el BCV inaccesible (sin internet, caido)
    retorna None sin lanzar excepcion. Test DETERMINISTA: el fallo se
    simula en bcv_obtener_tasa (no se toca la red real), y la escritura
    del log de errores se neutraliza para no ensuciar logs/."""
    ts = TasaCambioService()

    def _falla_sin_red() -> Decimal:
        raise ConnectionError("Sin conexion al BCV")

    monkeypatch.setattr(
        "sistema_financiero.core.tasa_cambio_service.bcv_obtener_tasa",
        _falla_sin_red,
    )
    monkeypatch.setattr(
        "sistema_financiero.core.tasa_cambio_service.registrar_excepcion",
        lambda *_args, **_kwargs: None,
    )

    resultado = ts.obtener_desde_bcv()

    assert resultado is None


def test_obtener_desde_bcv_actualiza_la_fila_de_hoy(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
) -> None:
    """obtener_desde_bcv() con el BCV accesible registra (y luego
    actualiza por UPSERT) la fila de HOY: la tasa del dia se refresca
    sin crear duplicados. Determinista: red y BD real neutralizadas."""
    ts = TasaCambioService()

    @contextmanager
    def _misma_sesion(db_session: Session | None = None) -> Iterator[Session]:
        yield session

    monkeypatch.setattr(
        "sistema_financiero.core.tasa_cambio_service.obtener_sesion",
        _misma_sesion,
    )

    def _tasa_859() -> Decimal:
        return Decimal("859.00")

    def _tasa_861() -> Decimal:
        return Decimal("861.00")

    monkeypatch.setattr(
        "sistema_financiero.core.tasa_cambio_service.bcv_obtener_tasa",
        _tasa_859,
    )
    primero = ts.obtener_desde_bcv()
    assert primero is not None
    assert primero.tasa_venta == Decimal("859.00")

    monkeypatch.setattr(
        "sistema_financiero.core.tasa_cambio_service.bcv_obtener_tasa",
        _tasa_861,
    )
    segundo = ts.obtener_desde_bcv()
    assert segundo is not None
    assert segundo.tasa_venta == Decimal("861.00")

    historial = ts.historial(db_session=session)
    assert len(historial) == 1
    assert historial[0].tasa_venta == Decimal("861.00")


def test_registrar_tasa_manual_con_origen_y_auditoria(session: Session) -> None:
    ts = TasaCambioService()

    tasa = ts.registrar_tasa_manual(
        Decimal("860.00"),
        registrado_por="cajero_prueba",
        db_session=session,
    )

    assert tasa is not None
    assert tasa.id is not None
    assert tasa.origen == ORIGEN_TASA_MANUAL
    assert tasa.registrado_por == "cajero_prueba"
    assert tasa.tasa_venta == Decimal("860.00")
    assert tasa.tasa_compra == Decimal("860.00")
    assert tasa.activa is True
    assert tasa.fecha == hoy()


def test_registrar_tasa_manual_upsert_mismo_dia(session: Session) -> None:
    ts = TasaCambioService()
    ts.registrar_tasa_manual(Decimal("860.00"), db_session=session)
    tasa2 = ts.registrar_tasa_manual(Decimal("900.00"), db_session=session)

    assert tasa2 is not None
    assert tasa2.id is not None
    assert tasa2.tasa_venta == Decimal("900.00")

    filas = session.exec(
        select(TasaCambio).where(
            TasaCambio.fecha == hoy(),
            TasaCambio.origen == ORIGEN_TASA_MANUAL,
        )
    ).all()
    assert len(filas) == 1


def test_registrar_tasa_manual_invalida(session: Session) -> None:
    ts = TasaCambioService()

    with pytest.raises(ValueError, match="mayor a cero"):
        ts.registrar_tasa_manual(Decimal("0"), db_session=session)


def test_tasa_manual_no_aparece_en_tasa_activa(session: Session) -> None:
    ts = TasaCambioService()
    ts.registrar(
        fecha=hoy(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.50"),
        activa=True,
        db_session=session,
    )
    ts.registrar_tasa_manual(Decimal("860.00"), db_session=session)

    activa = ts.tasa_activa(db_session=session)
    assert activa is not None
    assert activa.origen == ORIGEN_TASA_BCV
    assert activa.tasa_venta == Decimal("50.00")


def test_misma_fecha_origen_distinto_permitido(session: Session) -> None:
    ts = TasaCambioService()
    ts.registrar(
        fecha=hoy(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.50"),
        activa=True,
        db_session=session,
    )
    manual = ts.registrar_tasa_manual(Decimal("860.00"), db_session=session)

    assert manual is not None
    assert manual.origen == ORIGEN_TASA_MANUAL


def test_desactivar_tasa_manual(session: Session) -> None:
    ts = TasaCambioService()
    ts.registrar_tasa_manual(Decimal("860.00"), db_session=session)

    resultado = ts.desactivar_tasa_manual(db_session=session)
    assert resultado is True

    existente = session.exec(
        select(TasaCambio).where(
            TasaCambio.fecha == hoy(),
            TasaCambio.origen == ORIGEN_TASA_MANUAL,
        )
    ).first()
    assert existente is not None
    assert existente.activa is False


def test_desactivar_tasa_manual_sin_registro(session: Session) -> None:
    ts = TasaCambioService()
    resultado = ts.desactivar_tasa_manual(db_session=session)
    assert resultado is False

