import gc
from collections.abc import Iterator
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox
from pytestqt.qtbot import QtBot
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import sistema_financiero.models.conexion as conexion_mod
import sistema_financiero.ui.interfaz as interfaz_mod
from sistema_financiero.core.auth_service import AuthService
from sistema_financiero.core.caja_service import CajaService
from sistema_financiero.core.producto_controller import ProductoController
from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.models import (
    Caja,
    MovimientoInventario,
    PagoVenta,
    Producto,
    ReporteDiario,
    Usuario,
    Venta,
)
from sistema_financiero.ui.dashboard_pagina import DashboardPagina
from sistema_financiero.ui.formulario_venta import FormularioVenta
from sistema_financiero.ui.interfaz import VentanaPrincipal
from sistema_financiero.ui.ventana_login import VentanaLogin
from sistema_financiero.utils import ROL_ADMINISTRADOR, ROL_VENDEDOR, hoy

pytestmark = pytest.mark.sistema


# Sustituye registrar_evento del login (el test no ensucia logs/).
def _neutralizar_auditoria_login(*_args: object, **_kwargs: object) -> None:
    """Sustituye registrar_evento del login (el test no ensucia logs/)."""
    return None


# Evita que el dashboard consulte el BCV por red (no-op).
@pytest.fixture(autouse=True)
def _sin_fetch_bcv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evita que el dashboard consulte el BCV por red (no-op)."""

    # Deja el fetch BCV inactivo para no tocar la red.
    def _iniciar_fetch_sin_red(self: DashboardPagina) -> None:
        self._bcv_fetching = False

    monkeypatch.setattr(DashboardPagina, "_iniciar_fetch_bcv", _iniciar_fetch_sin_red)


# Fuerza la recoleccion de sesiones de BD tras cada test.
@pytest.fixture(autouse=True)
def _liberar_conexiones_sqlite() -> Iterator[None]:
    """Fuerza la recoleccion de sesiones de BD tras cada test."""
    yield
    gc.collect()


# Evita modales reales cuando pytest-qt cierra VentanaPrincipal (teardown).
@pytest.fixture(autouse=True, scope="module")
def _sin_dialogos_reales_al_cerrar_ventana():
    """Evita modales reales cuando pytest-qt cierra VentanaPrincipal (teardown)."""
    with patch(
        "sistema_financiero.ui.interfaz.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        yield


# BD unica compartida por servicios y UI (parcheando AMBOS engines).
@pytest.fixture()
def bd_sistema(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """BD unica compartida por servicios y UI (parcheando AMBOS engines)."""
    motor = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(motor)

    monkeypatch.setattr(conexion_mod, "engine", motor)
    monkeypatch.setattr(interfaz_mod, "engine", motor)

    with Session(motor) as sesion:
        yield sesion


# Usuario ADMINISTRADOR real con contrasena bcrypt (no mock).
def _crear_admin(sesion: Session) -> Usuario:
    """Usuario ADMINISTRADOR real con contrasena bcrypt (no mock)."""
    admin = AuthService().crear_usuario(
        usuario="admin",
        contrasena="admin123",
        nombre_completo="Administrador",
        rol=ROL_ADMINISTRADOR,
        db_session=sesion,
    )
    assert admin.id is not None
    return admin


# Usuario VENDEDOR real con contrasena bcrypt (no mock).
def _crear_vendedor(sesion: Session) -> Usuario:
    """Usuario VENDEDOR real con contrasena bcrypt (no mock)."""
    vendedor = AuthService().crear_usuario(
        usuario="cajero",
        contrasena="cajero123",
        nombre_completo="Cajero",
        rol=ROL_VENDEDOR,
        db_session=sesion,
    )
    assert vendedor.id is not None
    return vendedor


# Registra la tasa BCV real de hoy (no es idempotente: BD limpia por test).
def _crear_tasa_bcv_hoy(sesion: Session) -> None:
    """Registra la tasa BCV real de hoy (no es idempotente: BD limpia por test)."""
    TasaCambioService().registrar(
        fecha=hoy(),
        tasa_venta=Decimal("50.00"),
        tasa_compra=Decimal("50.00"),
        activa=True,
        db_session=sesion,
    )


# Producto real por UNIDAD: 2.
def _crear_producto(sesion: Session) -> Producto:
    """Producto real por UNIDAD: 2.00 USD = 100.00 Bs. con tasa 50."""
    producto = ProductoController().crear(
        Producto(
            nombre_producto="ARROZ",
            precio_compra=Decimal("1.00"),
            precio_venta_bs=Decimal("100.00"),
            precio_venta_usd=Decimal("2.00"),
            stock_actual=Decimal("20"),
            stock_minimo=Decimal("5"),
        ),
        db_session=sesion,
    )
    assert producto.idproducto is not None
    return producto


# Abre la caja del turno con fondo cero para el admin.
def _abrir_caja(sesion: Session, admin: Usuario) -> None:
    assert admin.id is not None
    CajaService(db_session=sesion).abrir_caja(
        monto_apertura_bs=Decimal("0.00"),
        usuario_id=admin.id,
    )


class TestCicloDeSesion:
    """Login real (bcrypt) -> ventana admin -> logout -> relogin (bucle __main__)."""

    # Prueba el ciclo completo login y logout con bcrypt real.
    def test_login_logout_relogin_completo(
        self,
        bd_sistema: Session,
        qtbot: QtBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _crear_admin(bd_sistema)
        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.registrar_evento",
            _neutralizar_auditoria_login,
        )
        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.QMessageBox.warning",
            MagicMock(),
        )

        login = VentanaLogin()
        qtbot.addWidget(login)
        login.txt_usuario.setText("admin")
        login.txt_contrasena.setText("admin123")
        login._validar_login()

        assert login.usuario_actual is not None
        assert login.usuario_actual.usuario == "admin"
        assert login.result() == QDialog.DialogCode.Accepted

        ventana = VentanaPrincipal(login.usuario_actual)
        qtbot.addWidget(ventana)
        assert ventana.usuario_actual is login.usuario_actual
        assert ventana._items_menu == [
            "Dashboard",
            "Ventas",
            "Inventarios",
            "Reportes",
            "Usuarios",
        ]
        assert ventana._indice_ventas == 1

        with qtbot.waitSignal(ventana.sesion_cerrada, timeout=2000):
            ventana._cerrar_sesion()
        assert ventana._cierre_autorizado is True

        login2 = VentanaLogin()
        qtbot.addWidget(login2)
        login2.txt_usuario.setText("admin")
        login2.txt_contrasena.setText("admin123")
        login2._validar_login()

        assert login2.usuario_actual is not None
        assert login2.result() == QDialog.DialogCode.Accepted

    # Prueba que un login fallido no acepta el dialogo.
    def test_login_fallido_no_acepta(
        self,
        bd_sistema: Session,
        qtbot: QtBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _crear_admin(bd_sistema)
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.QMessageBox.warning",
            mock_warning,
        )
        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.registrar_evento",
            _neutralizar_auditoria_login,
        )

        login = VentanaLogin()
        qtbot.addWidget(login)
        login.txt_usuario.setText("admin")
        login.txt_contrasena.setText("clave-incorrecta")
        login._validar_login()

        assert login.usuario_actual is None
        assert login.result() != QDialog.DialogCode.Accepted
        mock_warning.assert_called_once()


class TestFlujoPosCompleto:
    """POS real (producto + tasa + caja de la BD) -> venta persistida real."""

    # Prueba una venta completa por el POS persistida en la BD.
    def test_venta_completa_persistida(
        self,
        bd_sistema: Session,
        qtbot: QtBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        admin = _crear_admin(bd_sistema)
        _crear_tasa_bcv_hoy(bd_sistema)
        _abrir_caja(bd_sistema, admin)
        producto = _crear_producto(bd_sistema)

        factura_stub = MagicMock()
        factura_stub.exec.return_value = QDialog.DialogCode.Accepted
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.DialogoFactura",
            MagicMock(return_value=factura_stub),
        )
        mock_info = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.information",
            mock_info,
        )

        ventana = VentanaPrincipal(admin)
        qtbot.addWidget(ventana)

        pos = FormularioVenta(
            controlador_productos=ventana.controlador_productos,
            controlador_ventas=ventana.controlador_ventas,
            controlador_tasas=ventana.controlador_tasas,
            controlador_caja=ventana.controlador_caja,
            nombre_cajero="Administrador",
        )
        qtbot.addWidget(pos)

        pos._agregar_producto_venta(int(str(producto.idproducto)))
        assert len(pos.productos_venta) == 1
        assert pos.productos_venta[0]["cantidad"] == Decimal("1.00")
        assert pos.productos_venta[0]["precio"] == Decimal("100.00")

        pos._seleccionar_metodo("tarjeta")
        assert pos.pagos
        assert pos._monto_restante_bs() <= Decimal("0.01")

        pos._finalizar_venta()
        assert pos.result() == QDialog.DialogCode.Accepted
        mock_info.assert_called_once()

        bd_sistema.expire_all()
        ventas = bd_sistema.exec(select(Venta)).all()
        assert len(ventas) == 1
        venta = ventas[0]
        assert venta.estado == "COMPLETADA"
        assert venta.numero_factura is not None
        assert venta.total_bs == Decimal("100.00")
        assert venta.total_usd == Decimal("2.00")
        assert venta.caja_id is not None

        pagos = bd_sistema.exec(select(PagoVenta)).all()
        assert len(pagos) == 1
        assert pagos[0].metodo == "tarjeta"
        assert pagos[0].monto_bs == Decimal("100.00")

        recargado = bd_sistema.get(Producto, producto.idproducto)
        assert recargado is not None
        assert recargado.stock_actual == Decimal("19")

        movimientos = bd_sistema.exec(select(MovimientoInventario)).all()
        assert len(movimientos) == 1
        assert movimientos[0].tipo == "SALIDA"
        assert movimientos[0].cantidad == Decimal("1.000")
        assert movimientos[0].stock_nuevo == Decimal("19")


class TestCierreDeCajaYReporte:
    """Cierre real de caja con arqueo -> reporte diario consolidado."""

    # Prueba el cierre de caja que genera el reporte del dia.
    def test_cierre_con_arqueo_genera_reporte(
        self,
        bd_sistema: Session,
        qtbot: QtBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        admin = _crear_admin(bd_sistema)
        _crear_tasa_bcv_hoy(bd_sistema)
        _abrir_caja(bd_sistema, admin)
        producto = _crear_producto(bd_sistema)

        factura_stub = MagicMock()
        factura_stub.exec.return_value = QDialog.DialogCode.Accepted
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.DialogoFactura",
            MagicMock(return_value=factura_stub),
        )
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.information",
            MagicMock(),
        )
        ventana = VentanaPrincipal(admin)
        qtbot.addWidget(ventana)
        pos = FormularioVenta(
            controlador_productos=ventana.controlador_productos,
            controlador_ventas=ventana.controlador_ventas,
            controlador_tasas=ventana.controlador_tasas,
            controlador_caja=ventana.controlador_caja,
            nombre_cajero="Administrador",
        )
        qtbot.addWidget(pos)
        pos._agregar_producto_venta(int(str(producto.idproducto)))
        pos._seleccionar_metodo("tarjeta")
        pos._finalizar_venta()
        assert pos.result() == QDialog.DialogCode.Accepted

        mock_info = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.information",
            mock_info,
        )
        monkeypatch.setattr(
            ventana.pagina_ventas,
            "_recoger_arqueo",
            lambda: (Decimal("100.00"), Decimal("0.00"), None),
        )
        ventana.pagina_ventas._on_cerrar_caja()

        cajas = bd_sistema.exec(select(Caja)).all()
        assert len(cajas) == 1
        assert cajas[0].estado == "CERRADA"
        assert cajas[0].sobrante_faltante_bs == Decimal("100.00")

        reportes = bd_sistema.exec(select(ReporteDiario)).all()
        assert len(reportes) == 1
        assert reportes[0].cantidad_ventas == 1
        assert reportes[0].unidades_vendidas == 1
        assert reportes[0].peso_vendido_kg == Decimal("0.000")
        assert reportes[0].total_ventas_bs == Decimal("100.00")
        mock_info.assert_called_once()


class TestVendedorSoloVentas:
    """Login real de VENDEDOR -> la app arranca en Ventas y solo muestra Ventas."""

    # Prueba que el vendedor solo ve la pagina de Ventas.
    def test_vendedor_solo_ve_ventas(
        self,
        bd_sistema: Session,
        qtbot: QtBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _crear_vendedor(bd_sistema)
        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.registrar_evento",
            _neutralizar_auditoria_login,
        )
        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.QMessageBox.warning",
            MagicMock(),
        )

        login = VentanaLogin()
        qtbot.addWidget(login)
        login.txt_usuario.setText("cajero")
        login.txt_contrasena.setText("cajero123")
        login._validar_login()

        assert login.usuario_actual is not None
        assert login.usuario_actual.rol == ROL_VENDEDOR

        ventana = VentanaPrincipal(login.usuario_actual)
        qtbot.addWidget(ventana)

        assert ventana._items_menu == ["Ventas"]
        assert ventana._indice_ventas == 0
        assert ventana.paginas.count() == 1
        assert ventana.paginas.currentWidget() is ventana.pagina_ventas
        assert ventana._timer_dashboard.isActive() is False

