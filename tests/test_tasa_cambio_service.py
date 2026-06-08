# ============================================================
# ARCHIVO: tests/test_tasa_cambio_service.py
# Pruebas para el servicio de tasas de cambio (TasaCambioService).
#
# ¿QUE ES TasaCambioService?
#   Gestiona las tasas de cambio VES/USD. Permite:
#   - registrar()         → Crea una nueva tasa para una fecha.
#   - tasa_activa()       → Devuelve la tasa activa mas reciente.
#   - obtener_por_fecha() → Busca tasa de una fecha especifica.
#   - historial()         → Todas las tasas ordenadas.
#   - desactivar_tasa()   → Marca una tasa como inactiva.
#   - obtener_desde_bcv() → Obtiene la tasa actual del BCV.
#
# ¿QUE VERIFICAN ESTOS TESTS?
#   - Registro de tasa con valores validos.
#   - Validacion de tasas <= 0.
#   - Prevencion de duplicados por fecha.
#   - tasa_activa() cuando hay 1 o varias tasas.
#   - tasa_activa() retorna None si ninguna esta activa.
#   - Desactivar tasa (activa → inactiva).
#   - Historial ordenado de mas reciente a mas antigua.
#   - obtener_desde_bcv() que maneje errores de conexion.
# ============================================================

from datetime import date
from decimal import Decimal

import pytest

from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.models import TasaCambio


# ============================================================
# TEST: test_registrar_exitoso
# ¿QUE PRUEBA? Crear una tasa de cambio correctamente.
# ============================================================
def test_registrar_exitoso(session) -> None:
    """Registrar una tasa para hoy y verificar sus valores."""
    ts = TasaCambioService()
    hoy = date.today()

    tasa = ts.registrar(
        fecha=hoy,
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.50"),
        activa=True,
        db_session=session,
    )

    assert tasa is not None
    assert tasa.id is not None
    assert tasa.fecha == hoy
    assert tasa.tasa_venta == Decimal("50.00")
    assert tasa.tasa_compra == Decimal("49.50")
    assert tasa.activa is True
    assert tasa.fecha_registro is not None


# ============================================================
# TEST: test_registrar_tasa_invalida
# ¿QUE PRUEBA? Que registrar() rechace tasas <= 0.
# ============================================================
def test_registrar_tasa_invalida(session) -> None:
    ts = TasaCambioService()

    with pytest.raises(ValueError, match="deben ser mayores a cero"):
        ts.registrar(
            fecha=date.today(),
            tasa_venta=Decimal("0"),
            tasa_compra=Decimal("50.00"),
            db_session=session,
        )

    with pytest.raises(ValueError, match="deben ser mayores a cero"):
        ts.registrar(
            fecha=date.today(),
            tasa_venta=Decimal("50.00"),
            tasa_compra=Decimal("-1.00"),
            db_session=session,
        )


# ============================================================
# TEST: test_registrar_tasa_duplicada
# ¿QUE PRUEBA? Que no se pueda registrar 2 tasas para la misma fecha.
# ============================================================
def test_registrar_tasa_duplicada(session) -> None:
    ts = TasaCambioService()
    ts.registrar(
        fecha=date.today(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.50"),
        db_session=session,
    )

    with pytest.raises(ValueError, match="Ya existe una tasa"):
        ts.registrar(
            fecha=date.today(),
            tasa_venta=Decimal("55.00"),
            tasa_compra=Decimal("54.50"),
            db_session=session,
        )


# ============================================================
# TEST: test_tasa_activa_exitoso
# ¿QUE PRUEBA? Que tasa_activa() devuelva la tasa activa correcta.
# ============================================================
def test_tasa_activa_exitoso(session) -> None:
    """Registrar una tasa activa y verificar que tasa_activa() la encuentre."""
    ts = TasaCambioService()
    ts.registrar(
        fecha=date.today(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.50"),
        activa=True,
        db_session=session,
    )

    tasa = ts.tasa_activa(db_session=session)
    assert tasa is not None
    assert tasa.tasa_venta == Decimal("50.00")
    assert tasa.activa is True


# ============================================================
# TEST: test_tasa_activa_sin_tasas
# ¿QUE PRUEBA? Si no hay tasas registradas, retorna None.
# ============================================================
def test_tasa_activa_sin_tasas(session) -> None:
    ts = TasaCambioService()
    tasa = ts.tasa_activa(db_session=session)
    assert tasa is None


# ============================================================
# TEST: test_tasa_activa_con_varias_tasas
# ¿QUE PRUEBA? Con varias tasas activas, retorna la mas reciente.
# ============================================================
def test_tasa_activa_con_varias_tasas(session) -> None:
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


# ============================================================
# TEST: test_obtener_por_fecha
# ============================================================
def test_obtener_por_fecha(session) -> None:
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


# ============================================================
# TEST: test_obtener_por_fecha_inexistente
# ============================================================
def test_obtener_por_fecha_inexistente(session) -> None:
    ts = TasaCambioService()
    tasa = ts.obtener_por_fecha(fecha=date(2020, 1, 1), db_session=session)
    assert tasa is None


# ============================================================
# TEST: test_historial
# ============================================================
def test_historial(session) -> None:
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
    # Debe estar ordenado descendente: 2026 primero, luego 2025.
    assert historial[0].fecha == date(2026, 1, 1)
    assert historial[1].fecha == date(2025, 1, 1)


# ============================================================
# TEST: test_desactivar_tasa
# ============================================================
def test_desactivar_tasa(session) -> None:
    """Desactivar una tasa y verificar que ya no aparezca como activa."""
    ts = TasaCambioService()
    tasa = ts.registrar(
        fecha=date.today(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("49.50"),
        activa=True,
        db_session=session,
    )

    resultado = ts.desactivar_tasa(tasa_id=tasa.id, db_session=session)  # type: ignore[arg-type]
    assert resultado is True

    # Ya no debe estar activa.
    activa = ts.tasa_activa(db_session=session)
    assert activa is None or activa.id != tasa.id

    # Verificar directamente en la BD.
    tasa_refrescada = ts.obtener_por_fecha(fecha=date.today(), db_session=session)
    assert tasa_refrescada is not None
    assert tasa_refrescada.activa is False


# ============================================================
# TEST: test_desactivar_tasa_inexistente
# ============================================================
def test_desactivar_tasa_inexistente(session) -> None:
    ts = TasaCambioService()
    resultado = ts.desactivar_tasa(tasa_id=9999, db_session=session)
    assert resultado is False


# ============================================================
# TEST: test_obtener_desde_bcv_error
# ¿QUE PRUEBA? Que obtener_desde_bcv() maneje errores sin crashear.
# ============================================================
def test_obtener_desde_bcv_error(session) -> None:
    """obtener_desde_bcv() intenta consultar el BCV real. Si falla
    (sin internet, BCV caido, etc.), debe retornar None sin lanzar
    excepcion. Esto evita que la app se caiga por un error externo."""
    ts = TasaCambioService()
    resultado = ts.obtener_desde_bcv()
    # Puede ser None (sin conexion) o una TasaCambio (si hay conexion).
    # Solo verificamos que no lance excepcion.
    assert resultado is None or isinstance(resultado, TasaCambio)
