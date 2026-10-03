import gc
import html
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import bcrypt
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent, QFontMetrics
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QWidget,
)
from pytestqt.qtbot import QtBot
from sqlmodel import Session

from sistema_financiero.core.caja_service import CajaService
from sistema_financiero.models.modelos import Caja, Categoria, Producto, Usuario, Venta
from sistema_financiero.ui.dashboard_pagina import (
    INTERVALO_BCV_SEGUNDOS,
    DashboardPagina,
)
from sistema_financiero.ui.dialogo_anulacion import DialogoAnulacion
from sistema_financiero.ui.dialogo_factura import (
    NOMBRE_NEGOCIO,
    DialogoFactura,
    generar_html_factura,
)
from sistema_financiero.ui.dialogo_tasa_manual import DialogoTasaManual
from sistema_financiero.ui.formulario_cambio_contrasena import FormularioCambioContrasena
from sistema_financiero.ui.formulario_producto import FormularioProducto
from sistema_financiero.ui.formulario_venta import (
    ALTO_CASILLA_PESO,
    ALTO_FILA_TICKET,
    ANCHO_COLUMNA_GRAMOS,
    ANCHO_COLUMNA_IMPORTE,
    ANCHO_COLUMNA_KG,
    ANCHO_COLUMNA_PESO_RAPIDO,
    ANCHO_COLUMNA_PRECIO,
    ANCHO_COLUMNA_PRODUCTO_TICKET,
    ANCHO_COLUMNA_QUITAR,
    ANCHO_FIJO_TICKET,
    ANCHO_MINIMO_TICKET,
    MARGEN_DER_GRUPO_PESO,
    PROPORCION_PANEL_TICKET,
    RESERVA_PANEL_TICKET,
    FormularioVenta,
)
from sistema_financiero.ui.interfaz import VentanaPrincipal
from sistema_financiero.ui.inventario_pagina import InventarioPagina
from sistema_financiero.ui.productos_pagina import ProductosPagina
from sistema_financiero.ui.usuarios_pagina import UsuariosPagina
from sistema_financiero.ui.ventana_login import VentanaLogin
from sistema_financiero.ui.ventas_pagina import VentasPagina
from sistema_financiero.ui.widgets import SpinBoxStock, TituloPagina
from sistema_financiero.utils import (
    METODO_PAGO_EFECTIVO_BS,
    METODOS_PAGO,
    MONEDA_BS,
    UNIDADES_VENTA,
    ahora,
    hoy,
)
from sistema_financiero.utils.moneda import formatear_bs, formatear_usd


# Invariante: lo que cada widget embebido necesita cabe en su celda.
def _verificar_celdas_no_desbordan(tabla: QTableWidget) -> None:
    """Invariante: lo que cada widget embebido necesita cabe en su celda."""
    vheader = tabla.verticalHeader()
    assert vheader is not None
    for fila in range(tabla.rowCount()):
        for col in range(tabla.columnCount()):
            widget = tabla.cellWidget(fila, col)
            if widget is None:
                continue
            minimo = widget.minimumSizeHint()
            ancho_min = minimo.width()
            alto_min = minimo.height()
            if widget.minimumWidth() == widget.maximumWidth():
                ancho_min = widget.minimumWidth()
            if widget.minimumHeight() == widget.maximumHeight():
                alto_min = widget.minimumHeight()
            assert ancho_min <= tabla.columnWidth(col), (fila, col)
            assert alto_min <= vheader.defaultSectionSize(), (fila, col)


# Crea un objeto Usuario simulado (sin BD) para los tests de UI.
@pytest.fixture()
def usuario_admin() -> Usuario:
    """Crea un objeto Usuario simulado (sin BD) para los tests de UI."""
    return Usuario(
        id=1,
        usuario="admin",
        contrasena="hash_falso",
        nombre_completo="Administrador",
        activo=True,
    )


# Evita que el dashboard consulte el BCV por red durante los tests de UI.
@pytest.fixture(autouse=True)
def _sin_fetch_bcv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evita que el dashboard consulte el BCV por red durante los tests de UI."""

    # Deja el fetch BCV inactivo para no tocar la red.
    def _iniciar_fetch_sin_red(self: DashboardPagina) -> None:
        self._bcv_fetching = False

    monkeypatch.setattr(DashboardPagina, "_iniciar_fetch_bcv", _iniciar_fetch_sin_red)


# Fuerza la recoleccion de sesiones de BD tras cada test de UI.
@pytest.fixture(autouse=True)
def _liberar_conexiones_sqlite() -> Iterator[None]:
    """Fuerza la recoleccion de sesiones de BD tras cada test de UI."""
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


class TestVentanaLogin:
    """Pruebas para la ventana de inicio de sesion (VentanaLogin)."""

    pytestmark = pytest.mark.unitarias

    # Verifica que VentanaLogin se crea con el titulo correcto.
    def test_crear_dialogo(self, qtbot: QtBot) -> None:
        """Verifica que VentanaLogin se crea con el titulo correcto."""
        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        assert "Iniciar Sesión" in dialogo.windowTitle()

    # Verifica que los widgets del login se crearon correctamente.
    def test_widgets_existen(self, qtbot: QtBot) -> None:
        """Verifica que los widgets del login se crearon correctamente."""
        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        assert hasattr(dialogo, "txt_usuario")
        assert hasattr(dialogo, "txt_contrasena")

        assert isinstance(dialogo.txt_usuario, QLineEdit)
        assert isinstance(dialogo.txt_contrasena, QLineEdit)

        assert dialogo.txt_contrasena.echoMode() == QLineEdit.EchoMode.Password

    # Verifica que el login rechaza campos vacios.
    def test_validacion_campos_vacios(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que el login rechaza campos vacios."""
        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.QMessageBox.warning",
            mock_warning,
        )

        btn_ingresar = dialogo.findChild(QPushButton, "")
        assert btn_ingresar is not None

        qtbot.mouseClick(btn_ingresar, Qt.MouseButton.LeftButton)

        mock_warning.assert_called_once()

    # Verifica que credenciales incorrectas muestran error.
    def test_validar_login_incorrecto(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que credenciales incorrectas muestran error."""
        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.QMessageBox.warning",
            mock_warning,
        )

        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None

        class MockContextManager:
            # Entra en el contexto del mock de sesion.
            def __enter__(self) -> MockContextManager:
                return mock_session

            # Cierra el contexto del mock de sesion.
            def __exit__(self, *args: object) -> None:
                pass

        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.obtener_sesion",
            MockContextManager,
        )

        qtbot.keyClicks(dialogo.txt_usuario, "usuario_inexistente")
        qtbot.keyClicks(dialogo.txt_contrasena, "clave_incorrecta")

        btn_ingresar = dialogo.findChild(QPushButton, "")
        qtbot.mouseClick(btn_ingresar, Qt.MouseButton.LeftButton)

        mock_warning.assert_called_once()

    # Verifica que NO existe el boton "olvide mi contrasena".
    def test_login_sin_olvide_contrasena(self, qtbot: QtBot) -> None:
        """Verifica que NO existe el boton "olvide mi contrasena"."""
        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        botones = dialogo.findChildren(QPushButton)
        nombres = [b.text().lower() for b in botones]
        assert not any("olvid" in t for t in nombres), (
            "El login no debe ofrecer recuperar la contrasena"
        )

    # Auditoria: un login fallido se registra como WARNING.
    def test_login_fallido_registra_evento(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auditoria: un login fallido se registra como WARNING."""

        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        mock_evento = MagicMock()
        mock_warning = MagicMock()
        monkeypatch.setattr("sistema_financiero.ui.ventana_login.registrar_evento", mock_evento)
        monkeypatch.setattr("sistema_financiero.ui.ventana_login.QMessageBox.warning", mock_warning)

        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None

        class MockContextManager:
            # Entra en el contexto del mock de sesion.
            def __enter__(self) -> MagicMock:
                return mock_session

            # Cierra el contexto del mock de sesion.
            def __exit__(self, *args: object) -> None:
                pass

        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.obtener_sesion",
            MockContextManager,
        )

        qtbot.keyClicks(dialogo.txt_usuario, "usuario_inexistente")
        qtbot.keyClicks(dialogo.txt_contrasena, "clave_incorrecta")

        btn_ingresar = dialogo.findChild(QPushButton, "")
        qtbot.mouseClick(btn_ingresar, Qt.MouseButton.LeftButton)

        mock_evento.assert_called_once_with(
            logging.WARNING, "Intento de login fallido para el usuario: usuario_inexistente"
        )
        mock_warning.assert_called_once()

    # Auditoria: un login exitoso se registra como INFO.
    def test_login_exitoso_registra_evento(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auditoria: un login exitoso se registra como INFO."""

        clave_correcta = "clave_segura"
        hash_valido = bcrypt.hashpw(clave_correcta.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )

        usuario = MagicMock()
        usuario.usuario = "admin"
        usuario.contrasena = hash_valido

        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        mock_evento = MagicMock()
        monkeypatch.setattr("sistema_financiero.ui.ventana_login.registrar_evento", mock_evento)

        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = usuario

        class MockContextManager:
            # Entra en el contexto del mock de sesion.
            def __enter__(self) -> MagicMock:
                return mock_session

            # Cierra el contexto del mock de sesion.
            def __exit__(self, *args: object) -> None:
                pass

        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.obtener_sesion",
            MockContextManager,
        )

        qtbot.keyClicks(dialogo.txt_usuario, "admin")
        qtbot.keyClicks(dialogo.txt_contrasena, clave_correcta)

        btn_ingresar = dialogo.findChild(QPushButton, "")
        qtbot.mouseClick(btn_ingresar, Qt.MouseButton.LeftButton)

        mock_evento.assert_called_once_with(logging.INFO, "Login exitoso del usuario: admin")
        assert dialogo.usuario_actual is usuario


class TestVentanaPrincipal:
    """Pruebas para la ventana principal (VentanaPrincipal)."""

    pytestmark = pytest.mark.sistema

    # Verifica que VentanaPrincipal se crea con el titulo correcto.
    def test_crear_ventana(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que VentanaPrincipal se crea con el titulo correcto."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        assert "Administrador" in ventana.windowTitle()

    # Verifica que la barra lateral de navegacion se creo.
    def test_barra_navegacion_existe(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que la barra lateral de navegacion se creo."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        assert hasattr(ventana, "barra_navegacion")

        assert ventana.barra_navegacion.count() == 1

        nombres = []
        for i in range(ventana.barra_navegacion.count()):
            item = ventana.barra_navegacion.item(i)
            assert item is not None, f"item({i}) es None"
            nombres.append(item.text())
        assert nombres == ["Ventas"]

    # Verifica que el QStackedWidget contiene las paginas del rol.
    def test_paginas_existen(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que el QStackedWidget contiene las paginas del rol."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        assert ventana.paginas.count() == 1
        assert ventana.paginas.currentWidget() is ventana.pagina_ventas

    # La barra superior (header) existe y muestra titulo + usuario.
    def test_cabecera_aplicacion_existe(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """La barra superior (header) existe y muestra titulo + usuario."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        assert hasattr(ventana, "cabecera_aplicacion")
        cabecera = ventana.cabecera_aplicacion
        assert cabecera.property("rol") == "cabecera_aplicacion"

        textos = [etiqueta.text() for etiqueta in cabecera.findChildren(QLabel)]
        assert "Gestor de Ventas e Inventario" in textos
        assert "Administrador" in textos

    # Cada pagina lleva un TituloPagina (tarjeta con barra #2563eb).
    def test_paginas_tienen_titulo_con_barra_lateral(
        self, qtbot: QtBot, usuario_admin: Usuario
    ) -> None:
        """Cada pagina lleva un TituloPagina (tarjeta con barra #2563eb)."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        titulos = ventana.findChildren(TituloPagina)
        assert len(titulos) == 1
        assert all(t.property("rol") == "titulo_pagina" for t in titulos)
        textos = {etiqueta.text() for t in titulos for etiqueta in t.findChildren(QLabel)}
        assert {"Ventas"} <= textos

    # Verifica que se puede cambiar de pagina usando la barra lateral.
    def test_cambiar_pagina(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que se puede cambiar de pagina usando la barra lateral."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        for i in range(ventana.barra_navegacion.count()):
            ventana.barra_navegacion.setCurrentRow(i)

            assert ventana.paginas.currentIndex() == i

    # Verifica que los controladores se crearon al iniciar VentanaPrincipal.
    def test_controladores_creados(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que los controladores se crearon al iniciar VentanaPrincipal."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        controladores = [
            ("controlador_productos", None),
            ("controlador_inventario", None),
            ("controlador_ventas", None),
            ("controlador_tasas", None),
            ("controlador_reportes", None),
            ("controlador_caja", None),
        ]

        for nombre, _clase in controladores:
            assert hasattr(ventana, nombre), f"Falta el controlador: {nombre}"

    # El vendedor no ve Dashboard: su timer de refresco nunca arranca.
    @pytest.mark.aceptacion
    def test_vendedor_timer_dashboard_inactivo(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """El vendedor no ve Dashboard: su timer de refresco nunca arranca."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        assert "Dashboard" not in ventana._items_menu
        assert ventana._timer_dashboard.isActive() is False

    # Sin Dashboard en el stack, navegar nunca refresca el dashboard.
    @pytest.mark.aceptacion
    def test_vendedor_cambiar_pagina_no_refresca_dashboard(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin Dashboard en el stack, navegar nunca refresca el dashboard."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        refrescar = MagicMock()
        monkeypatch.setattr(ventana.pagina_dashboard, "refrescar", refrescar)

        ventana._cambiar_pagina(0)

        assert ventana.paginas.currentWidget() is ventana.pagina_ventas
        refrescar.assert_not_called()


class TestTituloPagina:
    """Pruebas del widget reutilizable TituloPagina (tarjeta con barra)."""

    pytestmark = pytest.mark.unitarias

    # El titulo expone el rol del QSS y muestra el texto recibido.
    def test_titulo_pagina_rol_y_texto(self, qtbot: QtBot) -> None:
        """El titulo expone el rol del QSS y muestra el texto recibido."""
        titulo = TituloPagina("Dashboard")
        qtbot.addWidget(titulo)

        assert titulo.property("rol") == "titulo_pagina"
        textos = [etiqueta.text() for etiqueta in titulo.findChildren(QLabel)]
        assert textos == ["Dashboard"]


class TestSpinBoxStock:
    """Pruebas del widget SpinBoxStock (stock entero o decimal sin relleno)."""

    pytestmark = pytest.mark.unitarias

    # UNIDAD: enteros con punto de miles (5, 10.
    def test_modo_entero_muestra_enteros_con_miles(self, qtbot: QtBot) -> None:
        """UNIDAD: enteros con punto de miles (5, 10.000)."""
        spin = SpinBoxStock()
        qtbot.addWidget(spin)

        spin.set_modo_entero(True)
        spin.setValue(5)
        assert spin.text() == "5"
        spin.setValue(10000)
        assert spin.text() == "10.000"
        assert spin.decimals() == 0
        assert spin.singleStep() == 1

    # KILO/GRAMO: decimales sin ceros de relleno (1,5 no 1,500).
    def test_modo_decimal_quita_ceros_finales(self, qtbot: QtBot) -> None:
        """KILO/GRAMO: decimales sin ceros de relleno (1,5 no 1,500)."""
        spin = SpinBoxStock()
        qtbot.addWidget(spin)

        spin.set_modo_entero(False)
        spin.setValue(1.5)
        assert spin.text() == "1,5"
        spin.setValue(1.50)
        assert spin.text() == "1,5"
        spin.setValue(0.5)
        assert spin.text() == "0,5"
        spin.setValue(1.25)
        assert spin.text() == "1,25"
        assert spin.decimals() == 3
        assert spin.singleStep() == 0.1

    # Cantidades grandes: miles con punto y decimales sueltos (999.
    def test_modo_decimal_miles_y_grandes(self, qtbot: QtBot) -> None:
        """Cantidades grandes: miles con punto y decimales sueltos (999.999,99)."""
        spin = SpinBoxStock()
        qtbot.addWidget(spin)

        spin.set_modo_entero(False)
        spin.setValue(12345.5)
        assert spin.text() == "12.345,5"
        spin.setValue(999999.99)
        assert spin.text() == "999.999,99"


class TestFormularioProducto:
    """Pruebas para el dialogo de crear/editar productos (FormularioProducto)."""

    pytestmark = pytest.mark.unitarias

    # Verifica que FormularioProducto se abre en modo crear.
    def test_crear_dialogo_modo_crear(self, qtbot: QtBot) -> None:
        """Verifica que FormularioProducto se abre en modo crear."""
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        assert "Agregar producto" in dialogo.windowTitle()

    # Verifica que FormularioProducto se abre en modo editar.
    def test_crear_dialogo_modo_editar(self, qtbot: QtBot) -> None:
        """Verifica que FormularioProducto se abre en modo editar."""
        producto = Producto(
            nombre_producto="Arroz",
            precio_compra=Decimal("1.00"),
            precio_venta_bs=Decimal("1.50"),
            precio_venta_usd=Decimal("0.50"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("5"),
            unidad="KG",
        )
        dialogo = FormularioProducto(producto=producto)
        qtbot.addWidget(dialogo)

        assert "Editar producto" in dialogo.windowTitle()
        assert "Arroz" in dialogo.windowTitle()

    # Regresion: editar con una categoria que NO esta en el combo.
    def test_editar_categoria_fuera_del_combo_no_abre_dialogo(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regresion: editar con una categoria que NO esta en el combo."""
        producto = Producto(
            idproducto=9,
            nombre_producto="Jabon de Baño",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("50.00"),
            precio_venta_usd=Decimal("1.25"),
            stock_actual=Decimal("12"),
            stock_minimo=Decimal("2"),
            unidad="UNIDAD",
            categoria=Categoria(id=2, nombre="Aseo Personal", clave="aseo personal"),
        )
        se_abrio_dialogo = False

        # Simula el QInputDialog real y avisa de que se habria abierto.
        def _dialogo_real(*_args: object, **_kwargs: object) -> tuple[str, bool]:
            nonlocal se_abrio_dialogo
            se_abrio_dialogo = True
            return ("", False)

        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_producto.QInputDialog.getText",
            _dialogo_real,
        )
        dialogo = FormularioProducto(producto=producto)
        qtbot.addWidget(dialogo)

        assert not se_abrio_dialogo
        assert dialogo.cmb_categoria.currentText() == "Aseo Personal"

    # Verifica que los campos del formulario existen en modo crear.
    def test_campos_existen_en_modo_crear(self, qtbot: QtBot) -> None:
        """Verifica que los campos del formulario existen en modo crear."""
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        campos = [
            "txt_nombre",
            "cmb_categoria",
            "spin_precio_compra_usd",
            "lbl_equiv_compra",
            "spin_precio_venta_usd",
            "lbl_equiv_venta",
            "spin_stock_actual",
            "spin_stock_minimo",
            "cmb_unidad",
        ]
        for campo in campos:
            assert hasattr(dialogo, campo), f"Falta el campo: {campo}"

        assert not hasattr(dialogo, "spin_precio_compra")
        assert not hasattr(dialogo, "spin_precio_venta_bs")
        assert not hasattr(dialogo, "cmb_tipo_venta")

    # Verifica que los campos se precargan en modo editar.
    def test_campos_precargados_en_editar(self, qtbot: QtBot) -> None:
        """Verifica que los campos se precargan en modo editar."""
        producto = Producto(
            nombre_producto="Leche",
            categoria=Categoria(nombre="LACTEOS", clave="lacteos"),
            precio_compra=Decimal("0.80"),
            precio_venta_bs=Decimal("1.20"),
            precio_venta_usd=Decimal("0.40"),
            stock_actual=Decimal("50"),
            stock_minimo=Decimal("10"),
            unidad="KG",
        )
        dialogo = FormularioProducto(producto=producto)
        qtbot.addWidget(dialogo)

        assert dialogo.txt_nombre.text() == "Leche"
        assert dialogo.cmb_categoria.currentText() == "LACTEOS"
        assert dialogo.cmb_unidad.currentText() == "KILO"

    # Verifica que el dialogo rechaza guardar sin nombre.
    def test_validacion_nombre_vacio(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que el dialogo rechaza guardar sin nombre."""
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_producto.QMessageBox.warning",
            mock_warning,
        )

        for btn in dialogo.findChildren(QPushButton):
            if btn.text() == "Guardar":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_warning.assert_called_once()

    # Los precios en Bs NO son campos editables: texto "Equivalente".
    def test_campos_bs_son_texto_no_editables(self, qtbot: QtBot) -> None:
        """Los precios en Bs NO son campos editables: texto "Equivalente"."""
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        assert not hasattr(dialogo, "spin_precio_compra")
        assert not hasattr(dialogo, "spin_precio_venta_bs")

        assert dialogo.lbl_equiv_compra.property("rol") == "equivalente"
        assert dialogo.lbl_equiv_venta.property("rol") == "equivalente"
        assert "Equivalente: —" in dialogo.lbl_equiv_compra.text()
        assert "Equivalente: —" in dialogo.lbl_equiv_venta.text()

    # Helper: controlador de tasas mockeado con tasa activa.
    @staticmethod
    def _tasa_mock(tasa_venta: str) -> MagicMock:
        """Helper: controlador de tasas mockeado con tasa activa."""
        tasa = MagicMock()
        tasa.tasa_venta = Decimal(tasa_venta)
        tasa.fecha = "2026-09-22"
        controlador = MagicMock()
        controlador.tasa_activa.return_value = tasa
        return controlador

    # Escribir el precio de venta USD calcula el Bs con la tasa.
    def test_precio_venta_usd_calcula_bs(self, qtbot: QtBot) -> None:
        """Escribir el precio de venta USD calcula el Bs con la tasa."""
        dialogo = FormularioProducto(
            controlador_tasas=self._tasa_mock("853.50"),
        )
        qtbot.addWidget(dialogo)

        dialogo.spin_precio_venta_usd.setValue(10.0)

        assert dialogo._bs_venta == Decimal("8535.00")
        assert "8.535,00" in dialogo.lbl_equiv_venta.text()

    # Al vaciar el precio USD, el Bs vuelve a 0 (no queda el viejo).
    def test_borrar_usd_reinicia_bs_a_cero(self, qtbot: QtBot) -> None:
        """Al vaciar el precio USD, el Bs vuelve a 0 (no queda el viejo)."""
        dialogo = FormularioProducto(
            controlador_tasas=self._tasa_mock("853.50"),
        )
        qtbot.addWidget(dialogo)

        dialogo.spin_precio_venta_usd.setValue(10.0)
        assert dialogo._bs_venta > 0

        dialogo.spin_precio_venta_usd.setValue(0.0)
        assert dialogo._bs_venta == 0
        assert "Equivalente: —" in dialogo.lbl_equiv_venta.text()

    # Escribir el precio de compra USD calcula el Bs con la tasa.
    def test_precio_compra_usd_calcula_bs(self, qtbot: QtBot) -> None:
        """Escribir el precio de compra USD calcula el Bs con la tasa."""
        dialogo = FormularioProducto(
            controlador_tasas=self._tasa_mock("853.50"),
        )
        qtbot.addWidget(dialogo)

        dialogo.spin_precio_compra_usd.setValue(5.0)

        assert dialogo._bs_compra == Decimal("4267.50")
        assert "4.267,50" in dialogo.lbl_equiv_compra.text()

    # Al editar, el Bs se recalcula con la tasa de HOY y avisa si cambio.
    def test_editar_recalcula_bs_y_muestra_aviso(self, qtbot: QtBot) -> None:
        """Al editar, el Bs se recalcula con la tasa de HOY y avisa si cambio."""
        producto = Producto(
            nombre_producto="Harina",
            precio_compra=Decimal("5000.00"),
            precio_venta_bs=Decimal("8000.00"),
            precio_venta_usd=Decimal("10.00"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("5"),
            unidad="KG",
        )
        dialogo = FormularioProducto(
            producto=producto,
            controlador_tasas=self._tasa_mock("853.50"),
        )
        qtbot.addWidget(dialogo)

        assert dialogo._bs_venta == Decimal("8535.00")
        assert "8.535,00" in dialogo.lbl_equiv_venta.text()
        assert not dialogo.lbl_aviso.isHidden()
        assert "Precio anterior: 8.000,00 Bs." in dialogo.lbl_aviso.text()
        assert "853,50" in dialogo.lbl_aviso.text()

    # Si la tasa actual no cambia el Bs, el aviso queda oculto.
    def test_editar_sin_cambio_oculta_aviso(self, qtbot: QtBot) -> None:
        """Si la tasa actual no cambia el Bs, el aviso queda oculto."""
        producto = Producto(
            nombre_producto="Azucar",
            precio_compra=Decimal("1500.00"),
            precio_venta_bs=Decimal("2000.00"),
            precio_venta_usd=Decimal("10.00"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("5"),
            unidad="KG",
        )
        dialogo = FormularioProducto(
            producto=producto,
            controlador_tasas=self._tasa_mock("200.00"),
        )
        qtbot.addWidget(dialogo)

        assert dialogo.lbl_aviso.isHidden()

    # Sin tasa activa no se puede guardar un producto con precio USD.
    def test_guardar_sin_tasa_rechaza_precio_usd(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin tasa activa no se puede guardar un producto con precio USD."""
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_producto.QMessageBox.warning",
            mock_warning,
        )

        dialogo.txt_nombre.setText("Aceite")
        dialogo.spin_precio_venta_usd.setValue(3.50)
        for btn in dialogo.findChildren(QPushButton):
            if btn.text() == "Guardar":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_warning.assert_called_once()
        mensaje = str(mock_warning.call_args.args[-1])
        assert "tasa activa" in mensaje

    # El combo de unidad ofrece UNIDAD/KILO (GRAMO se elimino del menu).
    def test_cmb_unidad_tiene_las_dos_opciones(self, qtbot: QtBot) -> None:
        """El combo de unidad ofrece UNIDAD/KILO (GRAMO se elimino del menu)."""
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        opciones = [dialogo.cmb_unidad.itemText(i) for i in range(dialogo.cmb_unidad.count())]
        assert opciones == UNIDADES_VENTA
        assert opciones == ["UNIDAD", "KILO"]
        assert dialogo.cmb_unidad.currentText() == "UNIDAD"

    # Con UNIDAD (default) el stock muestra enteros sin ceros de relleno.
    def test_stock_entero_por_defecto(self, qtbot: QtBot) -> None:
        """Con UNIDAD (default) el stock muestra enteros sin ceros de relleno."""
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        assert dialogo.spin_stock_actual.decimals() == 0
        assert dialogo.spin_stock_actual.singleStep() == 1
        assert dialogo.spin_stock_actual.text() == "0"
        assert dialogo.spin_stock_minimo.text() == "5"

    # KILO habilita decimales sin ceros de relleno (kg).
    def test_stock_decimal_con_unidad_medida(self, qtbot: QtBot) -> None:
        """KILO habilita decimales sin ceros de relleno (kg)."""
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        dialogo.cmb_unidad.setCurrentText("KILO")

        assert dialogo.spin_stock_actual.decimals() == 3
        assert dialogo.spin_stock_actual.singleStep() == 0.1
        dialogo.spin_stock_actual.setValue(1.5)
        assert dialogo.spin_stock_actual.text() == "1,5"

        dialogo.spin_stock_actual.setValue(1.50)
        assert dialogo.spin_stock_actual.text() == "1,5"

    # Cantidades grandes se muestran con punto de miles y decimales sueltos.
    def test_stock_miles_y_decimales_libres(self, qtbot: QtBot) -> None:
        """Cantidades grandes se muestran con punto de miles y decimales sueltos."""
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        dialogo.cmb_unidad.setCurrentText("KILO")
        dialogo.spin_stock_actual.setValue(12345.5)
        assert dialogo.spin_stock_actual.text() == "12.345,5"

        dialogo.spin_stock_actual.setValue(999999.99)
        assert dialogo.spin_stock_actual.text() == "999.999,99"

    # La etiqueta del precio dice 'por UNIDAD/KILO' segun la unidad.
    def test_etiqueta_precio_dinamica_por_unidad(self, qtbot: QtBot) -> None:
        """La etiqueta del precio dice 'por UNIDAD/KILO' segun la unidad."""
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        assert dialogo.lbl_precio_venta.text() == "Precio Venta por UNIDAD:"
        assert dialogo.lbl_precio_compra.text() == "Precio Compra por UNIDAD:"

        dialogo.cmb_unidad.setCurrentText("KILO")
        assert dialogo.lbl_precio_venta.text() == "Precio Venta por KILO:"
        assert dialogo.lbl_precio_compra.text() == "Precio Compra por KILO:"

    # Un producto 'por gramo' abre en KILO y reescala sus precios x1000.
    def test_editar_normaliza_unidad_legada_gramo_a_kilo(self, qtbot: QtBot) -> None:
        """Un producto 'por gramo' abre en KILO y reescala sus precios x1000."""
        producto = Producto(
            nombre_producto="POLLO",
            precio_compra=Decimal("80.00"),
            precio_venta_bs=Decimal("100.00"),
            precio_venta_usd=Decimal("0.50"),
            stock_actual=Decimal("12.500"),
            stock_minimo=Decimal("2.000"),
            unidad="GRAMO",
            tipo_venta="GRAMOS",
        )
        dialogo = FormularioProducto(producto=producto)
        qtbot.addWidget(dialogo)

        assert dialogo.cmb_unidad.currentText() == "KILO"
        assert dialogo.spin_precio_venta_usd.value() == pytest.approx(500.00)
        assert dialogo._bs_venta == Decimal("100000.00")
        assert dialogo._bs_compra == Decimal("80000.00")
        assert dialogo.spin_stock_actual.value() == pytest.approx(12.5)
        assert "POR GRAMO" in dialogo.lbl_aviso.text()
        assert "1000" in dialogo.lbl_aviso.text()
        assert not dialogo.lbl_aviso.isHidden()

    # El combo precarga unidades viejas normalizadas (PAQUETE → UNIDAD).
    def test_editar_normaliza_unidad_legada(self, qtbot: QtBot) -> None:
        """El combo precarga unidades viejas normalizadas (PAQUETE → UNIDAD)."""
        producto = Producto(
            nombre_producto="Papel",
            precio_compra=Decimal("0.50"),
            precio_venta_bs=Decimal("1.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("20"),
            stock_minimo=Decimal("5"),
            unidad="PAQUETE",
        )
        dialogo = FormularioProducto(producto=producto)
        qtbot.addWidget(dialogo)

        assert dialogo.cmb_unidad.currentText() == "UNIDAD"
        assert dialogo.spin_stock_actual.decimals() == 0
        assert dialogo.spin_stock_actual.text() == "20"

    # Unidades no contempladas en el combo se agregan como opcion.
    def test_editar_con_unidad_desconocida_la_agrega(self, qtbot: QtBot) -> None:
        """Unidades no contempladas en el combo se agregan como opcion."""
        producto = Producto(
            nombre_producto="Extrano",
            precio_compra=Decimal("1.00"),
            precio_venta_bs=Decimal("2.00"),
            precio_venta_usd=Decimal("0.50"),
            stock_actual=Decimal("3"),
            stock_minimo=Decimal("1"),
            unidad="BOLSA",
        )
        dialogo = FormularioProducto(producto=producto)
        qtbot.addWidget(dialogo)

        assert dialogo.cmb_unidad.currentText() == "BOLSA"
        assert dialogo.spin_stock_actual.decimals() == 0

    # Elegir 'Nueva categoria…' pide el nombre y lo inserta en el combo.
    def test_combo_crea_nueva_categoria_con_prompt(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Elegir 'Nueva categoria…' pide el nombre y lo inserta en el combo."""
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)
        dialogo.controlador_productos = MagicMock()
        dialogo.controlador_productos.crear_categoria.return_value = Categoria(
            nombre="Higiene",
            clave="higiene",
        )

        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_producto.QInputDialog.getText",
            lambda *_args, **_kwargs: ("Higiene", True),
        )
        dialogo._gestionar_categoria(dialogo.cmb_categoria.count() - 1)
        assert dialogo.cmb_categoria.currentText() == "Higiene"

        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_producto.QInputDialog.getText",
            lambda *_args, **_kwargs: ("", False),
        )
        dialogo._gestionar_categoria(dialogo.cmb_categoria.count() - 1)
        assert dialogo.cmb_categoria.currentText() == "Higiene"


class TestDialogoTasaManual:
    pytestmark = pytest.mark.unitarias

    # Prueba que el dialogo de tasa manual tiene sus widgets.
    def test_crear_dialogo_tiene_widgets_basicos(self, qtbot: QtBot) -> None:
        dialogo = DialogoTasaManual()
        qtbot.addWidget(dialogo)
        assert dialogo.windowTitle() == "Tasa Manual"
        assert dialogo.findChildren(QLabel)[0].text() == "Tasa de cambio (Bs. por USD):"
        assert dialogo.txt_tasa.placeholderText() == "Ej: 860,50 o 860.50"
        assert dialogo.btn_fijar.text() == "Fijar tasa"
        assert dialogo.btn_fijar.property("rol") == "primario"
        assert dialogo.btn_fijar.isDefault() is True
        assert dialogo.btn_fijar.isEnabled() is False

    # Prueba que Fijar tasa solo se habilita con valor valido.
    def test_boton_se_habilita_solo_con_tasa_valida(self, qtbot: QtBot) -> None:
        dialogo = DialogoTasaManual()
        qtbot.addWidget(dialogo)
        for texto, esperado in [
            ("", False),
            ("   ", False),
            ("0", False),
            ("0,00", False),
            ("abc", False),
            ("860", True),
            ("860.50", True),
            ("860,50", True),
        ]:
            dialogo.txt_tasa.setText(texto)
            assert dialogo.btn_fijar.isEnabled() is esperado, texto

    # Prueba que aceptar guarda la tasa leida.
    def test_aceptar_guarda_la_tasa_leida(self, qtbot: QtBot) -> None:
        dialogo = DialogoTasaManual()
        qtbot.addWidget(dialogo)
        dialogo.txt_tasa.setText("860,50")
        assert dialogo.btn_fijar.isEnabled() is True
        dialogo._aceptar()
        assert dialogo.result() == QDialog.DialogCode.Accepted
        assert dialogo.tasa() == Decimal("860.50")

    # Prueba que cancelar no fija ninguna tasa.
    def test_cancelar_no_fija_tasa(self, qtbot: QtBot) -> None:
        dialogo = DialogoTasaManual()
        qtbot.addWidget(dialogo)
        dialogo.txt_tasa.setText("860")
        dialogo.reject()
        assert dialogo.result() == QDialog.DialogCode.Rejected

    # Prueba que una tasa cero muestra el error.
    def test_error_visible_con_tasa_cero(self, qtbot: QtBot) -> None:
        dialogo = DialogoTasaManual()
        qtbot.addWidget(dialogo)
        dialogo.txt_tasa.setText("0")
        assert "mayor a cero" in dialogo.lbl_error.text()
        dialogo.txt_tasa.setText("860")
        assert dialogo.lbl_error.text() == ""


class TestFormularioVenta:
    """Pruebas para el POS de nueva venta (FormularioVenta)."""

    pytestmark = pytest.mark.integracion

    # Evita abrir la factura real tras cobrar en los tests del POS.
    @pytest.fixture(autouse=True)
    def _stub_factura(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Evita abrir la factura real tras cobrar en los tests del POS."""
        factura_stub = MagicMock()
        factura_stub.exec.return_value = QDialog.DialogCode.Accepted
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.DialogoFactura",
            MagicMock(return_value=factura_stub),
        )
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.a_local",
            lambda _fecha_utc: datetime.now(UTC),
        )

    # Helper: inyecta controladores mockeados y agrega un producto al ticket.
    def _agregar_producto_al_ticket(
        self,
        dialogo: FormularioVenta,
        producto: Producto,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Helper: inyecta controladores mockeados y agrega un producto al ticket."""
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )
        dialogo.controlador_productos = MagicMock()
        dialogo.controlador_productos.obtener_por_id.return_value = producto
        dialogo.controlador_ventas = MagicMock()
        dialogo._agregar_producto_venta(int(str(producto.idproducto)))

    # Helper: producto por PESO con stock 10 (se agrega por defecto 0.
    @staticmethod
    def _producto_peso() -> Producto:
        """Helper: producto por PESO con stock 10 (se agrega por defecto 0.100)."""
        return Producto(
            idproducto=1,
            nombre_producto="Carne",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )

    # Verifica que FormularioVenta se crea con el titulo correcto.
    def test_crear_dialogo(self, qtbot: QtBot) -> None:
        """Verifica que FormularioVenta se crea con el titulo correcto."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        assert "Nueva Venta" in dialogo.windowTitle()

    # Verifica que los widgets del POS existen.
    def test_widgets_principales_existen(self, qtbot: QtBot) -> None:
        """Verifica que los widgets del POS existen."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        assert hasattr(dialogo, "campo_busqueda")
        assert hasattr(dialogo, "tabla_productos_catalogo")

        assert hasattr(dialogo, "tabla_productos_venta")
        assert hasattr(dialogo, "lbl_total")
        assert hasattr(dialogo, "lbl_total_usd")

        assert hasattr(dialogo, "tabla_pagos")
        assert hasattr(dialogo, "lbl_cubierto")
        assert hasattr(dialogo, "lbl_restante")
        assert len(dialogo._botones_metodo) == 6
        assert hasattr(dialogo, "fila_recibido")
        assert hasattr(dialogo, "spin_recibido")
        assert hasattr(dialogo, "lbl_recibido")
        assert hasattr(dialogo, "lbl_estado_recibido")
        assert hasattr(dialogo, "btn_registrar_recibido")
        assert hasattr(dialogo, "panel_mixto")
        assert hasattr(dialogo, "spin_monto_mixto")
        assert hasattr(dialogo, "campo_ref_mixto")
        assert hasattr(dialogo, "lbl_info_mixto")
        assert hasattr(dialogo, "btn_agregar_mixto")
        assert hasattr(dialogo, "btn_pago_mixto")
        assert isinstance(dialogo.fila_recibido, QFrame)
        assert isinstance(dialogo.panel_mixto, QFrame)
        assert len(dialogo._botones_mixto) == 6

        assert hasattr(dialogo, "btn_limpiar_ticket")
        assert hasattr(dialogo, "btn_cobrar")

    # Verifica que el boton 'COBRAR' esta en el dialogo.
    def test_boton_cobrar_existe(self, qtbot: QtBot) -> None:
        """Verifica que el boton 'COBRAR' esta en el dialogo."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        botones = dialogo.findChildren(QPushButton)
        btn_cobrar = [b for b in botones if b.text() == "COBRAR"]
        assert len(btn_cobrar) > 0

    # COBRAR y LIMPIAR TICKET comparten su fila 40/60 (prioridad a COBRAR).
    def test_cobrar_y_limpiar_se_reparten_40_60(self, qtbot: QtBot) -> None:
        """COBRAR y LIMPIAR TICKET comparten su fila 40/60 (prioridad a COBRAR)."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        assert dialogo.btn_cobrar.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
        politica_limpiar = dialogo.btn_limpiar_ticket.sizePolicy().horizontalPolicy()
        assert politica_limpiar == QSizePolicy.Policy.Expanding

        fila = next(
            h for h in dialogo.findChildren(QHBoxLayout) if h.indexOf(dialogo.btn_cobrar) >= 0
        )
        assert fila.stretch(fila.indexOf(dialogo.btn_limpiar_ticket)) == 2
        assert fila.stretch(fila.indexOf(dialogo.btn_cobrar)) == 3

    # COBRAR sin productos: boton deshabilitado y handler con red de seguridad.
    def test_venta_vacia_muestra_error(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """COBRAR sin productos: boton deshabilitado y handler con red de seguridad."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        assert dialogo.btn_cobrar.isEnabled() is False

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        dialogo._finalizar_venta()

        mock_warning.assert_called_once()

    # Verifica la visibilidad progresiva de la seccion de pago.
    def test_pago_oculto_hasta_agregar_producto(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica la visibilidad progresiva de la seccion de pago."""
        producto = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            tipo_venta="UNIDAD",
            precio_compra=Decimal("1.00"),
            precio_venta_bs=Decimal("10.00"),
            precio_venta_usd=Decimal("0.20"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
            unidad="KG",
        )

        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        assert dialogo.productos_venta == []
        assert dialogo.grupo_pago.isHidden()

        self._agregar_producto_al_ticket(dialogo, producto, monkeypatch)
        assert len(dialogo.productos_venta) == 1
        assert not dialogo.grupo_pago.isHidden()

        dialogo._eliminar_producto_venta(0)
        assert dialogo.productos_venta == []
        assert dialogo.grupo_pago.isHidden()

    # Verifica la cantidad por defecto al hacer clic en el catalogo.
    def test_agregar_unidad_y_peso_por_defecto(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica la cantidad por defecto al hacer clic en el catalogo."""
        producto_unidad = Producto(
            idproducto=1,
            nombre_producto="Aceite",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("10.00"),
            precio_venta_usd=Decimal("0.20"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        producto_peso = Producto(
            idproducto=2,
            nombre_producto="Carne",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        dialogo.controlador_productos = MagicMock()
        dialogo.controlador_ventas = MagicMock()

        dialogo.controlador_productos.obtener_por_id.return_value = producto_unidad
        dialogo._agregar_producto_venta(1)
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("1.00")

        dialogo.controlador_productos.obtener_por_id.return_value = producto_peso
        dialogo._agregar_producto_venta(2)
        assert dialogo.productos_venta[1]["cantidad"] == Decimal("1.000")

    # Un producto por peso entra con el peso del boton rapido pulsado.
    def test_agregar_peso_elige_el_peso_inicial(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un producto por peso entra con el peso del boton rapido pulsado."""
        producto_peso = Producto(
            idproducto=3,
            nombre_producto="Carne",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        dialogo.controlador_productos = MagicMock()
        dialogo.controlador_ventas = MagicMock()
        dialogo.controlador_productos.obtener_por_id.return_value = producto_peso

        dialogo._agregar_producto_venta(3, peso=Decimal("0.500"))
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("0.500")

    # El catalogo PESO trae UN (+) azul; los 4 rapidos viven en la fila.
    def test_un_solo_mas_en_catalogo_agrega_1_kg_y_los_rapidos_viven_en_la_fila(
        self, qtbot: QtBot
    ) -> None:
        """El catalogo PESO trae UN (+) azul; los 4 rapidos viven en la fila."""
        producto_peso = Producto(
            idproducto=3,
            nombre_producto="Carne",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = self._pos_con_catalogo(qtbot, producto_peso)
        assert dialogo.tabla_productos_catalogo.rowCount() == 1

        celda = dialogo.tabla_productos_catalogo.cellWidget(0, 4)
        assert isinstance(celda, QPushButton)
        assert celda.text() == "+"
        assert celda.property("rol") == "agregar_catalogo"
        assert celda.toolTip().startswith("Agregar 1 Kg de Carne al ticket.")

        qtbot.mouseClick(celda, Qt.MouseButton.LeftButton)
        assert len(dialogo.productos_venta) == 1
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("1.000")

        celda_fila = dialogo.tabla_productos_venta.cellWidget(0, 5)
        assert isinstance(celda_fila, QWidget)
        botones = celda_fila.findChildren(QPushButton)
        assert len(botones) == 4
        assert [b.text() for b in botones] == ["1kg", "1/2", "1/4", "100g"]
        assert [b.toolTip() for b in botones] == [
            "Sumar 1 Kg a Carne",
            "Sumar 1/2 Kg (500 g) a Carne",
            "Sumar 1/4 Kg (250 g) a Carne",
            "Sumar 100 g a Carne",
        ]
        for boton in botones:
            assert boton.property("rol") == "agregar_catalogo_peso"
        for boton in botones:
            ancho_texto = QFontMetrics(boton.font()).horizontalAdvance(boton.text())
            assert ancho_texto <= boton.width() - 6, boton.text()

        qtbot.mouseClick(botones[2], Qt.MouseButton.LeftButton)
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("1.250")

    # En el ticket los botones suman al peso de ESA linea (no crean otra).
    def test_peso_rapido_de_la_fila_suma_a_la_linea(self, qtbot: QtBot) -> None:
        """En el ticket los botones suman al peso de ESA linea (no crean otra)."""
        producto_peso = Producto(
            idproducto=3,
            nombre_producto="Carne",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        dialogo.controlador_productos = MagicMock()
        dialogo.controlador_productos.obtener_por_id.return_value = producto_peso
        dialogo.controlador_ventas = MagicMock()
        dialogo._agregar_producto_venta(3, peso=Decimal("0.500"))
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("0.500")

        dialogo._sumar_peso_rapido(0, Decimal("0.100"))
        assert len(dialogo.productos_venta) == 1
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("0.600")
        dialogo._sumar_peso_rapido(0, Decimal("0.100"))
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("0.700")

    # El 2x2 de botones rapidos deja un hueco antes del ✕ de la fila.
    def test_el_grupo_rapido_esta_separado_del_boton_quitar(self, qtbot: QtBot) -> None:
        """El 2x2 de botones rapidos deja un hueco antes del ✕ de la fila."""
        producto_peso = Producto(
            idproducto=3,
            nombre_producto="Carne",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = self._pos_con_catalogo(qtbot, producto_peso)
        dialogo._agregar_producto_venta(3)
        celda_fila = dialogo.tabla_productos_venta.cellWidget(0, 5)
        assert isinstance(celda_fila, QWidget)
        grid = celda_fila.layout()
        assert isinstance(grid, QGridLayout)
        assert grid.contentsMargins().right() >= MARGEN_DER_GRUPO_PESO

    # La fila del ticket sobra para el 2x2 (antes no cabia en 36px).
    def test_el_alto_de_la_fila_alberga_el_grupo_rapido(self, qtbot: QtBot) -> None:
        """La fila del ticket sobra para el 2x2 (antes no cabia en 36px)."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        contenedor = dialogo._crear_botones_peso_rapido_fila("Carne", 0)
        grid = contenedor.layout()
        assert isinstance(grid, QGridLayout)
        assert grid.minimumSize().height() <= ALTO_FILA_TICKET

    # Invariante: ningun widget embebido se sale de su celda.
    def test_ninguna_celda_desborda_su_contenedor(self, qtbot: QtBot) -> None:
        """Invariante: ningun widget embebido se sale de su celda."""
        producto_peso = Producto(
            idproducto=1,
            nombre_producto="Arroz a granel",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("10.00"),
            precio_venta_usd=Decimal("0.20"),
            stock_actual=Decimal("100"),
            stock_minimo=Decimal("1"),
        )
        producto_unidad = Producto(
            idproducto=2,
            nombre_producto="Aceite",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("8.00"),
            precio_venta_usd=Decimal("0.16"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        dialogo.controlador_productos = MagicMock()
        dialogo.controlador_productos.listar_todos.return_value = [
            producto_peso,
            producto_unidad,
        ]
        dialogo.controlador_productos.obtener_por_id.side_effect = [
            producto_peso,
            producto_unidad,
        ]
        dialogo.controlador_productos.obtener_categorias.return_value = []
        dialogo.controlador_ventas = MagicMock()
        dialogo._cargar_catalogo()
        dialogo._aplicar_filtro()

        catalogo = dialogo.tabla_productos_catalogo
        assert catalogo.rowCount() == 2
        _verificar_celdas_no_desbordan(catalogo)

        dialogo._agregar_producto_venta(1)
        dialogo._agregar_producto_venta(2)
        _verificar_celdas_no_desbordan(dialogo.tabla_productos_venta)

    # Verifica que la busqueda y la categoria filtran la lista del catalogo.
    def test_catalogo_busca_y_filtra_por_categoria(self, qtbot: QtBot) -> None:
        """Verifica que la busqueda y la categoria filtran la lista del catalogo."""
        producto_arroz = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            categoria=Categoria(nombre="ALIMENTOS", clave="alimentos"),
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("10.00"),
            precio_venta_usd=Decimal("0.20"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        producto_leche = Producto(
            idproducto=2,
            nombre_producto="Leche",
            categoria=Categoria(nombre="LACTEOS", clave="lacteos"),
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("15.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )

        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        dialogo.controlador_productos = MagicMock()
        dialogo.controlador_productos.listar_todos.return_value = [producto_arroz, producto_leche]
        dialogo.controlador_productos.obtener_categorias.return_value = ["ALIMENTOS", "LACTEOS"]

        dialogo._cargar_catalogo()

        assert dialogo.tabla_productos_catalogo.rowCount() == 2

        dialogo.campo_busqueda.setText("arroz")
        assert dialogo.tabla_productos_catalogo.rowCount() == 1

        dialogo.campo_busqueda.setText("")
        dialogo._seleccionar_categoria("LACTEOS")
        assert dialogo.tabla_productos_catalogo.rowCount() == 1

        dialogo._seleccionar_categoria("Todos")
        assert dialogo.tabla_productos_catalogo.rowCount() == 2

    # El filtro de categorias del catalogo es un desplegable (QComboBox).
    def test_filtro_categorias_es_desplegable(self, qtbot: QtBot) -> None:
        """El filtro de categorias del catalogo es un desplegable (QComboBox)."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        dialogo.controlador_productos = MagicMock()
        dialogo.controlador_productos.listar_todos.return_value = []
        dialogo.controlador_productos.obtener_categorias.return_value = ["ALIMENTOS", "LACTEOS"]

        dialogo._cargar_catalogo()

        combo = dialogo.cmb_categoria_filtro
        assert isinstance(combo, QComboBox)
        etiquetas = [combo.itemText(i) for i in range(combo.count())]
        assert etiquetas == ["Todos", "ALIMENTOS", "LACTEOS"]
        assert combo.currentText() == "Todos"

    # Helper: POS con el catalogo cargado a partir de un unico producto.
    def _pos_con_catalogo(self, qtbot: QtBot, producto: Producto) -> FormularioVenta:
        """Helper: POS con el catalogo cargado a partir de un unico producto."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        dialogo.controlador_productos = MagicMock()
        dialogo.controlador_productos.listar_todos.return_value = [producto]
        dialogo.controlador_productos.obtener_por_id.return_value = producto
        dialogo.controlador_productos.obtener_categorias.return_value = []
        dialogo.controlador_ventas = MagicMock()
        dialogo._cargar_catalogo()
        return dialogo

    # El catalogo es una QTableWidget de 5 columnas (no un grid).
    def test_catalogo_es_lista_de_5_columnas(self, qtbot: QtBot) -> None:
        """El catalogo es una QTableWidget de 5 columnas (no un grid)."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        tabla = dialogo.tabla_productos_catalogo
        assert isinstance(tabla, QTableWidget)
        assert tabla.columnCount() == 5

    # Doble clic sobre una fila del catalogo agrega el producto al ticket.
    def test_doble_clic_en_lista_agrega_producto(self, qtbot: QtBot) -> None:
        """Doble clic sobre una fila del catalogo agrega el producto al ticket."""
        producto = Producto(
            idproducto=7,
            nombre_producto="Harina",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("5.00"),
            precio_venta_usd=Decimal("0.10"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = self._pos_con_catalogo(qtbot, producto)
        assert dialogo.tabla_productos_catalogo.rowCount() == 1

        item = dialogo.tabla_productos_catalogo.item(0, 0)
        assert item is not None
        dialogo._on_catalogo_doble_clic(item)
        assert len(dialogo.productos_venta) == 1
        assert dialogo.productos_venta[0]["idproducto"] == 7

    # Enter sobre la lista agrega el producto de la fila seleccionada.
    def test_enter_agrega_fila_seleccionada(self, qtbot: QtBot) -> None:
        """Enter sobre la lista agrega el producto de la fila seleccionada."""
        producto = Producto(
            idproducto=8,
            nombre_producto="Azucar",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("6.00"),
            precio_venta_usd=Decimal("0.12"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = self._pos_con_catalogo(qtbot, producto)

        dialogo.tabla_productos_catalogo.setCurrentCell(0, 0)
        dialogo._agregar_fila_activa()
        assert len(dialogo.productos_venta) == 1

    # El ticket tiene 7 columnas y cada fila un boton ✕ en la ultima.
    def test_ticket_tiene_columna_acciones_con_boton_quitar(self, qtbot: QtBot) -> None:
        """El ticket tiene 7 columnas y cada fila un boton ✕ en la ultima."""
        producto = Producto(
            idproducto=20,
            nombre_producto="Harina",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("80.00"),
            precio_venta_usd=Decimal("2.00"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = self._pos_con_catalogo(qtbot, producto)

        tabla = dialogo.tabla_productos_venta
        assert tabla.columnCount() == 7
        cabeceras = []
        for c in range(7):
            item_cabecera = tabla.horizontalHeaderItem(c)
            assert item_cabecera is not None
            cabeceras.append(item_cabecera.text())
        assert cabeceras == [
            "Producto",
            "Cant.",
            "g",
            "P.U.",
            "Importe",
            "+ Peso",
            "✕",
        ]
        assert len(dialogo.productos_venta) == 0

        item = dialogo.tabla_productos_catalogo.item(0, 0)
        assert item is not None
        dialogo._on_catalogo_doble_clic(item)
        assert len(dialogo.productos_venta) == 1

        assert tabla.isColumnHidden(2)
        assert tabla.isColumnHidden(5)
        assert not tabla.isColumnHidden(1)
        assert dialogo._spin_peso_de(0, "g") is None

        boton = tabla.cellWidget(0, 6)
        assert isinstance(boton, QPushButton)
        assert boton.text() == "✕"
        celda_nombre = tabla.item(0, 0)
        assert celda_nombre is not None
        assert celda_nombre.toolTip() == "Harina"

    # La columna Producto del ticket tiene ancho controlado (no absorbe el sobrante).
    def test_columna_producto_del_ticket_tiene_ancho_controlado(self, qtbot: QtBot) -> None:
        """La columna Producto del ticket tiene ancho controlado (no absorbe el sobrante)."""
        producto = Producto(
            idproducto=21,
            nombre_producto="Harina",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("80.00"),
            precio_venta_usd=Decimal("2.00"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = self._pos_con_catalogo(qtbot, producto)

        tabla = dialogo.tabla_productos_venta
        header = tabla.horizontalHeader()
        assert header is not None
        assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
        assert tabla.columnWidth(0) == ANCHO_COLUMNA_PRODUCTO_TICKET

        # Al no absorber el sobrante, la columna conserva su ancho al agregar lineas.
        item = dialogo.tabla_productos_catalogo.item(0, 0)
        assert item is not None
        dialogo._on_catalogo_doble_clic(item)
        assert tabla.columnWidth(0) == ANCHO_COLUMNA_PRODUCTO_TICKET

    # A 1024x680 el ticket entra COMPLETO: sin scrollbar horizontal.
    def test_ticket_no_necesita_scroll_horizontal_a_1024(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A 1024x680 el ticket entra COMPLETO: sin scrollbar horizontal."""
        producto = Producto(
            idproducto=22,
            nombre_producto="Harina de trigo",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("80.00"),
            precio_venta_usd=Decimal("2.00"),
            stock_actual=Decimal("50"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto, monkeypatch)

        dialogo.resize(1024, 680)
        dialogo._repartir_paneles()
        dialogo._repartir_paneles()
        tamanos = dialogo.splitter_paneles.sizes()
        assert sum(tamanos) <= dialogo.splitter_paneles.width(), tamanos

        ancho_fijo = (
            ANCHO_COLUMNA_KG
            + ANCHO_COLUMNA_GRAMOS
            + ANCHO_COLUMNA_PRECIO
            + ANCHO_COLUMNA_IMPORTE
            + ANCHO_COLUMNA_PESO_RAPIDO
            + ANCHO_COLUMNA_QUITAR
        )
        assert ancho_fijo == 511
        assert ancho_fijo == ANCHO_FIJO_TICKET
        # El minimo del panel cubre las columnas + el nombre + el aire de reserva.
        esperado_minimo = ancho_fijo + ANCHO_COLUMNA_PRODUCTO_TICKET + RESERVA_PANEL_TICKET
        assert esperado_minimo == ANCHO_MINIMO_TICKET
        assert ancho_fijo + ANCHO_COLUMNA_PRODUCTO_TICKET < ANCHO_MINIMO_TICKET

        panel_ticket = dialogo.splitter_paneles.widget(1)
        panel_catalogo = dialogo.splitter_paneles.widget(0)
        assert panel_ticket is not None
        assert panel_catalogo is not None
        assert panel_ticket.minimumWidth() == ANCHO_MINIMO_TICKET
        assert panel_catalogo.minimumSizeHint().width() < ANCHO_MINIMO_TICKET
        assert tamanos[1] >= min(ANCHO_MINIMO_TICKET, ancho_fijo)

    # El splitter reparte 40/60 y el ticket gana ancho al expandir la ventana.
    def test_splitter_reparte_40_60_con_prioridad_al_ticket(self, qtbot: QtBot) -> None:
        """El splitter reparte 40/60 y el ticket gana ancho al expandir la ventana."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        assert PROPORCION_PANEL_TICKET == 0.60

        # Headless (sin show) la geometria del splitter no se finaliza: solo se
        # comprueba que el ticket recibe mas ancho que el catalogo.
        tamanos = dialogo.splitter_paneles.sizes()
        assert tamanos[1] > tamanos[0]

    # El ✕ quita SOLO esa linea del ticket y el total vuelve a cero.
    def test_boton_quitar_elimina_la_fila_y_recalcula_total(self, qtbot: QtBot) -> None:
        """El ✕ quita SOLO esa linea del ticket y el total vuelve a cero."""
        producto = Producto(
            idproducto=21,
            nombre_producto="Azucar",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("6.00"),
            precio_venta_usd=Decimal("0.15"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = self._pos_con_catalogo(qtbot, producto)

        for _ in range(2):
            item = dialogo.tabla_productos_catalogo.item(0, 0)
            assert item is not None
            dialogo._on_catalogo_doble_clic(item)
        assert len(dialogo.productos_venta) == 2
        assert dialogo.lbl_total.text() != ""

        boton = dialogo.tabla_productos_venta.cellWidget(1, 6)
        assert isinstance(boton, QPushButton)
        boton.click()
        assert len(dialogo.productos_venta) == 1

        boton_restante = dialogo.tabla_productos_venta.cellWidget(0, 6)
        assert isinstance(boton_restante, QPushButton)
        boton_restante.click()
        assert dialogo.productos_venta == []

    # El boton (+) de la fila agrega el producto al ticket.
    def test_boton_mas_de_la_fila_agrega_producto(self, qtbot: QtBot) -> None:
        """El boton (+) de la fila agrega el producto al ticket."""
        producto = Producto(
            idproducto=9,
            nombre_producto="Sal",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("3.00"),
            precio_venta_usd=Decimal("0.06"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = self._pos_con_catalogo(qtbot, producto)

        boton = dialogo.tabla_productos_catalogo.cellWidget(0, 4)
        assert isinstance(boton, QPushButton)
        assert boton.text() == "+"
        boton.click()
        assert len(dialogo.productos_venta) == 1

    # TODOS los tipos traen un solo (+) azul; los rapidos viven en la fila.
    def test_boton_mas_por_tipo_venta(self, qtbot: QtBot) -> None:
        """TODOS los tipos traen un solo (+) azul; los rapidos viven en la fila."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        unidad = Producto(
            idproducto=1,
            nombre_producto="Aceite",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("10.00"),
            precio_venta_usd=Decimal("0.20"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        peso = Producto(
            idproducto=2,
            nombre_producto="Carne",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        gramo_legacy = Producto(
            idproducto=3,
            nombre_producto="Canela",
            tipo_venta="GRAMOS",
            precio_venta_bs=Decimal("5.00"),
            precio_venta_usd=Decimal("0.10"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )

        btn_unidad = dialogo._crear_boton_agregar(unidad)
        assert isinstance(btn_unidad, QPushButton)
        assert btn_unidad.text() == "+"
        assert btn_unidad.property("rol") == "agregar_catalogo"

        btn_peso = dialogo._crear_boton_agregar(peso)
        assert isinstance(btn_peso, QPushButton)
        assert btn_peso.text() == "+"
        assert btn_peso.property("rol") == "agregar_catalogo"
        assert btn_peso.toolTip() == (
            "Agregar 1 Kg de Carne al ticket. Ajusta el peso con los botones rapidos de la fila."
        )

        btn_legacy = dialogo._crear_boton_agregar(gramo_legacy)
        assert isinstance(btn_legacy, QPushButton)
        assert btn_legacy.text() == "+"
        assert btn_legacy.property("rol") == "agregar_catalogo"
        assert "Ajusta el peso con los botones rapidos de la fila" in btn_legacy.toolTip()

    # La fila muestra USD, Bs calculado con la tasa y stock formateado.
    def test_fila_catalogo_muestra_usd_bs_y_stock(self, qtbot: QtBot) -> None:
        """La fila muestra USD, Bs calculado con la tasa y stock formateado."""
        producto = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("100.00"),
            precio_venta_usd=Decimal("2.00"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        tasa_mock = MagicMock()
        tasa_mock.tasa_venta = Decimal("40.00")
        dialogo._tasa = tasa_mock
        dialogo.controlador_productos = MagicMock()
        dialogo.controlador_productos.listar_todos.return_value = [producto]
        dialogo.controlador_productos.obtener_categorias.return_value = []
        dialogo.controlador_productos.obtener_por_id.return_value = producto
        dialogo.controlador_ventas = MagicMock()
        dialogo._cargar_catalogo()

        tabla = dialogo.tabla_productos_catalogo
        celda_nombre = tabla.item(0, 0)
        celda_usd = tabla.item(0, 1)
        celda_bs = tabla.item(0, 2)
        celda_stock = tabla.item(0, 3)
        assert celda_nombre is not None
        assert celda_usd is not None
        assert celda_bs is not None
        assert celda_stock is not None
        assert celda_nombre.text() == "Arroz"
        assert celda_usd.text() == "2.00"
        assert celda_usd.toolTip() == "Precio en dolares: 2.00 $"
        assert celda_bs.text() == "80,00"
        assert celda_bs.toolTip() == "Precio en bolivares: 80,00 Bs."
        assert celda_stock.text() == "10"

    # Verifica que editar Cant/Peso en el ticket recalcula el total.
    def test_editar_peso_recalcula_total(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica que editar Cant/Peso en el ticket recalcula el total."""
        producto_peso = Producto(
            idproducto=1,
            nombre_producto="Carne",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto_peso, monkeypatch)

        assert dialogo.total_bs == Decimal("12.00")

        spin_kg = dialogo._spin_peso_de(0, "kg")
        spin_g = dialogo._spin_peso_de(0, "g")
        assert spin_kg is not None
        assert spin_g is not None
        spin_g.setValue(500)

        assert dialogo.productos_venta[0]["cantidad"] == Decimal("1.500")
        assert dialogo.total_bs == Decimal("18.00")
        assert dialogo.tabla_productos_venta.item(0, 4) is not None
        assert dialogo.tabla_productos_venta.item(0, 4).text() == "18,00"  # type: ignore[union-attr]

    # REGRESION: tocar la casilla de g NO puede leerla como kilos.
    def test_tocar_gramos_no_toma_esos_gramos_como_kilos(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REGRESION: tocar la casilla de g NO puede leerla como kilos."""
        producto_peso = self._producto_peso()
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto_peso, monkeypatch)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        spin_g = dialogo._spin_peso_de(0, "g")
        assert spin_g is not None
        spin_g.setValue(500)

        assert dialogo.productos_venta[0]["cantidad"] == Decimal("1.500")
        assert dialogo.total_bs == Decimal("18.00")
        mock_warning.assert_not_called()

        spin_g = dialogo._spin_peso_de(0, "g")
        spin_kg = dialogo._spin_peso_de(0, "kg")
        assert spin_kg is not None
        assert spin_g is not None
        spin_kg.setValue(0)
        spin_g = dialogo._spin_peso_de(0, "g")
        assert spin_g is not None
        spin_g.setValue(999)
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("0.999")
        mock_warning.assert_not_called()

    # Kg acepta decimales ("0.
    def test_casillas_de_peso_kg_decimal_y_g_enteros_con_limite(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Kg acepta decimales ("0.5" = 500 g); g es entero; tope 999 ambos."""
        producto_peso = Producto(
            idproducto=1,
            nombre_producto="Arroz a granel",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("10.00"),
            precio_venta_usd=Decimal("0.20"),
            stock_actual=Decimal("2000"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto_peso, monkeypatch)

        spin_kg = dialogo._spin_peso_de(0, "kg")
        spin_g = dialogo._spin_peso_de(0, "g")
        assert spin_kg is not None
        assert spin_g is not None
        assert spin_kg.decimals() == 3
        assert spin_kg.singleStep() == 0.1
        assert spin_g.decimals() == 0
        assert spin_g.singleStep() == 50
        for spin in (spin_kg, spin_g):
            assert spin.minimum() == 0
            assert spin.maximum() == 999
            assert spin.property("rol") == "casilla_peso"
            assert spin.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
            assert spin.minimumHeight() == ALTO_CASILLA_PESO
            assert spin.maximumHeight() == ALTO_CASILLA_PESO

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        spin_kg.setValue(999)
        spin_kg = dialogo._spin_peso_de(0, "kg")
        spin_g = dialogo._spin_peso_de(0, "g")
        assert spin_kg is not None
        assert spin_g is not None
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("999.000")

        spin_g.setValue(999)
        spin_kg_final = dialogo._spin_peso_de(0, "kg")
        spin_g_final = dialogo._spin_peso_de(0, "g")
        assert spin_kg_final is not None
        assert spin_g_final is not None
        assert spin_kg_final.value() == 999
        assert spin_g_final.value() == 999
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("999.999")
        mock_warning.assert_not_called()

        assert "999 kg y 999 g" in spin_kg_final.toolTip()

    # Escribir 0.
    def test_kg_con_decimales_normaliza_a_gramos_al_refrescar(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Escribir 0.5 en Kg deja la linea en Kg 0 · g 500 (normalizado)."""
        producto_peso = Producto(
            idproducto=1,
            nombre_producto="Carne",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto_peso, monkeypatch)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        spin_kg = dialogo._spin_peso_de(0, "kg")
        assert spin_kg is not None
        spin_kg.setValue(0.5)

        assert dialogo.productos_venta[0]["cantidad"] == Decimal("0.500")
        mock_warning.assert_not_called()

        spin_kg = dialogo._spin_peso_de(0, "kg")
        spin_g = dialogo._spin_peso_de(0, "g")
        assert spin_kg is not None
        assert spin_g is not None
        assert spin_kg.value() == 0
        assert spin_g.value() == 500
        assert dialogo.total_bs == Decimal("6.00")

    # UNIDAD: UNA casilla "Cant.
    def test_linea_unidad_tiene_casilla_cant_entera_y_editable(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UNIDAD: UNA casilla "Cant." entera; editar a 2 piezas duplica."""
        producto_unidad = Producto(
            idproducto=10,
            nombre_producto="Arroz",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("5.00"),
            precio_venta_usd=Decimal("0.10"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto_unidad, monkeypatch)

        tabla = dialogo.tabla_productos_venta
        assert not tabla.isColumnHidden(1)
        assert tabla.isColumnHidden(2)
        assert tabla.isColumnHidden(5)
        item_cabecera = tabla.horizontalHeaderItem(1)
        assert item_cabecera is not None
        assert item_cabecera.text() == "Cant."

        spin_cant = dialogo._spin_peso_de(0, "kg")
        assert spin_cant is not None
        assert spin_cant.decimals() == 0
        assert spin_cant.maximum() == 999
        assert dialogo._spin_peso_de(0, "g") is None
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("1.000")

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )
        spin_cant.setValue(2)
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("2.000")
        assert dialogo.productos_venta[0]["subtotal"] == Decimal("10.00")
        assert dialogo.total_bs == Decimal("10.00")
        mock_warning.assert_not_called()

        spin_cant = dialogo._spin_peso_de(0, "kg")
        assert spin_cant is not None
        assert "2 und." in spin_cant.toolTip()

    # Pedir mas piezas que el stock avisa y revierte la casilla entera.
    def test_linea_unidad_cantidad_mayor_al_stock_revierte(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pedir mas piezas que el stock avisa y revierte la casilla entera."""
        producto_unidad = Producto(
            idproducto=10,
            nombre_producto="Arroz",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("5.00"),
            precio_venta_usd=Decimal("0.10"),
            stock_actual=Decimal("3"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto_unidad, monkeypatch)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        spin_cant = dialogo._spin_peso_de(0, "kg")
        assert spin_cant is not None
        spin_cant.setValue(5)

        mock_warning.assert_called_once()
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("1.000")
        assert dialogo.total_bs == Decimal("5.00")
        spin_cant = dialogo._spin_peso_de(0, "kg")
        assert spin_cant is not None
        assert spin_cant.value() == 1

    # El ticket muestra Kg/g SOLO si alguna linea es PESO/GRAMOS.
    def test_ticket_mezcla_unidad_y_peso_y_alterna_el_layout(self, qtbot: QtBot) -> None:
        """El ticket muestra Kg/g SOLO si alguna linea es PESO/GRAMOS."""
        unidad = Producto(
            idproducto=10,
            nombre_producto="Arroz",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("5.00"),
            precio_venta_usd=Decimal("0.10"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        peso = Producto(
            idproducto=11,
            nombre_producto="Carne",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = self._pos_con_catalogo(qtbot, unidad)
        dialogo.controlador_productos = MagicMock()
        dialogo.controlador_productos.listar_todos.return_value = [unidad, peso]
        dialogo.controlador_productos.obtener_por_id.side_effect = lambda pid: (
            peso if int(str(pid)) == 11 else unidad
        )
        dialogo.controlador_productos.obtener_categorias.return_value = []
        dialogo._cargar_catalogo()
        assert dialogo.tabla_productos_catalogo.rowCount() == 2

        tabla = dialogo.tabla_productos_venta

        item = dialogo.tabla_productos_catalogo.item(0, 0)
        assert item is not None
        dialogo._on_catalogo_doble_clic(item)
        assert tabla.isColumnHidden(2)
        assert tabla.isColumnHidden(5)
        assert dialogo._layout_ticket == "unidad"
        assert dialogo._spin_peso_de(0, "g") is None

        item_peso = dialogo.tabla_productos_catalogo.item(1, 0)
        assert item_peso is not None
        dialogo._on_catalogo_doble_clic(item_peso)
        assert not tabla.isColumnHidden(2)
        assert not tabla.isColumnHidden(5)
        assert dialogo._layout_ticket == "peso"
        item_cabecera = tabla.horizontalHeaderItem(1)
        assert item_cabecera is not None
        assert item_cabecera.text() == "Kg"
        assert dialogo._spin_peso_de(0, "g") is None
        assert dialogo._spin_peso_de(1, "kg") is not None
        assert dialogo._spin_peso_de(1, "g") is not None
        assert tabla.cellWidget(1, 5) is not None

        dialogo._eliminar_producto_venta(1)
        assert len(dialogo.productos_venta) == 1
        assert tabla.isColumnHidden(2)
        assert tabla.isColumnHidden(5)
        assert dialogo._layout_ticket == "unidad"

    # Un peso mayor al stock avisa y revierte la casilla editada.
    def test_editar_cantidad_mayor_al_stock_revierte(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un peso mayor al stock avisa y revierte la casilla editada."""
        producto_peso = self._producto_peso()
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto_peso, monkeypatch)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        spin_kg = dialogo._spin_peso_de(0, "kg")
        assert spin_kg is not None
        spin_kg.setValue(99)

        mock_warning.assert_called_once()
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("1.000")
        assert dialogo.total_bs == Decimal("12.00")
        assert dialogo._spin_peso_de(0, "kg") is not None
        assert dialogo._spin_peso_de(0, "kg").value() == 1  # type: ignore[union-attr]

    # Tras un peso invalido, el foco vuelve a Kg con el texto elegido.
    def test_revertir_peso_devuelve_el_foco_a_la_casilla_de_kg(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tras un peso invalido, el foco vuelve a Kg con el texto elegido."""
        producto_peso = self._producto_peso()
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto_peso, monkeypatch)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        spin_kg = dialogo._spin_peso_de(0, "kg")
        assert spin_kg is not None
        spin_kg.setValue(99)
        mock_warning.assert_called_once()

        spin_nuevo = dialogo._spin_peso_de(0, "kg")
        assert spin_nuevo is not None
        assert spin_nuevo is not spin_kg
        assert spin_nuevo.value() == 1
        linea_spin = spin_nuevo.lineEdit()
        assert linea_spin is not None
        assert linea_spin.selectedText() == "1"

    # Verifica que ANULAR VENTA vacia el ticket actual.
    def test_anular_limpia_el_ticket(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que ANULAR VENTA vacia el ticket actual."""
        producto = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("10.00"),
            precio_venta_usd=Decimal("0.20"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto, monkeypatch)
        assert len(dialogo.productos_venta) == 1

        dialogo._limpiar_ticket()

        assert dialogo.productos_venta == []
        assert dialogo.total_bs == Decimal("0.00")
        assert dialogo.tabla_productos_venta.rowCount() == 0
        assert dialogo.grupo_pago.isHidden()

    # Verifica que el TOTAL muestra el precio completo (sin desglose IVA).
    def test_total_sin_desglose_iva(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que el TOTAL muestra el precio completo (sin desglose IVA)."""
        producto = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("11.60"),
            precio_venta_usd=Decimal("0.24"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto, monkeypatch)

        assert dialogo.total_bs == Decimal("11.60")
        assert "11,60" in dialogo.lbl_total.text()
        assert "Sin tasa de cambio" in dialogo.lbl_total_usd.text()

    # Verifica que el total en USD usa la tasa activa.
    def test_total_usd_con_tasa(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que el total en USD usa la tasa activa."""
        producto = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("100.00"),
            precio_venta_usd=Decimal("2.00"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        tasa_mock = MagicMock()
        tasa_mock.tasa_venta = Decimal("40.00")
        tasa_mock.fecha = "2026-09-17"

        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        dialogo.controlador_tasas = MagicMock()
        dialogo.controlador_tasas.tasa_activa.return_value = tasa_mock
        dialogo._actualizar_tasa()
        self._agregar_producto_al_ticket(dialogo, producto, monkeypatch)

        assert "80,00" in dialogo.lbl_total.text()
        assert "2.00" in dialogo.lbl_total_usd.text()

    # Verifica que F12 esta ligado a la finalizacion de la venta.
    def test_atajo_f12_cobra(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que F12 esta ligado a la finalizacion de la venta."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        atajo = dialogo._atajo_cobrar
        assert atajo.key().toString() == "F12"
        atajo.activated.emit()

        mock_warning.assert_called_once()

    # Helper: POS abierto con 1 producto en el ticket y tasa simulada.
    def _abrir_pos_con_ticket(
        self,
        qtbot: QtBot,
        monkeypatch: pytest.MonkeyPatch,
        precio: str = "100.00",
        tasa: str = "50.00",
    ) -> FormularioVenta:
        """Helper: POS abierto con 1 producto en el ticket y tasa simulada."""
        precio_dec = Decimal(precio)
        tasa_dec = Decimal(tasa)
        producto = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            tipo_venta="UNIDAD",
            precio_venta_bs=precio_dec,
            precio_venta_usd=precio_dec / tasa_dec,
            stock_actual=Decimal("100"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        tasa_mock = MagicMock()
        tasa_mock.tasa_venta = Decimal(tasa)
        tasa_mock.fecha = "2026-09-17"
        dialogo._tasa = tasa_mock
        dialogo.controlador_tasas = MagicMock()
        dialogo.controlador_tasas.tasa_activa.return_value = tasa_mock
        self._agregar_producto_al_ticket(dialogo, producto, monkeypatch)
        return dialogo

    # Los 6 metodos existen como botones y sin elegir uno no hay pago.
    def test_metodos_de_pago_en_botones(self, qtbot: QtBot) -> None:
        """Los 6 metodos existen como botones y sin elegir uno no hay pago."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        assert sorted(dialogo._botones_metodo) == sorted(METODOS_PAGO)
        assert dialogo.pagos == []
        assert dialogo.btn_pago_mixto.text() == "PAGO MIXTO"
        assert dialogo.btn_pago_mixto.property("rol") == "pago_mixto_boton"
        assert dialogo.fila_recibido.isHidden()
        assert dialogo.panel_mixto.isHidden()

    # COBRAR deshabilitado sin pagos/parcial; habilitado con PAGO COMPLETO.
    def test_cobrar_solo_se_habilita_con_pago_completo(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """COBRAR deshabilitado sin pagos/parcial; habilitado con PAGO COMPLETO."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        assert dialogo.btn_cobrar.isEnabled() is False

        dialogo._alternar_panel_mixto()
        dialogo._seleccionar_metodo_mixto("efectivo_bs")
        dialogo.spin_monto_mixto.setValue(40.0)
        dialogo._agregar_pago_mixto()
        assert len(dialogo.pagos) == 1
        assert dialogo.btn_cobrar.isEnabled() is False
        assert "RESTANTE" in dialogo.lbl_restante.text()

        dialogo._seleccionar_metodo_mixto("pago_movil")
        dialogo._agregar_pago_mixto()
        assert len(dialogo.pagos) == 2
        assert "PAGO COMPLETO" in dialogo.lbl_restante.text()
        assert dialogo.btn_cobrar.isEnabled() is True

        dialogo._eliminar_pago(0)
        assert dialogo.btn_cobrar.isEnabled() is False

    # Flujo del usuario: Efectivo Bs 40 + Pago Movil (resto) → 2 pagos.
    @pytest.mark.aceptacion
    def test_flujo_pago_mixto_parcial_tras_parcial(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Flujo del usuario: Efectivo Bs 40 + Pago Movil (resto) → 2 pagos."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo.controlador_ventas = MagicMock()
        venta_mock = MagicMock()
        venta_mock.numero_factura = "F-0001"
        venta_mock.total_bs = Decimal("100.00")
        dialogo.controlador_ventas.crear.return_value = venta_mock

        mock_information = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.information",
            mock_information,
        )
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        dialogo._alternar_panel_mixto()
        dialogo._seleccionar_metodo_mixto("efectivo_bs")
        dialogo.spin_monto_mixto.setValue(40.0)
        dialogo._agregar_pago_mixto()
        assert len(dialogo.pagos) == 1
        assert "40,00" in dialogo.lbl_cubierto.text()

        dialogo._seleccionar_metodo_mixto("pago_movil")
        assert dialogo.spin_monto_mixto.value() == 60.0
        dialogo._agregar_pago_mixto()

        assert len(dialogo.pagos) == 2
        assert dialogo.pagos[0]["metodo"] == "efectivo_bs"
        assert dialogo.pagos[0]["monto_bs"] == Decimal("40.00")
        assert dialogo.pagos[1]["metodo"] == "pago_movil"
        assert dialogo.pagos[1]["monto_bs"] == Decimal("60.00")
        assert dialogo._monto_restante_bs() == Decimal("0.00")
        assert "PAGO COMPLETO" in dialogo.lbl_restante.text()
        assert not dialogo.lbl_modo_pago.isHidden()

        dialogo._finalizar_venta()

        assert mock_warning.call_count == 0
        mock_information.assert_called_once()
        args, kwargs = dialogo.controlador_ventas.crear.call_args
        metodo_pago = args[1]
        assert metodo_pago["efectivo_bs"] == Decimal("40.00")
        assert metodo_pago["pago_movil"] == Decimal("60.00")
        assert len(kwargs["pagos"]) == 2
        assert kwargs["pagos"][0]["metodo"] == "efectivo_bs"
        assert kwargs["pagos"][1]["metodo"] == "pago_movil"

    # Elegir metodo pre-llena el recibido con el faltante (cobro rapido).
    def test_seleccionar_metodo_prellena_el_faltante(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Elegir metodo pre-llena el recibido con el faltante (cobro rapido)."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        assert dialogo.total_bs == Decimal("100.00")

        dialogo._seleccionar_metodo("efectivo_bs")
        assert dialogo._botones_metodo["efectivo_bs"].property("rol") == "metodo_activo"
        assert not dialogo.fila_recibido.isHidden()
        assert dialogo.lbl_recibido.text() == "Recibido Bs.:"
        assert dialogo.spin_recibido.value() == 100.0
        assert "Pago exacto" in dialogo.lbl_estado_recibido.text()
        assert dialogo.btn_registrar_recibido.isEnabled() is True

        dialogo._seleccionar_metodo("efectivo_usd")
        assert dialogo.lbl_recibido.text() == "Recibido USD:"
        assert dialogo.spin_recibido.value() == 2.0
        assert "Pago exacto" in dialogo.lbl_estado_recibido.text()

    # El POS muestra 'PAGO MIXTO' en el resumen al usar 2+ metodos.
    def test_indicador_pago_mixto_aparece_con_2_metodos(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """El POS muestra 'PAGO MIXTO' en el resumen al usar 2+ metodos."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        assert dialogo.lbl_modo_pago.text() == "PAGO MIXTO"
        assert dialogo.lbl_modo_pago.isHidden()

        dialogo._alternar_panel_mixto()
        dialogo._seleccionar_metodo_mixto("efectivo_bs")
        dialogo.spin_monto_mixto.setValue(40.0)
        dialogo._agregar_pago_mixto()
        assert len(dialogo.pagos) == 1
        assert dialogo.lbl_modo_pago.isHidden()

        dialogo.spin_monto_mixto.setValue(30.0)
        dialogo._agregar_pago_mixto()
        assert len(dialogo.pagos) == 2
        assert dialogo.lbl_modo_pago.isHidden()

        dialogo._seleccionar_metodo_mixto("pago_movil")
        dialogo.spin_monto_mixto.setValue(30.0)
        dialogo._agregar_pago_mixto()
        assert len(dialogo.pagos) == 3
        assert not dialogo.lbl_modo_pago.isHidden()

    # Efectivo: si se teclea de mas, se aplica solo lo que cubre.
    def test_agregar_pago_registra_solo_lo_aplicado(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Efectivo: si se teclea de mas, se aplica solo lo que cubre."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)

        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_recibido.setValue(500.0)
        assert "VUELTO" in dialogo.lbl_estado_recibido.text()
        assert "400,00" in dialogo.lbl_estado_recibido.text()
        dialogo._registrar_efectivo()

        assert len(dialogo.pagos) == 1
        assert dialogo.pagos[0]["monto"] == Decimal("500.00")
        assert dialogo.pagos[0]["monto_bs"] == Decimal("100.00")
        assert dialogo.pagos[0]["vuelto_bs"] == Decimal("400.00")
        assert dialogo.tabla_pagos.rowCount() == 1
        celda_vuelto = dialogo.tabla_pagos.item(0, 3)
        assert celda_vuelto is not None
        assert "400,00" in celda_vuelto.text()
        assert dialogo._monto_restante_bs() == Decimal("0.00")
        assert "PAGO COMPLETO" in dialogo.lbl_restante.text()

    # Regresion: USD cuando la tasa no divide exacto (100.
    @pytest.mark.aceptacion
    def test_pago_en_usd_con_tasa_no_redonda_cobra_en_un_paso(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regresion: USD cuando la tasa no divide exacto (100.00 / 30.00)."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch, tasa="30.00")
        dialogo.controlador_ventas = MagicMock()
        venta_mock = MagicMock()
        venta_mock.numero_factura = "F-0002"
        venta_mock.total_bs = Decimal("100.00")
        dialogo.controlador_ventas.crear.return_value = venta_mock

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )
        mock_information = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.information",
            mock_information,
        )

        dialogo._seleccionar_metodo("efectivo_usd")
        assert dialogo.spin_recibido.value() == 3.34
        dialogo._registrar_efectivo()

        assert len(dialogo.pagos) == 1
        assert dialogo.pagos[0]["monto"] == Decimal("3.34")
        assert dialogo.pagos[0]["monto_bs"] == Decimal("100.00")
        assert dialogo.pagos[0]["vuelto_bs"] == Decimal("0.20")
        assert dialogo.pagos[0]["tasa_venta"] == Decimal("30.00")
        assert dialogo._monto_restante_bs() == Decimal("0.00")
        celda_aplicado = dialogo.tabla_pagos.item(0, 2)
        assert celda_aplicado is not None
        celda_vuelto = dialogo.tabla_pagos.item(0, 3)
        assert celda_vuelto is not None
        assert celda_aplicado.text() == "100,00 Bs."
        assert "0,20" in celda_vuelto.text()

        dialogo._finalizar_venta()

        assert mock_warning.call_count == 0
        mock_information.assert_called_once()
        args, kwargs = dialogo.controlador_ventas.crear.call_args
        assert args[1]["efectivo_usd"] == Decimal("3.34")
        assert kwargs["pagos"][0]["monto_bs"] == Decimal("100.00")

    # Regresion: con el alto fijo de 88 px solo se veia la PRIMERA fila.
    def test_alto_de_la_tabla_de_pagos_acompana_a_las_filas(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regresion: con el alto fijo de 88 px solo se veia la PRIMERA fila."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch, precio="5000.00")
        tabla = dialogo.tabla_pagos
        alto_minimo = tabla.height()

        dialogo._alternar_panel_mixto()

        for _ in range(2):
            dialogo.spin_monto_mixto.setValue(10.0)
            dialogo._agregar_pago_mixto()
        assert tabla.height() == alto_minimo

        dialogo.spin_monto_mixto.setValue(10.0)
        dialogo._agregar_pago_mixto()
        alto_3 = tabla.height()
        assert alto_3 > alto_minimo

        dialogo.spin_monto_mixto.setValue(10.0)
        dialogo._agregar_pago_mixto()
        alto_4 = tabla.height()
        assert alto_4 > alto_3

        dialogo.spin_monto_mixto.setValue(10.0)
        dialogo._agregar_pago_mixto()
        assert tabla.rowCount() == 5
        assert tabla.height() == alto_4

        while dialogo.pagos:
            dialogo._eliminar_pago(0)
        assert tabla.rowCount() == 0
        assert tabla.height() == alto_minimo

    # La ultima columna (Borrar) queda fija y ninguna seccion desborda.
    def test_tabla_de_pagos_no_desborda_el_viewport(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """La ultima columna (Borrar) queda fija y ninguna seccion desborda."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo._registrar_efectivo()
        qtbot.wait(0)

        tabla = dialogo.tabla_pagos
        encabezado = tabla.horizontalHeader()
        viewport = tabla.viewport()
        assert encabezado is not None
        assert viewport is not None
        assert encabezado.stretchLastSection() is False
        assert encabezado.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
        assert encabezado.sectionResizeMode(4) == QHeaderView.ResizeMode.Fixed

        anchos = [encabezado.sectionSize(i) for i in range(tabla.columnCount())]
        assert sum(anchos) <= viewport.width()

        boton = tabla.cellWidget(0, 4)
        assert boton is not None
        assert boton.minimumWidth() <= anchos[4]
        assert boton.maximumWidth() <= anchos[4]

    # Si la tasa cambia, el recorte anterior deja de ser valido.
    def test_cambio_de_tasa_descarta_el_vuelto_por_redondeo(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Si la tasa cambia, el recorte anterior deja de ser valido."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch, tasa="30.00")
        dialogo.controlador_ventas = MagicMock()
        dialogo._seleccionar_metodo("efectivo_usd")
        dialogo._registrar_efectivo()
        assert dialogo.pagos[0]["vuelto_bs"] == Decimal("0.20")

        assert dialogo._tasa is not None
        dialogo._tasa.tasa_venta = Decimal("50.00")
        dialogo._recalcular_equivalencias()

        assert dialogo.pagos[0]["tasa_venta"] == Decimal("50.00")
        assert dialogo.pagos[0]["monto_bs"] == Decimal("167.00")
        assert dialogo.pagos[0]["vuelto_bs"] == Decimal("0.00")
        assert dialogo._monto_restante_bs() == Decimal("-67.00")

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )
        dialogo._finalizar_venta()

        assert "Pago de mas" in str(mock_warning.call_args)
        dialogo.controlador_ventas.crear.assert_not_called()

    # Con dos pagos el resumen cuadra; borrar uno vuelve a faltar.
    def test_varios_pagos_y_eliminar_uno(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Con dos pagos el resumen cuadra; borrar uno vuelve a faltar."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)

        dialogo._alternar_panel_mixto()
        dialogo._seleccionar_metodo_mixto("efectivo_bs")
        dialogo.spin_monto_mixto.setValue(60.0)
        dialogo._agregar_pago_mixto()

        dialogo._seleccionar_metodo_mixto("efectivo_usd")
        assert dialogo.spin_monto_mixto.value() == 0.8
        dialogo._agregar_pago_mixto()

        assert [p["metodo"] for p in dialogo.pagos] == ["efectivo_bs", "efectivo_usd"]
        assert dialogo.pagos[1]["monto"] == Decimal("0.80")
        assert dialogo.pagos[1]["moneda"] == "USD"
        assert dialogo._monto_restante_bs() == Decimal("0.00")
        assert dialogo.tabla_pagos.rowCount() == 2

        boton_borrar = dialogo.tabla_pagos.cellWidget(0, 4)
        assert isinstance(boton_borrar, QPushButton)
        boton_borrar.click()

        assert len(dialogo.pagos) == 1
        assert dialogo._monto_restante_bs() == Decimal("60.00")
        assert "RESTANTE" in dialogo.lbl_restante.text()

    # Si el monto supera el faltante, se informa el cambio a devolver.
    def test_efectivo_avisa_el_cambio_en_vivo(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Si el monto supera el faltante, se informa el cambio a devolver."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)

        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_recibido.setValue(150.0)
        assert "VUELTO" in dialogo.lbl_estado_recibido.text()
        assert "50,00" in dialogo.lbl_estado_recibido.text()

        dialogo._alternar_panel_mixto()
        dialogo._seleccionar_metodo_mixto("efectivo_bs")
        dialogo.spin_monto_mixto.setValue(150.0)
        assert "CAMBIO" in dialogo.lbl_info_mixto.text()
        assert "50,00" in dialogo.lbl_info_mixto.text()

    # Sin metodo elegido en el panel mixto no se agrega nada y se avisa.
    def test_agregar_pago_mixto_sin_metodo_avisa(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin metodo elegido en el panel mixto no se agrega nada y se avisa."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        dialogo._metodo_mixto = None
        dialogo._agregar_pago_mixto()

        mock_warning.assert_called_once()
        assert "Selecciona un metodo" in str(mock_warning.call_args)
        assert dialogo.pagos == []

    # Sin tasa activa no se puede convertir ni cobrar en USD.
    def test_efectivo_usd_sin_tasa_queda_deshabilitado(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin tasa activa no se puede convertir ni cobrar en USD."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo._tasa = None

        dialogo._seleccionar_metodo("efectivo_usd")

        assert dialogo.spin_recibido.isEnabled() is False
        assert dialogo.btn_registrar_recibido.isEnabled() is False
        assert "Sin tasa" in dialogo.lbl_estado_recibido.text()

    # Quitar el ultimo producto descarta los pagos de esa venta.
    def test_ticket_vacio_descarta_el_desglose(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Quitar el ultimo producto descarta los pagos de esa venta."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)

        dialogo._seleccionar_metodo("tarjeta")
        assert len(dialogo.pagos) == 1

        dialogo._eliminar_producto_venta(0)

        assert dialogo.pagos == []
        assert dialogo.tabla_pagos.rowCount() == 0
        assert dialogo.grupo_pago.isHidden()

    # ANULAR VENTA limpia el ticket y su desglose de pagos.
    def test_anular_tambien_limpia_el_desglose(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ANULAR VENTA limpia el ticket y su desglose de pagos."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)

        dialogo._seleccionar_metodo("tarjeta")
        assert len(dialogo.pagos) == 1

        dialogo._limpiar_ticket()

        assert dialogo.pagos == []
        assert dialogo._metodo_actual is None
        assert dialogo.tabla_pagos.rowCount() == 0
        assert dialogo.panel_mixto.isHidden()
        assert dialogo.fila_recibido.isHidden()

    # Con ticket pero sin pagos, COBRAR avisa y no llama al controlador.
    def test_cobrar_sin_pagos_avisa_y_no_crea_la_venta(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Con ticket pero sin pagos, COBRAR avisa y no llama al controlador."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo.controlador_ventas = MagicMock()
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        dialogo._finalizar_venta()

        mock_warning.assert_called_once()
        dialogo.controlador_ventas.crear.assert_not_called()

    # Si falta por cubrir, COBRAR avisa y no registra la venta.
    def test_cobrar_con_pago_parcial_avisa(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Si falta por cubrir, COBRAR avisa y no registra la venta."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo.controlador_ventas = MagicMock()
        dialogo._alternar_panel_mixto()
        dialogo._seleccionar_metodo_mixto("efectivo_bs")
        dialogo.spin_monto_mixto.setValue(30.0)
        dialogo._agregar_pago_mixto()

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        dialogo._finalizar_venta()

        mock_warning.assert_called_once()
        assert "Falta por cubrir" in str(mock_warning.call_args)
        dialogo.controlador_ventas.crear.assert_not_called()

    # COBRAR envia el desglose de pagos y su resumen por metodo.
    @pytest.mark.aceptacion
    def test_cobrar_envia_el_desglose_al_controlador(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """COBRAR envia el desglose de pagos y su resumen por metodo."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo.controlador_ventas = MagicMock()
        venta_mock = MagicMock()
        venta_mock.numero_factura = "F-0001"
        venta_mock.total_bs = Decimal("100.00")
        dialogo.controlador_ventas.crear.return_value = venta_mock

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )
        mock_information = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.information",
            mock_information,
        )

        dialogo._alternar_panel_mixto()
        dialogo._seleccionar_metodo_mixto("efectivo_bs")
        dialogo.spin_monto_mixto.setValue(60.0)
        dialogo._agregar_pago_mixto()
        dialogo._seleccionar_metodo_mixto("efectivo_usd")
        dialogo._agregar_pago_mixto()

        dialogo._finalizar_venta()

        assert mock_warning.call_count == 0
        mock_information.assert_called_once()
        args, kwargs = dialogo.controlador_ventas.crear.call_args
        metodo_pago = args[1]
        assert metodo_pago["efectivo_bs"] == Decimal("60.00")
        assert metodo_pago["efectivo_usd"] == Decimal("0.80")
        assert len(kwargs["pagos"]) == 2
        assert kwargs["pagos"][1]["metodo"] == "efectivo_usd"
        assert kwargs["pagos"][1]["monto"] == Decimal("0.80")
        assert kwargs["pagos"][1]["monto_bs"] == Decimal("40.00")

    # El POS tiene el boton '✏️ Tasa Manual' (rol QSS en la cabecera).
    def test_boton_tasa_manual_existe(self, qtbot: QtBot) -> None:
        """El POS tiene el boton '✏️ Tasa Manual' (rol QSS en la cabecera)."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        assert isinstance(dialogo.btn_tasa_manual, QPushButton)
        assert "Tasa Manual" in dialogo.btn_tasa_manual.text()
        assert dialogo.btn_tasa_manual.property("rol") == "tasa_manual_boton"
        assert dialogo.btn_tasa_manual.isEnabled() is False

        controlador = MagicMock()
        controlador.tasa_activa.return_value = None
        con_controlador = FormularioVenta(controlador_tasas=controlador)
        qtbot.addWidget(con_controlador)
        assert con_controlador.btn_tasa_manual.isEnabled() is True

    # Fijar una manual cambia el label, la tasa en vivo y persiste con origen.
    @pytest.mark.aceptacion
    def test_fijar_tasa_manual_actualiza_label_y_registra(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fijar una manual cambia el label, la tasa en vivo y persiste con origen."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo.controlador_tasas = MagicMock()

        dialogo._establecer_tasa_manual(Decimal("860.00"))

        assert dialogo._tasa_manual_activa is True
        assert dialogo._tasa is not None
        assert dialogo._tasa.tasa_venta == Decimal("860.00")
        assert dialogo._tasa_base_bcv == Decimal("50.00")
        assert "Tasa MANUAL" in dialogo.lbl_tasa.text()
        assert dialogo.lbl_tasa.property("rol") == "tasa_bcv_manual"
        dialogo.controlador_tasas.registrar_tasa_manual.assert_called_once_with(
            Decimal("860.00"),
            registrado_por=None,
        )

    # El clic en el boton abre el dialogo de tasa manual y la fija.
    @pytest.mark.aceptacion
    def test_pulsar_boton_tasa_manual_pide_y_fija(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """El clic en el boton abre el dialogo de tasa manual y la fija."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        instancia = MagicMock()
        instancia.exec.return_value = QDialog.DialogCode.Accepted
        instancia.tasa.return_value = Decimal("860.00")
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.DialogoTasaManual",
            MagicMock(return_value=instancia),
        )
        dialogo.btn_tasa_manual.setEnabled(True)

        dialogo.btn_tasa_manual.click()

        assert dialogo._tasa_manual_activa is True
        assert dialogo._tasa is not None
        assert dialogo._tasa.tasa_venta == Decimal("860.00")

    # Cancelar el dialogo de la tasa manual deja todo como estaba.
    @pytest.mark.aceptacion
    def test_cancelar_pedido_de_tasa_manual_no_cambia_nada(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cancelar el dialogo de la tasa manual deja todo como estaba."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        instancia = MagicMock()
        instancia.exec.return_value = QDialog.DialogCode.Rejected
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.DialogoTasaManual",
            MagicMock(return_value=instancia),
        )
        dialogo.btn_tasa_manual.setEnabled(True)

        dialogo.btn_tasa_manual.click()

        assert dialogo._tasa_manual_activa is False
        assert dialogo._tasa is not None
        assert dialogo._tasa.tasa_venta == Decimal("50.00")

    # Revertir vuelve a la tasa BCV base y apaga la manual en la BD.
    @pytest.mark.aceptacion
    def test_revertir_tasa_manual_restaura_la_bcv(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Revertir vuelve a la tasa BCV base y apaga la manual en la BD."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo.controlador_tasas = MagicMock()
        dialogo._establecer_tasa_manual(Decimal("860.00"))

        dialogo._revertir_tasa_manual()

        assert dialogo._tasa_manual_activa is False
        assert dialogo._tasa is not None
        assert dialogo._tasa.tasa_venta == Decimal("50.00")
        assert "Tasa BCV" in dialogo.lbl_tasa.text()
        assert dialogo.lbl_tasa.property("rol") == "tasa_bcv_auto"
        dialogo.controlador_tasas.desactivar_tasa_manual.assert_called_once_with()

    # Con manual activa, _actualizar_tasa() no consulta ni pisa la BCV.
    @pytest.mark.aceptacion
    def test_actualizar_tasa_no_pisa_la_manual(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Con manual activa, _actualizar_tasa() no consulta ni pisa la BCV."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo.controlador_tasas = MagicMock()
        dialogo._establecer_tasa_manual(Decimal("860.00"))

        tasa_nueva = MagicMock()
        tasa_nueva.tasa_venta = Decimal("75.00")
        tasa_nueva.fecha = "2026-09-17"
        dialogo.controlador_tasas.tasa_activa.return_value = tasa_nueva

        dialogo._actualizar_tasa()

        assert dialogo._tasa is not None
        assert dialogo._tasa.tasa_venta == Decimal("860.00")
        assert dialogo._tasa_manual_activa is True

    # Sin venta en curso y con manual activa, el tick pregunta y revierte.
    @pytest.mark.aceptacion
    def test_comprobar_tasa_bcv_sin_ticket_ofrece_reversion(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin venta en curso y con manual activa, el tick pregunta y revierte."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo.controlador_tasas = MagicMock()
        dialogo._establecer_tasa_manual(Decimal("860.00"))
        dialogo._limpiar_ticket()

        tasa_nueva = MagicMock()
        tasa_nueva.tasa_venta = Decimal("75.00")
        dialogo.controlador_tasas.tasa_activa.return_value = tasa_nueva
        mock_question = MagicMock(return_value=QMessageBox.StandardButton.Yes)
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.question",
            mock_question,
        )

        dialogo._comprobar_tasa_bcv()

        mock_question.assert_called_once()
        assert dialogo._tasa_manual_activa is False
        assert dialogo._tasa is not None
        assert dialogo._tasa.tasa_venta == Decimal("50.00")

    # Con ticket abierto el tick NUNCA pregunta: solo marca reversion.
    @pytest.mark.aceptacion
    def test_comprobar_tasa_bcv_con_ticket_solo_marca_pendiente(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Con ticket abierto el tick NUNCA pregunta: solo marca reversion."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo.controlador_tasas = MagicMock()
        dialogo._establecer_tasa_manual(Decimal("860.00"))

        tasa_nueva = MagicMock()
        tasa_nueva.tasa_venta = Decimal("75.00")
        dialogo.controlador_tasas.tasa_activa.return_value = tasa_nueva
        mock_question = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.question",
            mock_question,
        )

        dialogo._comprobar_tasa_bcv()

        mock_question.assert_not_called()
        assert dialogo._reversion_pendiente is True
        assert dialogo._tasa_manual_activa is True

    # La reversion diferida se ofrece al terminar (vacio el ticket).
    @pytest.mark.aceptacion
    def test_reversion_pendiente_se_ofrece_al_vaciar_ticket(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """La reversion diferida se ofrece al terminar (vacio el ticket)."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo.controlador_tasas = MagicMock()
        dialogo._establecer_tasa_manual(Decimal("860.00"))

        tasa_nueva = MagicMock()
        tasa_nueva.tasa_venta = Decimal("75.00")
        dialogo.controlador_tasas.tasa_activa.return_value = tasa_nueva
        mock_question = MagicMock(return_value=QMessageBox.StandardButton.Yes)
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.question",
            mock_question,
        )

        dialogo._comprobar_tasa_bcv()
        assert dialogo._reversion_pendiente is True

        dialogo._limpiar_ticket()

        mock_question.assert_called_once()
        assert dialogo._tasa_manual_activa is False
        assert dialogo._tasa is not None
        assert dialogo._tasa.tasa_venta == Decimal("50.00")

    # Sin tasa activa el panel mixto informa sin lanzar AssertionError.
    @pytest.mark.aceptacion
    def test_mixto_sin_tasa_muestra_texto_sin_crash(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin tasa activa el panel mixto informa sin lanzar AssertionError."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo._tasa = None
        dialogo._metodo_mixto = "efectivo_bs"
        dialogo.spin_monto_mixto.setValue(100.0)

        dialogo._actualizar_info_mixto()

        assert "sin tasa" in dialogo.lbl_info_mixto.text()

    # '+ AGREGAR' sobre una venta ya cubierta avisa y no crashea (fix del clic).
    @pytest.mark.aceptacion
    def test_agregar_pago_mixto_venta_cubierta_avisa(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """'+ AGREGAR' sobre una venta ya cubierta avisa y no crashea (fix del clic)."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo._alternar_panel_mixto()
        dialogo._seleccionar_metodo_mixto("efectivo_bs")
        dialogo.spin_monto_mixto.setValue(100.0)
        dialogo._agregar_pago_mixto()
        assert len(dialogo.pagos) == 1
        assert "PAGO COMPLETO" in dialogo.lbl_restante.text()

        mock_information = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.information",
            mock_information,
        )
        dialogo.spin_monto_mixto.setValue(10.0)
        dialogo.btn_agregar_mixto.setEnabled(True)
        dialogo.btn_agregar_mixto.click()

        mock_information.assert_called_once()
        assert "ya esta cubierta" in str(mock_information.call_args)


# Producto de prueba para tests de inventario.
@pytest.fixture()
def producto_ejemplo() -> Producto:
    """Producto de prueba para tests de inventario."""
    return Producto(
        idproducto=1,
        nombre_producto="Arroz",
        precio_compra=Decimal("1.00"),
        precio_venta_bs=Decimal("1.50"),
        precio_venta_usd=Decimal("0.50"),
        stock_actual=Decimal("10"),
        stock_minimo=Decimal("5"),
        unidad="KG",
    )


# Movimiento de inventario simulado para tests de tabla.
@pytest.fixture()
def movimiento_ejemplo(producto_ejemplo: Producto) -> MagicMock:
    """Movimiento de inventario simulado para tests de tabla."""
    mov = MagicMock()
    mov.id = 1
    mov.fecha_movimiento = datetime(2025, 1, 15, 10, 30, 0)
    mov.producto = producto_ejemplo
    mov.tipo = "ENTRADA"
    mov.cantidad = 5
    mov.stock_anterior = 10
    mov.stock_nuevo = 15
    return mov


class TestFormularioCambioContrasena:
    """Pruebas para el dialogo de cambio de contrasena/usuario."""

    pytestmark = pytest.mark.unitarias

    # Verifica que el dialogo se crea con el titulo correcto.
    def test_crear_dialogo(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que el dialogo se crea con el titulo correcto."""
        dialogo = FormularioCambioContrasena(usuario=usuario_admin)
        qtbot.addWidget(dialogo)

        assert "Cambiar Contraseña / Usuario" in dialogo.windowTitle()

    # Verifica que los campos del formulario existen.
    def test_widgets_existen(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que los campos del formulario existen."""
        dialogo = FormularioCambioContrasena(usuario=usuario_admin)
        qtbot.addWidget(dialogo)

        assert hasattr(dialogo, "txt_nombre_completo")
        assert hasattr(dialogo, "txt_nuevo_usuario")
        assert hasattr(dialogo, "txt_contrasena_actual")
        assert hasattr(dialogo, "txt_nueva_contrasena")

        assert isinstance(dialogo.txt_contrasena_actual, QLineEdit)
        assert isinstance(dialogo.txt_nueva_contrasena, QLineEdit)
        assert dialogo.txt_contrasena_actual.echoMode() == QLineEdit.EchoMode.Password
        assert dialogo.txt_nueva_contrasena.echoMode() == QLineEdit.EchoMode.Password

    # Verifica que los campos se precargan con datos del usuario.
    def test_campos_precargados(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que los campos se precargan con datos del usuario."""
        dialogo = FormularioCambioContrasena(usuario=usuario_admin)
        qtbot.addWidget(dialogo)

        assert dialogo.txt_nombre_completo.text() == "Administrador"

    # Verifica que rechaza guardar sin escribir la contrasena actual.
    def test_guardar_sin_contrasena_actual(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica que rechaza guardar sin escribir la contrasena actual."""
        dialogo = FormularioCambioContrasena(usuario=usuario_admin)
        qtbot.addWidget(dialogo)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_cambio_contrasena.QMessageBox.warning",
            mock_warning,
        )

        for btn in dialogo.findChildren(QPushButton):
            if btn.text() == "Guardar Cambios":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_warning.assert_called_once()

    # Verifica que contrasena actual incorrecta muestra error.
    def test_guardar_contrasena_incorrecta(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica que contrasena actual incorrecta muestra error."""
        dialogo = FormularioCambioContrasena(usuario=usuario_admin)
        qtbot.addWidget(dialogo)

        dialogo.auth_service.verificar_login = MagicMock(return_value=False)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_cambio_contrasena.QMessageBox.warning",
            mock_warning,
        )

        qtbot.keyClicks(dialogo.txt_contrasena_actual, "clave_incorrecta")

        for btn in dialogo.findChildren(QPushButton):
            if btn.text() == "Guardar Cambios":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_warning.assert_called_once()

    # Verifica que sin cambios muestra mensaje 'No se realizaron cambios'.
    def test_guardar_sin_cambios(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica que sin cambios muestra mensaje 'No se realizaron cambios'."""
        dialogo = FormularioCambioContrasena(usuario=usuario_admin)
        qtbot.addWidget(dialogo)

        dialogo.auth_service.verificar_login = MagicMock(return_value=True)

        mock_info = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_cambio_contrasena.QMessageBox.information",
            mock_info,
        )

        qtbot.keyClicks(dialogo.txt_contrasena_actual, "admin")

        for btn in dialogo.findChildren(QPushButton):
            if btn.text() == "Guardar Cambios":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_info.assert_called_once()

    # Verifica que cambiar nombre completo guarda exitosamente.
    def test_guardar_exitoso(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica que cambiar nombre completo guarda exitosamente."""
        dialogo = FormularioCambioContrasena(usuario=usuario_admin)
        qtbot.addWidget(dialogo)

        dialogo.auth_service.verificar_login = MagicMock(return_value=True)
        dialogo.auth_service.actualizar = MagicMock()

        mock_info = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_cambio_contrasena.QMessageBox.information",
            mock_info,
        )

        qtbot.keyClicks(dialogo.txt_contrasena_actual, "admin")
        dialogo.txt_nombre_completo.setText("Nuevo Nombre")

        for btn in dialogo.findChildren(QPushButton):
            if btn.text() == "Guardar Cambios":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        dialogo.auth_service.actualizar.assert_called_once()
        mock_info.assert_called_once()


class TestInventarioPagina:
    """Pruebas para la pagina de inventario."""

    pytestmark = pytest.mark.integracion

    # Verifica que la pagina se crea sin errores.
    def test_crear_pagina(self, qtbot: QtBot, producto_ejemplo: Producto) -> None:
        """Verifica que la pagina se crea sin errores."""
        mock_controlador_inv = MagicMock()
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        titulo = pagina.findChild(TituloPagina)
        assert titulo is not None
        label = titulo.findChild(QLabel)
        assert label is not None
        assert "Inventario" in label.text()

    # Verifica que los widgets principales existen.
    def test_widgets_existen(self, qtbot: QtBot, producto_ejemplo: Producto) -> None:
        """Verifica que los widgets principales existen."""
        mock_controlador_inv = MagicMock()
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        assert hasattr(pagina, "cmb_producto_inventario")
        assert hasattr(pagina, "tabla_movimientos")
        assert isinstance(pagina.cmb_producto_inventario, QComboBox)
        assert isinstance(pagina.tabla_movimientos, QTableWidget)

        botones = [btn.text() for btn in pagina.findChildren(QPushButton)]
        assert "Entrada" in botones
        assert "Salida" in botones
        assert "Ajuste" in botones
        assert "Refrescar" in botones

    # El cajero (VENDEDOR) no ve Salida ni Ajuste: solo historial y Entrada.
    def test_vendedor_solo_entrada_y_historial(
        self, qtbot: QtBot, producto_ejemplo: Producto
    ) -> None:
        """El cajero (VENDEDOR) no ve Salida ni Ajuste: solo historial y Entrada."""
        mock_controlador_inv = MagicMock()
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        vendedor = Usuario(
            id=2,
            usuario="cajero1",
            contrasena="hash_falso",
            nombre_completo="Cajero Uno",
            rol="VENDEDOR",
        )
        pagina = InventarioPagina(
            mock_controlador_inv,
            mock_controlador_prod,
            usuario_actual=vendedor,
        )
        qtbot.addWidget(pagina)

        assert pagina.btn_entrada.isVisibleTo(pagina)
        assert not pagina.btn_salida.isVisibleTo(pagina)
        assert not pagina.btn_ajuste.isVisibleTo(pagina)

        admin = Usuario(
            id=1,
            usuario="admin",
            contrasena="hash_falso",
            rol="ADMINISTRADOR",
        )
        pagina_admin = InventarioPagina(
            mock_controlador_inv,
            mock_controlador_prod,
            usuario_actual=admin,
        )
        qtbot.addWidget(pagina_admin)
        assert pagina_admin.btn_salida.isVisibleTo(pagina_admin)
        assert pagina_admin.btn_ajuste.isVisibleTo(pagina_admin)

    # Verifica que el combo de productos se puebla correctamente.
    def test_combo_poblado(self, qtbot: QtBot, producto_ejemplo: Producto) -> None:
        """Verifica que el combo de productos se puebla correctamente."""
        mock_controlador_inv = MagicMock()
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        assert pagina.cmb_producto_inventario.count() == 2
        assert pagina.cmb_producto_inventario.itemText(0) == "Todos los productos"
        assert "Arroz" in pagina.cmb_producto_inventario.itemText(1)

    # Verifica que la tabla se muestra vacia cuando no hay movimientos.
    def test_tabla_movimientos_vacia(self, qtbot: QtBot, producto_ejemplo: Producto) -> None:
        """Verifica que la tabla se muestra vacia cuando no hay movimientos."""
        mock_controlador_inv = MagicMock()
        mock_controlador_inv.movimientos_recientes.return_value = []
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        assert pagina.tabla_movimientos.rowCount() == 0

    # Verifica que la tabla muestra datos de movimientos.
    def test_tabla_movimientos_poblada(
        self, qtbot: QtBot, producto_ejemplo: Producto, movimiento_ejemplo: MagicMock
    ) -> None:
        """Verifica que la tabla muestra datos de movimientos."""
        mock_controlador_inv = MagicMock()
        mock_controlador_inv.movimientos_recientes.return_value = [movimiento_ejemplo]
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        assert pagina.tabla_movimientos.rowCount() == 1
        item_id = pagina.tabla_movimientos.item(0, 0)
        assert item_id is not None, "item(0,0) es None"
        assert item_id.text() == "1"
        item_tipo = pagina.tabla_movimientos.item(0, 3)
        assert item_tipo is not None, "item(0,3) es None"
        assert item_tipo.text() == "ENTRADA"

    # Verifica que el boton Entrada llama a registrar_entrada.
    def test_dialogo_entrada_flujo_exitoso(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, producto_ejemplo: Producto
    ) -> None:
        """Verifica que el boton Entrada llama a registrar_entrada."""
        mock_controlador_inv = MagicMock()
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        mock_info = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QMessageBox.information",
            mock_info,
        )
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QMessageBox.warning",
            mock_warning,
        )

        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QDialog.exec",
            MagicMock(return_value=QDialog.DialogCode.Accepted),
        )

        mock_combo = MagicMock()
        mock_combo.currentData.return_value = 1
        mock_spin = MagicMock()
        mock_spin.value.return_value = 5
        mock_motivo = MagicMock()
        mock_motivo.currentText.return_value = "COMPRA"
        mock_obs = MagicMock()
        mock_obs.text.return_value = ""

        monkeypatch.setattr(
            pagina,
            "_crear_formulario_movimiento",
            MagicMock(return_value=(mock_combo, mock_spin, mock_motivo, mock_obs)),
        )

        for btn in pagina.findChildren(QPushButton):
            if btn.text() == "Entrada":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_controlador_inv.registrar_entrada.assert_called_once_with(
            producto_id=1,
            cantidad=Decimal("5"),
            motivo="COMPRA",
            observaciones=None,
        )
        mock_info.assert_called_once()

    # Verifica que el boton Salida llama a registrar_salida.
    def test_dialogo_salida_flujo_exitoso(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, producto_ejemplo: Producto
    ) -> None:
        """Verifica que el boton Salida llama a registrar_salida."""
        mock_controlador_inv = MagicMock()
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        mock_info = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QMessageBox.information",
            mock_info,
        )
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QMessageBox.warning",
            mock_warning,
        )

        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QDialog.exec",
            MagicMock(return_value=QDialog.DialogCode.Accepted),
        )

        mock_combo = MagicMock()
        mock_combo.currentData.return_value = 1
        mock_spin = MagicMock()
        mock_spin.value.return_value = 3
        mock_motivo = MagicMock()
        mock_motivo.currentText.return_value = "VENTA"
        mock_obs = MagicMock()
        mock_obs.text.return_value = ""

        monkeypatch.setattr(
            pagina,
            "_crear_formulario_movimiento",
            MagicMock(return_value=(mock_combo, mock_spin, mock_motivo, mock_obs)),
        )

        for btn in pagina.findChildren(QPushButton):
            if btn.text() == "Salida":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_controlador_inv.registrar_salida.assert_called_once_with(
            producto_id=1,
            cantidad=Decimal("3"),
            motivo="VENTA",
            observaciones=None,
        )
        mock_info.assert_called_once()

    # Verifica que el boton Ajuste llama a registrar_ajuste.
    def test_dialogo_ajuste_flujo_exitoso(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, producto_ejemplo: Producto
    ) -> None:
        """Verifica que el boton Ajuste llama a registrar_ajuste."""
        mock_controlador_inv = MagicMock()
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        mock_info = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QMessageBox.information",
            mock_info,
        )
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QMessageBox.warning",
            mock_warning,
        )

        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QDialog.exec",
            MagicMock(return_value=QDialog.DialogCode.Accepted),
        )

        mock_combo = MagicMock()
        mock_combo.currentData.return_value = 1
        mock_spin = MagicMock()
        mock_spin.value.return_value = 8
        mock_motivo = MagicMock()
        mock_motivo.currentText.return_value = "INVENTARIO"
        mock_obs = MagicMock()
        mock_obs.text.return_value = "Ajuste por inventario"

        monkeypatch.setattr(
            pagina,
            "_crear_formulario_movimiento",
            MagicMock(return_value=(mock_combo, mock_spin, mock_motivo, mock_obs)),
        )

        for btn in pagina.findChildren(QPushButton):
            if btn.text() == "Ajuste":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_controlador_inv.registrar_ajuste.assert_called_once_with(
            producto_id=1,
            stock_fisico=Decimal("8"),
            motivo="INVENTARIO",
            observaciones="Ajuste por inventario",
        )
        mock_info.assert_called_once()

    # Verifica que cancelar el dialogo no llama a los servicios.
    def test_dialogo_cancelado(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, producto_ejemplo: Producto
    ) -> None:
        """Verifica que cancelar el dialogo no llama a los servicios."""
        mock_controlador_inv = MagicMock()
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QDialog.exec",
            MagicMock(return_value=QDialog.DialogCode.Rejected),
        )

        for btn in pagina.findChildren(QPushButton):
            if btn.text() == "Entrada":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_controlador_inv.registrar_entrada.assert_not_called()
        mock_controlador_inv.registrar_salida.assert_not_called()
        mock_controlador_inv.registrar_ajuste.assert_not_called()

    # Verifica que sin producto seleccionado muestra advertencia.
    def test_dialogo_producto_no_seleccionado(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, producto_ejemplo: Producto
    ) -> None:
        """Verifica que sin producto seleccionado muestra advertencia."""
        mock_controlador_inv = MagicMock()
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QMessageBox.warning",
            mock_warning,
        )

        monkeypatch.setattr(
            "sistema_financiero.ui.inventario_pagina.QDialog.exec",
            MagicMock(return_value=QDialog.DialogCode.Accepted),
        )

        mock_combo = MagicMock()
        mock_combo.currentData.return_value = None
        mock_spin = MagicMock()
        mock_spin.value.return_value = 5
        mock_motivo = MagicMock()
        mock_motivo.currentText.return_value = "COMPRA"
        mock_obs = MagicMock()
        mock_obs.text.return_value = ""

        monkeypatch.setattr(
            pagina,
            "_crear_formulario_movimiento",
            MagicMock(return_value=(mock_combo, mock_spin, mock_motivo, mock_obs)),
        )

        for btn in pagina.findChildren(QPushButton):
            if btn.text() == "Entrada":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_warning.assert_called_once()
        mock_controlador_inv.registrar_entrada.assert_not_called()

    # Verifica que cambiar el combo refresca la tabla con historial del producto.
    def test_tabla_refrescada_al_cambiar_producto(
        self, qtbot: QtBot, producto_ejemplo: Producto
    ) -> None:
        """Verifica que cambiar el combo refresca la tabla con historial del producto."""
        mock_controlador_inv = MagicMock()
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        pagina.cmb_producto_inventario.setCurrentIndex(1)

        mock_controlador_inv.historial_por_producto.assert_called_with(1)


class TestProductosPagina:
    """Pruebas para la pagina de productos con inventario embebido."""

    pytestmark = pytest.mark.integracion

    # La pagina creada tiene QTabWidget con pestanas Catalogo y Movimientos.
    def test_crear_pagina_con_pestanas(self, qtbot: QtBot, producto_ejemplo: Producto) -> None:
        """La pagina creada tiene QTabWidget con pestanas Catalogo y Movimientos."""
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]
        mock_controlador_inv = MagicMock()
        mock_controlador_inv.movimientos_recientes.return_value = []

        pagina = ProductosPagina(mock_controlador_prod, mock_controlador_inv)
        qtbot.addWidget(pagina)

        assert hasattr(pagina, "pestanas")
        assert pagina.pestanas.count() == 2
        assert pagina.pestanas.tabText(0) == "Catálogo"
        assert pagina.pestanas.tabText(1) == "Movimientos"

        titulo = pagina.findChild(TituloPagina)
        assert titulo is not None
        label = titulo.findChild(QLabel)
        assert label is not None
        assert "Productos" in label.text()

        assert hasattr(pagina, "tabla_productos")
        assert isinstance(pagina.tabla_productos, QTableWidget)
        botones = [btn.text() for btn in pagina.findChildren(QPushButton)]
        assert "Agregar" in botones
        assert "Editar" in botones
        assert "Eliminar" in botones

    # La pestana Movimientos contiene una InventarioPagina funcional.
    def test_pagina_embebe_inventario(self, qtbot: QtBot, producto_ejemplo: Producto) -> None:
        """La pestana Movimientos contiene una InventarioPagina funcional."""
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]
        mock_controlador_inv = MagicMock()
        mock_controlador_inv.movimientos_recientes.return_value = []

        pagina = ProductosPagina(mock_controlador_prod, mock_controlador_inv)
        qtbot.addWidget(pagina)

        sub_paginas = pagina.findChildren(InventarioPagina)
        assert len(sub_paginas) == 1
        sub = sub_paginas[0]
        assert sub.findChild(TituloPagina) is None

        assert sub.cmb_producto_inventario.count() == 2
        assert sub.cmb_producto_inventario.itemText(0) == "Todos los productos"
        assert "Arroz" in sub.cmb_producto_inventario.itemText(1)

        pagina.pestanas.setCurrentIndex(1)
        mock_controlador_inv.movimientos_recientes.assert_called()

    # Sin controlador de inventario: solo existe la pestana Catalogo.
    def test_sin_controlador_inventario_no_crea_pestana_movimientos(
        self, qtbot: QtBot, producto_ejemplo: Producto
    ) -> None:
        """Sin controlador de inventario: solo existe la pestana Catalogo."""
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = ProductosPagina(mock_controlador_prod)
        qtbot.addWidget(pagina)

        assert pagina.pestanas.count() == 1
        assert pagina.pestanas.tabText(0) == "Catálogo"


class TestUsuariosPagina:
    """Pruebas para la pagina de gestion de usuarios."""

    pytestmark = pytest.mark.integracion

    # Verifica que la pagina se crea sin errores.
    def test_crear_pagina(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que la pagina se crea sin errores."""

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        titulo = pagina.findChild(TituloPagina)
        assert titulo is not None
        label = titulo.findChild(QLabel)
        assert label is not None
        assert "Usuarios" in label.text()

    # Verifica que los labels del perfil existen.
    def test_widgets_perfil_existen(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que los labels del perfil existen."""

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        assert hasattr(pagina, "lbl_nombre")
        assert hasattr(pagina, "lbl_usuario")
        assert hasattr(pagina, "lbl_rol")
        assert "Administrador" in pagina.lbl_nombre.text()

    # Verifica que los botones de perfil existen.
    def test_botones_perfil_existen(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que los botones de perfil existen."""

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        botones = [btn.text() for btn in pagina.findChildren(QPushButton)]
        assert "Editar Perfil" in botones
        assert "Cambiar Contraseña" in botones

    # Verifica que la tabla de usuarios se crea correctamente.
    def test_tabla_usuarios_vacia(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica que la tabla de usuarios se crea correctamente."""
        monkeypatch.setattr(
            "sistema_financiero.ui.usuarios_pagina.AuthService.listar_usuarios",
            lambda _self: [],
        )

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        assert hasattr(pagina, "tabla_usuarios")
        assert pagina.tabla_usuarios.rowCount() == 0

    # Verifica que los botones de admin existen.
    def test_botones_admin_existen(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que los botones de admin existen."""

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        botones = [btn.text() for btn in pagina.findChildren(QPushButton)]
        assert "+ Crear Usuario" in botones
        assert "Resetear Contraseña" in botones
        assert "Activar / Desactivar" in botones

    # Verifica que resetear sin seleccionar muestra error.
    def test_seleccion_sin_usuario_muestra_error(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica que resetear sin seleccionar muestra error."""

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.usuarios_pagina.QMessageBox.warning",
            mock_warning,
        )

        for btn in pagina.findChildren(QPushButton):
            if btn.text() == "Resetear Contraseña":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_warning.assert_called_once()

    # Verifica que activar/desactivar sin seleccionar muestra error.
    def test_toggle_sin_seleccion_muestra_error(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica que activar/desactivar sin seleccionar muestra error."""

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.usuarios_pagina.QMessageBox.warning",
            mock_warning,
        )

        for btn in pagina.findChildren(QPushButton):
            if btn.text() == "Activar / Desactivar":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        mock_warning.assert_called_once()


class TestVentanaPrincipalAdmin:
    """Pruebas para VentanaPrincipal con usuario ADMINISTRADOR."""

    pytestmark = pytest.mark.sistema

    # Usuario con rol ADMINISTRADOR.
    @pytest.fixture()
    def usuario_real_admin(self) -> Usuario:
        """Usuario con rol ADMINISTRADOR."""
        return Usuario(
            id=1,
            usuario="admin",
            contrasena="hash_falso",
            nombre_completo="Administrador",
            activo=True,
            rol="ADMINISTRADOR",
        )

    # Verifica que el menu incluye 'Usuarios' para admin.
    def test_menu_incluye_usuarios(self, qtbot: QtBot, usuario_real_admin: Usuario) -> None:
        """Verifica que el menu incluye 'Usuarios' para admin."""
        ventana = VentanaPrincipal(usuario_real_admin)
        qtbot.addWidget(ventana)

        assert ventana.barra_navegacion.count() == 5

        nombres = []
        for i in range(ventana.barra_navegacion.count()):
            item = ventana.barra_navegacion.item(i)
            assert item is not None
            nombres.append(item.text())
        assert "Usuarios" in nombres

    # Verifica que hay 5 paginas para admin.
    def test_paginas_con_admin(self, qtbot: QtBot, usuario_real_admin: Usuario) -> None:
        """Verifica que hay 5 paginas para admin."""
        ventana = VentanaPrincipal(usuario_real_admin)
        qtbot.addWidget(ventana)

        assert ventana.paginas.count() == 5

    # El admin ve Dashboard: Ventas en la fila 1 y el timer activo.
    def test_admin_indice_ventas_y_timer_activo(
        self, qtbot: QtBot, usuario_real_admin: Usuario
    ) -> None:
        """El admin ve Dashboard: Ventas en la fila 1 y el timer activo."""
        ventana = VentanaPrincipal(usuario_real_admin)
        qtbot.addWidget(ventana)

        assert ventana._indice_ventas == 1
        assert ventana._timer_dashboard.isActive() is True

    # El VENDEDOR solo ve "Ventas" (sin Usuarios ni otras paginas).
    def test_menu_sin_usuarios_para_vendedor(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """El VENDEDOR solo ve "Ventas" (sin Usuarios ni otras paginas)."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        assert ventana.barra_navegacion.count() == 1

        nombres = []
        for i in range(ventana.barra_navegacion.count()):
            item = ventana.barra_navegacion.item(i)
            assert item is not None
            nombres.append(item.text())
        assert nombres == ["Ventas"]


class TestVentasPagina:
    """Pruebas de la anulacion de ventas por fila (columna Acciones, admin)."""

    pytestmark = pytest.mark.integracion

    # Construye una VentasPagina con ventas simuladas y controlador mock.
    def _pagina(self, session: Session, rol: str, ventas: list[Venta]) -> VentasPagina:
        """Construye una VentasPagina con ventas simuladas y controlador mock."""
        usuario = Usuario(
            id=1,
            usuario="admin",
            contrasena="hash_falso",
            nombre_completo="Administrador",
            rol=rol,
            activo=True,
        )
        controlador = MagicMock()
        controlador.historial_por_fecha.return_value = ventas
        pagina = VentasPagina(
            usuario_actual=usuario,
            controlador_ventas=controlador,
            controlador_productos=MagicMock(),
            caja_service=CajaService(db_session=session),
        )
        return pagina

    # Crea una venta de prueba con los campos del historial.
    @staticmethod
    def _venta(idventa: int, factura: str, estado: str) -> Venta:
        return Venta(
            idventa=idventa,
            numero_factura=factura,
            fecha_venta=datetime(2026, 9, 24, 12, 0),
            total_bs=Decimal("100.00"),
            total_usd=Decimal("2.50"),
            efectivo_bs=Decimal("0.00"),
            efectivo_usd=Decimal("0.00"),
            tarjeta=Decimal("0.00"),
            pago_movil=Decimal("0.00"),
            bio_pago=Decimal("0.00"),
            transferencia=Decimal("100.00"),
            estado=estado,
        )

    # Admin ve la columna Acciones con botones 🚫; el cajero NO.
    def test_columna_acciones_solo_para_administrador(self, qtbot: QtBot, session: Session) -> None:
        """Admin ve la columna Acciones con botones 🚫; el cajero NO."""
        ventas = [self._venta(1, "F-0001", "COMPLETADA")]
        pagina = self._pagina(session, "ADMINISTRADOR", ventas)
        qtbot.addWidget(pagina)

        assert pagina.es_administrador is True
        assert pagina.tabla_ventas.columnCount() == 7
        boton = pagina.tabla_ventas.cellWidget(0, 6)
        assert isinstance(boton, QPushButton)
        assert boton.text() == "🚫"
        assert boton.isEnabled()

        pagina_cajera = self._pagina(session, "VENDEDOR", ventas)
        qtbot.addWidget(pagina_cajera)
        assert pagina_cajera.es_administrador is False
        assert pagina_cajera.tabla_ventas.columnCount() == 6
        assert pagina_cajera.tabla_ventas.cellWidget(0, 6) is None

    # Una venta ya anulada no puede anularse dos veces (boton disabled).
    @pytest.mark.aceptacion
    def test_boton_anular_fila_deshabilitado_en_venta_anulada(
        self, qtbot: QtBot, session: Session
    ) -> None:
        """Una venta ya anulada no puede anularse dos veces (boton disabled)."""
        ventas = [
            self._venta(1, "F-0001", "COMPLETADA"),
            self._venta(2, "F-0002", "ANULADA"),
        ]
        pagina = self._pagina(session, "ADMINISTRADOR", ventas)
        qtbot.addWidget(pagina)

        fila_completada = pagina.tabla_ventas.cellWidget(0, 6)
        assert fila_completada is not None
        assert fila_completada.isEnabled()

        fila_anulada = pagina.tabla_ventas.cellWidget(1, 6)
        assert fila_anulada is not None
        assert not fila_anulada.isEnabled()

    # Cancelar el dialogo de anulacion NO anula la venta.
    def test_anular_fila_cancelada_no_llama_al_controlador(
        self,
        qtbot: QtBot,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Cancelar el dialogo de anulacion NO anula la venta."""
        ventas = [self._venta(1, "F-0001", "COMPLETADA")]
        pagina = self._pagina(session, "ADMINISTRADOR", ventas)
        qtbot.addWidget(pagina)

        pagina.controlador_ventas = MagicMock()
        pagina.controlador_ventas.obtener_por_id.return_value = ventas[0]

        instancia_dialogo = MagicMock()
        instancia_dialogo.exec.return_value = QDialog.DialogCode.Rejected
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.DialogoAnulacion",
            MagicMock(return_value=instancia_dialogo),
        )

        boton = pagina.tabla_ventas.cellWidget(0, 6)
        assert isinstance(boton, QPushButton)
        boton.click()

        pagina.controlador_ventas.anular.assert_not_called()

    # Diálogo aceptado: anular() recibe el motivo y quien autoriza.
    @pytest.mark.aceptacion
    def test_anular_fila_con_motivo_llama_al_controlador(
        self,
        qtbot: QtBot,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Diálogo aceptado: anular() recibe el motivo y quien autoriza."""
        ventas = [self._venta(1, "F-0001", "COMPLETADA")]
        pagina = self._pagina(session, "ADMINISTRADOR", ventas)
        qtbot.addWidget(pagina)

        pagina.controlador_ventas = MagicMock()
        pagina.controlador_ventas.obtener_por_id.return_value = ventas[0]
        autorizante = Usuario(
            id=5,
            usuario="jefa",
            contrasena="x",
            rol="ADMINISTRADOR",
            activo=True,
        )

        instancia_dialogo = MagicMock()
        instancia_dialogo.exec.return_value = QDialog.DialogCode.Accepted
        instancia_dialogo.motivo.return_value = "Error de caja, se registro doble"
        instancia_dialogo.usuario_autorizante.return_value = autorizante
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.DialogoAnulacion",
            MagicMock(return_value=instancia_dialogo),
        )

        mock_informacion = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.information",
            mock_informacion,
        )

        boton = pagina.tabla_ventas.cellWidget(0, 6)
        assert isinstance(boton, QPushButton)
        boton.click()

        pagina.controlador_ventas.anular.assert_called_once_with(
            1,
            motivo_anulacion="Error de caja, se registro doble",
            anulado_por="jefa",
        )

    # Si anular() lanza un error inesperado, se muestra dialogo critico.
    def test_anular_fila_muestra_error_si_el_controlador_falla(
        self,
        qtbot: QtBot,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Si anular() lanza un error inesperado, se muestra dialogo critico."""
        ventas = [self._venta(1, "F-0001", "COMPLETADA")]
        pagina = self._pagina(session, "ADMINISTRADOR", ventas)
        qtbot.addWidget(pagina)

        pagina.controlador_ventas = MagicMock()
        pagina.controlador_ventas.obtener_por_id.return_value = ventas[0]
        autorizante = Usuario(
            id=5,
            usuario="jefa",
            contrasena="x",
            rol="ADMINISTRADOR",
            activo=True,
        )

        instancia_dialogo = MagicMock()
        instancia_dialogo.exec.return_value = QDialog.DialogCode.Accepted
        instancia_dialogo.motivo.return_value = "prueba"
        instancia_dialogo.usuario_autorizante.return_value = autorizante
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.DialogoAnulacion",
            MagicMock(return_value=instancia_dialogo),
        )
        mock_critico = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.critical",
            mock_critico,
        )
        mock_registrar = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.registrar_excepcion",
            mock_registrar,
        )

        # Funcion que lanza un RuntimeError para forzar el fallo.
        def _fallar(*args: object, **kwargs: object) -> None:
            raise RuntimeError("error inesperado de prueba")

        monkeypatch.setattr(pagina.controlador_ventas, "anular", _fallar)

        boton = pagina.tabla_ventas.cellWidget(0, 6)
        assert isinstance(boton, QPushButton)
        boton.click()

        mock_registrar.assert_called_once()
        mock_critico.assert_called_once()
        mensaje = mock_critico.call_args.args[2]
        assert "No se pudo anular" in mensaje

    # Columna Total de Venta: UNA cantidad clara en Bs (pago no-USD).
    def test_tabla_muestra_total_bs_una_cantidad(self, qtbot: QtBot, session: Session) -> None:
        """Columna Total de Venta: UNA cantidad clara en Bs (pago no-USD)."""
        ventas = [self._venta(1, "F-0001", "COMPLETADA")]
        pagina = self._pagina(session, "ADMINISTRADOR", ventas)
        qtbot.addWidget(pagina)

        cabeceras = []
        for i in range(6):
            item_cabecera = pagina.tabla_ventas.horizontalHeaderItem(i)
            assert item_cabecera is not None
            cabeceras.append(item_cabecera.text())
        assert cabeceras == ["ID", "Factura", "Fecha", "Total de Venta", "Metodo de Pago", "Estado"]

        contenedor = pagina.tabla_ventas.cellWidget(0, 3)
        assert contenedor is not None
        labels = contenedor.findChildren(QLabel)
        assert len(labels) == 1
        assert labels[0].text() == formatear_bs(Decimal("100.00"))
        assert labels[0].property("rol") == "total_tabla_bs"

    # Venta pagada SOLO en Efectivo USD → la celda muestra el USD.
    @pytest.mark.aceptacion
    def test_tabla_total_usd_solo_con_efectivo_usd(self, qtbot: QtBot, session: Session) -> None:
        """Venta pagada SOLO en Efectivo USD → la celda muestra el USD."""
        venta = self._venta(1, "F-0001", "COMPLETADA")
        venta.efectivo_usd = Decimal("2.50")
        venta.transferencia = Decimal("0.00")
        pagina = self._pagina(session, "ADMINISTRADOR", [venta])
        qtbot.addWidget(pagina)

        contenedor = pagina.tabla_ventas.cellWidget(0, 3)
        assert contenedor is not None
        labels = contenedor.findChildren(QLabel)
        assert len(labels) == 1
        assert labels[0].text() == formatear_usd(Decimal("2.50"))

    # Pago mixto → la celda muestra el total en Bolivares (no USD).
    @pytest.mark.aceptacion
    def test_tabla_total_mixto_muestra_bs(self, qtbot: QtBot, session: Session) -> None:
        """Pago mixto → la celda muestra el total en Bolivares (no USD)."""
        venta = self._venta(1, "F-0001", "COMPLETADA")
        venta.efectivo_bs = Decimal("50.00")
        venta.pago_movil = Decimal("50.00")
        venta.transferencia = Decimal("0.00")
        pagina = self._pagina(session, "ADMINISTRADOR", [venta])
        qtbot.addWidget(pagina)

        contenedor = pagina.tabla_ventas.cellWidget(0, 3)
        assert contenedor is not None
        labels = contenedor.findChildren(QLabel)
        assert len(labels) == 1
        assert labels[0].text() == formatear_bs(Decimal("100.00"))
        assert labels[0].property("rol") == "total_tabla_bs"

    # Solo un metodo con monto > 0 → su nombre legible.
    def test_metodo_pago_solo_con_efectivo_usd(self, qtbot: QtBot, session: Session) -> None:
        """Solo un metodo con monto > 0 → su nombre legible."""
        venta = self._venta(1, "F-0001", "COMPLETADA")
        venta.efectivo_usd = Decimal("2.50")
        venta.transferencia = Decimal("0.00")
        paginas = [
            self._pagina(session, "ADMINISTRADOR", [venta]),
            self._pagina(session, "ADMINISTRADOR", [venta]),
        ]
        for pagina in paginas:
            qtbot.addWidget(pagina)

        item = paginas[0].tabla_ventas.item(0, 4)
        assert item is not None
        assert item.text() == "Efectivo USD"
        assert item.toolTip() == ""

    # Dos metodos → 'Pago Mixto (A + B)' en la celda y en el tooltip.
    @pytest.mark.aceptacion
    def test_metodo_pago_resumen_mixto_corto(self, qtbot: QtBot, session: Session) -> None:
        """Dos metodos → 'Pago Mixto (A + B)' en la celda y en el tooltip."""
        venta = self._venta(1, "F-0001", "COMPLETADA")
        venta.efectivo_bs = Decimal("50.00")
        venta.pago_movil = Decimal("50.00")
        venta.transferencia = Decimal("0.00")
        pagina = self._pagina(session, "ADMINISTRADOR", [venta])
        qtbot.addWidget(pagina)

        item = pagina.tabla_ventas.item(0, 4)
        assert item is not None
        assert item.text() == "Pago Mixto (Efectivo Bs + Pago Movil)"
        assert item.toolTip() == "Pago Mixto (Efectivo Bs + Pago Movil)"

    # Tres o mas metodos → celda 'Pago Mixto' + tooltip con detalle.
    @pytest.mark.aceptacion
    def test_metodo_pago_mixto_largo_resume_con_tooltip(
        self, qtbot: QtBot, session: Session
    ) -> None:
        """Tres o mas metodos → celda 'Pago Mixto' + tooltip con detalle."""
        venta = self._venta(1, "F-0001", "COMPLETADA")
        venta.efectivo_bs = Decimal("25.00")
        venta.efectivo_usd = Decimal("0.80")
        venta.tarjeta = Decimal("25.00")
        venta.pago_movil = Decimal("25.00")
        venta.transferencia = Decimal("0.00")
        pagina = self._pagina(session, "ADMINISTRADOR", [venta])
        qtbot.addWidget(pagina)

        item = pagina.tabla_ventas.item(0, 4)
        assert item is not None
        assert item.text() == "Pago Mixto"
        assert item.toolTip() == ("Pago Mixto (Efectivo Bs + Efectivo USD + Tarjeta + Pago Movil)")

    # Venta sin pagos registrados (ventas viejas) → '-' en la celda.
    def test_metodo_pago_sin_desglose_muestra_guion(self, qtbot: QtBot, session: Session) -> None:
        """Venta sin pagos registrados (ventas viejas) → '-' en la celda."""
        venta = self._venta(1, "F-0001", "COMPLETADA")
        venta.efectivo_bs = Decimal("0.00")
        venta.efectivo_usd = Decimal("0.00")
        venta.tarjeta = Decimal("0.00")
        venta.pago_movil = Decimal("0.00")
        venta.bio_pago = Decimal("0.00")
        venta.transferencia = Decimal("0.00")
        pagina = self._pagina(session, "ADMINISTRADOR", [venta])
        qtbot.addWidget(pagina)

        item = pagina.tabla_ventas.item(0, 4)
        assert item is not None
        assert item.text() == "-"

    # Se puede abrir la caja con fondo inicial 0 (dialogo ya impide negativos).
    @pytest.mark.aceptacion
    def test_abrir_caja_con_fondo_cero(
        self, qtbot: QtBot, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Se puede abrir la caja con fondo inicial 0 (dialogo ya impide negativos)."""
        pagina = self._pagina(session, "ADMINISTRADOR", [])
        qtbot.addWidget(pagina)

        mock_getdouble = MagicMock(return_value=(0.0, True))
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QInputDialog.getDouble",
            mock_getdouble,
        )
        mock_abrir = MagicMock()
        mock_abrir.return_value.monto_apertura_bs = Decimal("0.00")
        monkeypatch.setattr(pagina.caja_service, "abrir_caja", mock_abrir)
        mock_info = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.information",
            mock_info,
        )
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.warning",
            mock_warning,
        )

        pagina._on_abrir_caja()

        mock_abrir.assert_called_once_with(Decimal("0.0"), 1)
        mock_info.assert_called_once()
        mock_warning.assert_not_called()


class TestDialogoAnulacion:
    """Pruebas del DialogoAnulacion (doble autorizacion para anular)."""

    pytestmark = pytest.mark.unitarias

    # Crea un DialogoAnulacion de prueba con el servicio mockeado.
    @staticmethod
    def _dialogo(qtbot: QtBot, auth_service: MagicMock) -> DialogoAnulacion:
        dialogo = DialogoAnulacion(auth_service=auth_service, numero_factura="F-0001")
        qtbot.addWidget(dialogo)
        return dialogo

    # Sin motivo, el boton Anular Venta esta deshabilitado.
    def test_motivo_vacio_deshabilita_anular(self, qtbot: QtBot) -> None:
        """Sin motivo, el boton Anular Venta esta deshabilitado."""
        dialogo = DialogoAnulacion(auth_service=MagicMock())
        qtbot.addWidget(dialogo)

        assert not dialogo.btn_anular.isEnabled()

        dialogo.txt_motivo.setText("cliente devolvio el producto")
        assert dialogo.btn_anular.isEnabled()

        dialogo.txt_motivo.clear()
        assert not dialogo.btn_anular.isEnabled()

    # Usuario/contrasena mal: aviso generico y el dialogo NO se cierra.
    @pytest.mark.aceptacion
    def test_credenciales_incorrectas_no_cierran_el_dialogo(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Usuario/contrasena mal: aviso generico y el dialogo NO se cierra."""
        auth_service = MagicMock()
        auth_service.verificar_login.return_value = None
        dialogo = self._dialogo(qtbot, auth_service)

        mock_aviso = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.dialogo_anulacion.QMessageBox.warning",
            mock_aviso,
        )

        dialogo.txt_motivo.setText("prueba")
        dialogo.txt_usuario.setText("jefa")
        dialogo.txt_contrasena.setText("incorrecta123")
        dialogo._validar()

        mock_aviso.assert_called_once()
        mensaje = mock_aviso.call_args.args[2]
        assert "incorrectos" in mensaje
        assert dialogo.usuario_autorizante() is None
        assert dialogo.result() != QDialog.DialogCode.Accepted

    # Un VENDEDOR no tiene permisos para anular (rol sera credencial).
    @pytest.mark.aceptacion
    def test_usuario_no_administrador_no_puede_anular(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un VENDEDOR no tiene permisos para anular (rol sera credencial)."""
        vendedor = Usuario(
            id=2,
            usuario="cajero",
            contrasena="x",
            rol="VENDEDOR",
            activo=True,
        )
        auth_service = MagicMock()
        auth_service.verificar_login.return_value = vendedor
        dialogo = self._dialogo(qtbot, auth_service)

        mock_aviso = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.dialogo_anulacion.QMessageBox.warning",
            mock_aviso,
        )

        dialogo.txt_motivo.setText("prueba")
        dialogo.txt_usuario.setText("cajero")
        dialogo.txt_contrasena.setText("secreta")
        dialogo._validar()

        mock_aviso.assert_called_once()
        mensaje = mock_aviso.call_args.args[2]
        assert "Solo un administrador" in mensaje
        assert dialogo.usuario_autorizante() is None

    # Con credenciales validas de admin, el dialogo se cierra con exito.
    @pytest.mark.aceptacion
    def test_admin_valido_acepta_con_motivo(self, qtbot: QtBot) -> None:
        """Con credenciales validas de admin, el dialogo se cierra con exito."""
        admin = Usuario(
            id=1,
            usuario="jefa",
            contrasena="x",
            rol="ADMINISTRADOR",
            activo=True,
        )
        auth_service = MagicMock()
        auth_service.verificar_login.return_value = admin
        dialogo = self._dialogo(qtbot, auth_service)

        dialogo.txt_motivo.setText("doble facturacion")
        dialogo.txt_usuario.setText("jefa")
        dialogo.txt_contrasena.setText("clave-admin")
        dialogo._validar()

        assert dialogo.result() == QDialog.DialogCode.Accepted
        assert dialogo.motivo() == "doble facturacion"
        assert dialogo.usuario_autorizante() is admin

    # Cancelar el dialogo deja motivo y autorizante vacios.
    def test_cancelar_no_registra_autorizacion(self, qtbot: QtBot) -> None:
        """Cancelar el dialogo deja motivo y autorizante vacios."""
        dialogo = DialogoAnulacion(auth_service=MagicMock())
        qtbot.addWidget(dialogo)

        dialogo.reject()

        assert dialogo.result() != QDialog.DialogCode.Accepted
        assert dialogo.motivo() == ""
        assert dialogo.usuario_autorizante() is None


class TestCierreCajaPagina:
    """Pruebas del boton Cerrar Caja (flujo de arqueo)."""

    pytestmark = pytest.mark.integracion

    # Flujo completo: arqueo aceptado y la caja queda CERRADA.
    @pytest.mark.aceptacion
    def test_boton_cerrar_caja_cierra_la_caja(
        self,
        qtbot: QtBot,
        usuario_admin: Usuario,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Flujo completo: arqueo aceptado y la caja queda CERRADA."""
        pagina = VentasPagina(
            usuario_actual=usuario_admin,
            controlador_ventas=MagicMock(),
            controlador_productos=MagicMock(),
            caja_service=CajaService(db_session=session),
        )
        qtbot.addWidget(pagina)

        caja_service = pagina.caja_service
        caja_service.abrir_caja(Decimal("100.00"), 1)
        pagina._actualizar_estado_caja()

        monkeypatch.setattr(pagina, "_pedir_billetes_bs", lambda: Decimal("100.00"))
        monkeypatch.setattr(pagina, "_pedir_billetes_usd", lambda: Decimal("10.00"))
        monkeypatch.setattr(
            pagina, "_pedir_observaciones_cierre", lambda: (True, "cierre de prueba")
        )
        mock_informacion = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.information",
            mock_informacion,
        )

        pagina.btn_cerrar_caja.click()

        assert caja_service.obtener_caja_abierta() is None
        mock_informacion.assert_called_once()
        mensaje = mock_informacion.call_args.args[2]
        assert "cerrada correctamente" in mensaje

    # Si el usuario cancela el primer dialogo, la caja sigue ABIERTA.
    @pytest.mark.aceptacion
    def test_cancelar_el_arqueo_no_cierra_la_caja(
        self,
        qtbot: QtBot,
        usuario_admin: Usuario,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Si el usuario cancela el primer dialogo, la caja sigue ABIERTA."""
        pagina = VentasPagina(
            usuario_actual=usuario_admin,
            controlador_ventas=MagicMock(),
            controlador_productos=MagicMock(),
            caja_service=CajaService(db_session=session),
        )
        qtbot.addWidget(pagina)

        caja_service = pagina.caja_service
        caja_service.abrir_caja(Decimal("100.00"), 1)
        pagina._actualizar_estado_caja()

        monkeypatch.setattr(pagina, "_pedir_billetes_bs", lambda: None)
        mock_informacion = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.information",
            mock_informacion,
        )
        mock_critico = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.critical",
            mock_critico,
        )

        pagina.btn_cerrar_caja.click()

        assert caja_service.obtener_caja_abierta() is not None
        mock_informacion.assert_not_called()
        mock_critico.assert_not_called()

    # Cerrar Caja sin caja abierta: aviso claro, sin error.
    def test_cerrar_sin_caja_abierta_muestra_aviso(
        self,
        qtbot: QtBot,
        usuario_admin: Usuario,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Cerrar Caja sin caja abierta: aviso claro, sin error."""
        pagina = VentasPagina(
            usuario_actual=usuario_admin,
            controlador_ventas=MagicMock(),
            controlador_productos=MagicMock(),
            caja_service=CajaService(db_session=session),
        )
        qtbot.addWidget(pagina)

        mock_aviso = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.warning",
            mock_aviso,
        )

        pagina._on_cerrar_caja()

        mock_aviso.assert_called_once()
        mensaje = mock_aviso.call_args.args[2]
        assert "No hay caja abierta" in mensaje

    # El reporte se regenera APARTE: su fallo no debe parecer un fallo del cierre.
    @pytest.mark.aceptacion
    def test_si_el_reporte_falla_la_caja_ya_quedo_cerrada(
        self,
        qtbot: QtBot,
        usuario_admin: Usuario,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """El reporte se regenera APARTE: su fallo no debe parecer un fallo del cierre."""
        reporte_fallido = MagicMock()
        reporte_fallido.generar_reporte.side_effect = RuntimeError("reporte roto")
        pagina = VentasPagina(
            usuario_actual=usuario_admin,
            controlador_ventas=MagicMock(),
            controlador_productos=MagicMock(),
            caja_service=CajaService(db_session=session),
            reporte_service=reporte_fallido,  # type: ignore[arg-type]
        )
        qtbot.addWidget(pagina)

        caja_service = pagina.caja_service
        caja_service.abrir_caja(Decimal("100.00"), 1)
        pagina._actualizar_estado_caja()

        monkeypatch.setattr(pagina, "_pedir_billetes_bs", lambda: Decimal("100.00"))
        monkeypatch.setattr(pagina, "_pedir_billetes_usd", lambda: Decimal("0.00"))
        monkeypatch.setattr(pagina, "_pedir_observaciones_cierre", lambda: (True, None))
        mock_informacion = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.information",
            mock_informacion,
        )
        mock_aviso = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.warning",
            mock_aviso,
        )
        mock_registrar = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.registrar_excepcion",
            mock_registrar,
        )

        pagina.btn_cerrar_caja.click()

        assert caja_service.obtener_caja_abierta() is None
        mock_informacion.assert_called_once()
        mock_aviso.assert_called_once()
        mensaje = mock_aviso.call_args.args[2]
        assert "no se pudo regenerar el reporte" in mensaje
        mock_registrar.assert_called_once()


class TestSalidaConCajaAbierta:
    """Pruebas del bloqueo de salida cuando hay una caja abierta."""

    pytestmark = pytest.mark.sistema

    # Sin caja abierta la ventana se cierra sin preguntar nada.
    def test_salida_normal_sin_caja_abierta(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin caja abierta la ventana se cierra sin preguntar nada."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(ventana.controlador_caja, "obtener_caja_abierta", lambda: None)

        evento = QCloseEvent()
        ventana.closeEvent(evento)

        assert evento.isAccepted()

    # Con caja abierta y respuesta No, se cancela la salida y se navega a Ventas.
    def test_con_caja_abierta_ir_a_cerrar_cancela_la_salida(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Con caja abierta y respuesta No, se cancela la salida y se navega a Ventas."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(
            ventana.controlador_caja,
            "obtener_caja_abierta",
            lambda: Caja(monto_apertura_bs=Decimal("250.00"), usuario_id=1),
        )
        mock_question = MagicMock(return_value=QMessageBox.StandardButton.No)
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.QMessageBox.question",
            mock_question,
        )

        evento = QCloseEvent()
        ventana.closeEvent(evento)

        assert not evento.isAccepted()
        assert ventana.paginas.currentIndex() == 0
        assert ventana.paginas.currentWidget() is ventana.pagina_ventas

    # Forzar la salida exige confirmar DOS veces (Si + Si).
    def test_fuerza_la_salida_con_doble_confirmacion(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Forzar la salida exige confirmar DOS veces (Si + Si)."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(
            ventana.controlador_caja,
            "obtener_caja_abierta",
            lambda: Caja(monto_apertura_bs=Decimal("250.00"), usuario_id=1),
        )
        mock_question = MagicMock(return_value=QMessageBox.StandardButton.Yes)
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.QMessageBox.question",
            mock_question,
        )

        evento = QCloseEvent()
        ventana.closeEvent(evento)

        assert evento.isAccepted()
        assert mock_question.call_count == 2

    # Primera respuesta Si pero segunda No: la salida se cancela.
    def test_cancela_en_la_segunda_confirmacion(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Primera respuesta Si pero segunda No: la salida se cancela."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(
            ventana.controlador_caja,
            "obtener_caja_abierta",
            lambda: Caja(monto_apertura_bs=Decimal("250.00"), usuario_id=1),
        )
        mock_question = MagicMock(
            side_effect=[
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.Yes,
            ]
        )
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.QMessageBox.question",
            mock_question,
        )

        evento = QCloseEvent()
        ventana.closeEvent(evento)

        assert mock_question.call_count == 2
        assert not evento.isAccepted()

    # Si consultar la caja falla, NO bloquear la salida (evita quedar atrapado).
    def test_error_al_consultar_caja_no_bloquea_la_salida(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Si consultar la caja falla, NO bloquear la salida (evita quedar atrapado)."""

        # Simula que la consulta de caja falla.
        def _fallar_consulta_caja() -> object:
            raise RuntimeError("caja rota")

        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(
            ventana.controlador_caja,
            "obtener_caja_abierta",
            _fallar_consulta_caja,
        )
        mock_registrar = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.registrar_excepcion",
            mock_registrar,
        )

        evento = QCloseEvent()
        ventana.closeEvent(evento)

        assert evento.isAccepted()
        mock_registrar.assert_called_once()


class TestCerrarSesion:
    pytestmark = pytest.mark.sistema

    # La cabecera lleva el boton 'Cerrar Sesion' con rol cabecera_salir.
    def test_boton_existe_en_la_cabecera(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """La cabecera lleva el boton 'Cerrar Sesion' con rol cabecera_salir."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        assert hasattr(ventana, "btn_cerrar_sesion")
        assert ventana.btn_cerrar_sesion.text() == "Cerrar Sesion"
        assert ventana.btn_cerrar_sesion.property("rol") == "cabecera_salir"

    # Caja cerrada: el cierre se autoriza sin preguntar y se emite la.
    def test_logout_sin_caja_abierta_emite_senal_y_cierra(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Caja cerrada: el cierre se autoriza sin preguntar y se emite la."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(ventana.controlador_caja, "obtener_caja_abierta", lambda: None)
        mock_question = MagicMock()
        monkeypatch.setattr("sistema_financiero.ui.interfaz.QMessageBox.question", mock_question)
        mock_close = MagicMock()
        monkeypatch.setattr(ventana, "close", mock_close)
        receptor = MagicMock()
        ventana.sesion_cerrada.connect(receptor)

        ventana._cerrar_sesion()

        receptor.assert_called_once()
        mock_close.assert_called_once()
        mock_question.assert_not_called()
        assert ventana._cierre_autorizado is True

    # El clic real en el boton ejecuta el mismo flujo (caja cerrada).
    def test_logout_clic_boton_emite_senal(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """El clic real en el boton ejecuta el mismo flujo (caja cerrada)."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(ventana.controlador_caja, "obtener_caja_abierta", lambda: None)
        receptor = MagicMock()
        ventana.sesion_cerrada.connect(receptor)

        ventana.btn_cerrar_sesion.click()

        receptor.assert_called_once()

    # Caja abierta y 'No': se cancela el logout y se navega a Ventas.
    def test_logout_con_caja_abierta_y_no_redirige_a_ventas(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Caja abierta y 'No': se cancela el logout y se navega a Ventas."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(
            ventana.controlador_caja,
            "obtener_caja_abierta",
            lambda: Caja(monto_apertura_bs=Decimal("250.00"), usuario_id=1),
        )
        mock_question = MagicMock(return_value=QMessageBox.StandardButton.No)
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.QMessageBox.question",
            mock_question,
        )
        receptor = MagicMock()
        ventana.sesion_cerrada.connect(receptor)

        ventana._cerrar_sesion()

        receptor.assert_not_called()
        assert ventana.paginas.currentIndex() == 0
        assert ventana.paginas.currentWidget() is ventana.pagina_ventas

    # Admin: caja abierta y 'No' navega a Ventas en la fila 1 del menu.
    def test_logout_con_caja_abierta_y_no_redirige_a_ventas_admin(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Admin: caja abierta y 'No' navega a Ventas en la fila 1 del menu."""
        admin = Usuario(
            id=1,
            usuario="admin",
            contrasena="hash_falso",
            nombre_completo="Administrador",
            activo=True,
            rol="ADMINISTRADOR",
        )
        ventana = VentanaPrincipal(admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(
            ventana.controlador_caja,
            "obtener_caja_abierta",
            lambda: Caja(monto_apertura_bs=Decimal("250.00"), usuario_id=1),
        )
        mock_question = MagicMock(return_value=QMessageBox.StandardButton.No)
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.QMessageBox.question",
            mock_question,
        )
        receptor = MagicMock()
        ventana.sesion_cerrada.connect(receptor)

        ventana._cerrar_sesion()

        receptor.assert_not_called()
        assert ventana._indice_ventas == 1
        assert ventana.paginas.currentIndex() == 1
        assert ventana.paginas.currentWidget() is ventana.pagina_ventas

    # Caja abierta y 'Si + Si': se autoriza el logout.
    def test_logout_con_caja_abierta_y_doble_confirmacion_emite(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Caja abierta y 'Si + Si': se autoriza el logout."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(
            ventana.controlador_caja,
            "obtener_caja_abierta",
            lambda: Caja(monto_apertura_bs=Decimal("250.00"), usuario_id=1),
        )
        mock_question = MagicMock(return_value=QMessageBox.StandardButton.Yes)
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.QMessageBox.question",
            mock_question,
        )
        receptor = MagicMock()
        ventana.sesion_cerrada.connect(receptor)

        ventana._cerrar_sesion()

        receptor.assert_called_once()
        assert mock_question.call_count == 2

    # Caja abierta y 'Si + No': el logout se cancela en la 2a confirmacion.
    def test_logout_con_caja_abierta_si_y_no_no_emite(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Caja abierta y 'Si + No': el logout se cancela en la 2a confirmacion."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(
            ventana.controlador_caja,
            "obtener_caja_abierta",
            lambda: Caja(monto_apertura_bs=Decimal("250.00"), usuario_id=1),
        )
        mock_question = MagicMock(
            side_effect=[
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.Yes,
            ]
        )
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.QMessageBox.question",
            mock_question,
        )
        receptor = MagicMock()
        ventana.sesion_cerrada.connect(receptor)

        ventana._cerrar_sesion()

        receptor.assert_not_called()
        assert ventana._cierre_autorizado is False

    # Tras autorizar el logout, el close() resultante NO repregunta.
    def test_closeevent_tras_logout_no_vuelve_a_preguntar(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tras autorizar el logout, el close() resultante NO repregunta."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(
            ventana.controlador_caja,
            "obtener_caja_abierta",
            lambda: Caja(monto_apertura_bs=Decimal("250.00"), usuario_id=1),
        )
        mock_question = MagicMock(return_value=QMessageBox.StandardButton.Yes)
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.QMessageBox.question",
            mock_question,
        )
        ventana._cierre_autorizado = True

        evento = QCloseEvent()
        ventana.closeEvent(evento)

        assert evento.isAccepted()
        mock_question.assert_not_called()


class TestRefrescoPostVenta:
    pytestmark = pytest.mark.integracion

    # Ventana con caja abierta y FormularioVenta reemplazado por un mock.
    def _ventana_con_pos_falso(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> VentanaPrincipal:
        """Ventana con caja abierta y FormularioVenta reemplazado por un mock."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(
            ventana.controlador_caja,
            "obtener_caja_abierta",
            lambda: Caja(monto_apertura_bs=Decimal("250.00"), usuario_id=1),
        )
        dialogo = MagicMock()
        dialogo.exec.return_value = QDialog.DialogCode.Accepted
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.FormularioVenta",
            MagicMock(return_value=dialogo),
        )
        return ventana

    # Tras cobrar (Accepted) se refresca la tabla de ventas y la caja.
    @pytest.mark.aceptacion
    def test_venta_aceptada_refresca_tabla_y_estado_de_caja(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tras cobrar (Accepted) se refresca la tabla de ventas y la caja."""
        ventana = self._ventana_con_pos_falso(qtbot, usuario_admin, monkeypatch)
        spy_cargar = MagicMock()
        monkeypatch.setattr(ventana.pagina_ventas, "cargar", spy_cargar)
        spy_indicador = MagicMock()
        monkeypatch.setattr(ventana, "_actualizar_indicador_caja", spy_indicador)
        mock_warning = MagicMock()
        monkeypatch.setattr("sistema_financiero.ui.interfaz.QMessageBox.warning", mock_warning)

        ventana._nueva_venta()

        spy_cargar.assert_called_once_with()
        spy_indicador.assert_called_once_with()
        mock_warning.assert_not_called()

    # El refresco no puede fallar en silencio: se registra y se avisa.
    @pytest.mark.aceptacion
    def test_fallo_de_refresco_se_registra_y_avisa(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """El refresco no puede fallar en silencio: se registra y se avisa."""
        ventana = self._ventana_con_pos_falso(qtbot, usuario_admin, monkeypatch)
        spy_cargar = MagicMock(side_effect=RuntimeError("boom de prueba"))
        monkeypatch.setattr(ventana.pagina_ventas, "cargar", spy_cargar)
        monkeypatch.setattr(ventana, "_actualizar_indicador_caja", MagicMock())
        mock_registrar = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.registrar_excepcion",
            mock_registrar,
        )
        mock_warning = MagicMock()
        monkeypatch.setattr("sistema_financiero.ui.interfaz.QMessageBox.warning", mock_warning)

        ventana._nueva_venta()

        mock_registrar.assert_called_once()
        assert "refresco post-venta" in mock_registrar.call_args.args[1]
        mock_warning.assert_called_once()
        _, titulo, mensaje = mock_warning.call_args.args
        assert titulo == "Refresco"
        assert "La venta se registro correctamente" in mensaje

    # Si el POS se cierra sin cobrar (Rejected) no hay refresco.
    @pytest.mark.aceptacion
    def test_venta_cancelada_no_refresca(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Si el POS se cierra sin cobrar (Rejected) no hay refresco."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        monkeypatch.setattr(
            ventana.controlador_caja,
            "obtener_caja_abierta",
            lambda: Caja(monto_apertura_bs=Decimal("250.00"), usuario_id=1),
        )
        dialogo = MagicMock()
        dialogo.exec.return_value = QDialog.DialogCode.Rejected
        monkeypatch.setattr(
            "sistema_financiero.ui.interfaz.FormularioVenta",
            MagicMock(return_value=dialogo),
        )
        spy_cargar = MagicMock()
        monkeypatch.setattr(ventana.pagina_ventas, "cargar", spy_cargar)

        ventana._nueva_venta()

        spy_cargar.assert_not_called()


class TestDialogoFactura:
    """Pruebas de la factura: HTML puro + dialogo con Imprimir/PDF/Cerrar."""

    pytestmark = pytest.mark.integracion

    # Crea un item de la factura de prueba.
    @staticmethod
    def _item(
        nombre: str = "Premium",
        cantidad: str = "0.5",
        tipo_venta: str = "UNIDAD",
    ) -> dict[str, object]:
        return {
            "nombre": nombre,
            "cantidad": Decimal(cantidad),
            "tipo_venta": tipo_venta,
            "precio": Decimal("853.50"),
            "subtotal": Decimal("426.75"),
        }

    # Crea un pago de la factura de prueba.
    @staticmethod
    def _pago(
        monto: str = "100.00",
        monto_bs: str = "100.00",
        vuelto: str = "0.00",
        referencia: str = "",
    ) -> dict[str, object]:
        return {
            "metodo": METODO_PAGO_EFECTIVO_BS,
            "moneda": MONEDA_BS,
            "monto": Decimal(monto),
            "monto_bs": Decimal(monto_bs),
            "vuelto_bs": Decimal(vuelto),
            "referencia": referencia,
        }

    # Crea un DialogoFactura de prueba con datos fijos.
    @staticmethod
    def _dialogo() -> DialogoFactura:
        return DialogoFactura(
            numero_factura="F-0001",
            fecha_venta=datetime(2026, 9, 25, 14, 30),
            nombre_cajero="Maria",
            tasa_venta=Decimal("853.50"),
            total_bs=Decimal("426.75"),
            total_usd=Decimal("0.50"),
            items=[TestDialogoFactura._item()],
            pagos=[TestDialogoFactura._pago()],
        )

    # Prueba que el HTML de la factura trae los datos basicos.
    def test_generar_html_contiene_datos_basicos(self) -> None:
        html_doc = generar_html_factura(
            numero_factura="F-0001",
            fecha_local=datetime(2026, 9, 25, 14, 30),
            nombre_cajero="Maria",
            tasa_venta=Decimal("853.50"),
            total_bs=Decimal("426.75"),
            total_usd=Decimal("0.50"),
            items=[self._item(), self._item("Pan")],
            pagos=[self._pago()],
        )
        assert html.escape(NOMBRE_NEGOCIO) in html_doc
        assert "FACTURA F-0001" in html_doc
        assert "Cajero: Maria" in html_doc
        assert "25/09/2026 14:30" in html_doc
        assert "0,5" in html_doc
        assert "TOTAL 426,75 Bs." in html_doc
        assert "Tasa usada: 853,50 Bs. / USD" in html_doc
        assert "Equivalente USD: 0.50 $" in html_doc
        assert "Efectivo Bs" in html_doc
        assert "Gracias por su compra" in html_doc

    # La factura imprime el peso en palabras, no el crudo en kg.
    @pytest.mark.parametrize(
        ("cantidad", "esperado"),
        [
            ("1.500", "1 kg y 500 g"),
            ("0.999", "999 g"),
            ("2.000", "2 kg"),
        ],
    )
    def test_generar_html_muestra_el_peso_legible(self, cantidad: str, esperado: str) -> None:
        """La factura imprime el peso en palabras, no el crudo en kg."""
        html_doc = generar_html_factura(
            numero_factura="F-0001",
            fecha_local=datetime(2026, 9, 25, 14, 30),
            nombre_cajero="Maria",
            tasa_venta=Decimal("853.50"),
            total_bs=Decimal("426.75"),
            total_usd=Decimal("0.50"),
            items=[self._item("Carne molida", cantidad, "PESO")],
            pagos=[self._pago()],
        )
        assert f"<td>{esperado}</td>" in html_doc
        assert f"<td>{cantidad}</td>" not in html_doc

    # Una fila antigua con tipo_venta GRAMOS tambien se lee en kg/g.
    def test_generar_html_muestra_el_peso_legacy_gramos(self) -> None:
        """Una fila antigua con tipo_venta GRAMOS tambien se lee en kg/g."""
        html_doc = generar_html_factura(
            numero_factura="F-0001",
            fecha_local=datetime(2026, 9, 25, 14, 30),
            nombre_cajero="Maria",
            tasa_venta=Decimal("853.50"),
            total_bs=Decimal("426.75"),
            total_usd=Decimal("0.50"),
            items=[self._item("Queso blanco", "0.250", "GRAMOS")],
            pagos=[self._pago()],
        )
        assert "<td>250 g</td>" in html_doc

    # Prueba que el HTML escapa textos y maneja nulos.
    def test_generar_html_escapa_textos_y_nulos(self) -> None:
        html_doc = generar_html_factura(
            numero_factura=None,
            fecha_local=datetime(2026, 9, 25, 8, 0),
            nombre_cajero=None,
            tasa_venta=None,
            total_bs=Decimal("0.00"),
            total_usd=Decimal("0.00"),
            items=[self._item("Huevo & <Harina>")],
            pagos=[
                {
                    "metodo": METODO_PAGO_EFECTIVO_BS,
                    "moneda": MONEDA_BS,
                    "monto": Decimal("1.00"),
                    "monto_bs": Decimal("1.00"),
                    "vuelto_bs": Decimal("0.00"),
                    "referencia": "<ref> & #1",
                }
            ],
        )
        assert "&lt;Harina&gt;" in html_doc
        assert "<Harina>" not in html_doc
        assert "&amp;" in html_doc
        assert "FACTURA -" in html_doc
        assert "Cajero: -" in html_doc
        assert "Tasa usada" not in html_doc
        assert "Equivalente USD" not in html_doc

    # Prueba que el vuelto solo se muestra si existe.
    def test_generar_html_vuelto_visible_solo_si_hay(self) -> None:
        html_con_vuelto = generar_html_factura(
            numero_factura="F-0001",
            fecha_local=datetime(2026, 9, 25, 8, 0),
            nombre_cajero=None,
            tasa_venta=None,
            total_bs=Decimal("100.00"),
            total_usd=Decimal("0.00"),
            items=[self._item()],
            pagos=[self._pago(monto="100.20", vuelto="0.20")],
        )
        assert "0,20 Bs." in html_con_vuelto

        html_sin_vuelto = generar_html_factura(
            numero_factura="F-0001",
            fecha_local=datetime(2026, 9, 25, 8, 0),
            nombre_cajero=None,
            tasa_venta=None,
            total_bs=Decimal("100.00"),
            total_usd=Decimal("0.00"),
            items=[self._item()],
            pagos=[self._pago()],
        )
        assert '<td align="right">-</td>' in html_sin_vuelto
        assert "0,20" not in html_sin_vuelto

    # Prueba que el dialogo muestra preview y botones.
    def test_dialogo_muestra_preview_con_botones(self, qtbot: QtBot) -> None:
        dialogo = self._dialogo()
        qtbot.addWidget(dialogo)

        assert "FACTURA F-0001" in dialogo.preview.toHtml()
        assert NOMBRE_NEGOCIO in dialogo.preview.toHtml()
        assert dialogo.btn_imprimir.text() == "Imprimir…"
        assert dialogo.btn_imprimir.property("rol") == "primario"
        assert dialogo.btn_pdf.text() == "Guardar PDF…"
        assert dialogo.btn_pdf.property("rol") == "secundario"
        assert dialogo.btn_cerrar.text() == "Cerrar"

    # Prueba que Guardar PDF escribe un archivo real.
    @pytest.mark.aceptacion
    def test_guardar_pdf_escribe_archivo_real(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        dialogo = self._dialogo()
        qtbot.addWidget(dialogo)
        destino = tmp_path / "factura_F-0001.pdf"
        monkeypatch.setattr(
            "sistema_financiero.ui.dialogo_factura.QFileDialog.getSaveFileName",
            lambda *_args, **_kwargs: (str(destino), "PDF (*.pdf)"),
        )

        dialogo._guardar_pdf()

        assert destino.exists()
        assert destino.stat().st_size > 100
        with destino.open("rb") as f:
            assert f.read(4) == b"%PDF"

    # Prueba que cancelar el PDF no crea archivos.
    def test_guardar_pdf_cancelado_no_crea_nada(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        dialogo = self._dialogo()
        qtbot.addWidget(dialogo)
        monkeypatch.setattr(
            "sistema_financiero.ui.dialogo_factura.QFileDialog.getSaveFileName",
            lambda *_args, **_kwargs: ("", ""),
        )

        dialogo._guardar_pdf()

        assert not list(tmp_path.iterdir())

    # Prueba que imprimir envia el documento a la impresora.
    def test_imprimir_envia_documento_a_la_impresora(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dialogo = self._dialogo()
        qtbot.addWidget(dialogo)
        printer_mock = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.dialogo_factura.QPrinter",
            MagicMock(return_value=printer_mock),
        )
        dialogo_impresion = MagicMock()
        dialogo_impresion.exec.return_value = QDialog.DialogCode.Accepted
        monkeypatch.setattr(
            "sistema_financiero.ui.dialogo_factura.QPrintDialog",
            MagicMock(return_value=dialogo_impresion),
        )
        doc_mock = MagicMock()
        monkeypatch.setattr(dialogo, "_documento", MagicMock(return_value=doc_mock))

        dialogo._imprimir()

        dialogo_impresion.exec.assert_called_once()
        doc_mock.print.assert_called_once_with(printer_mock)

    # Prueba que cancelar la impresion no envia nada.
    def test_imprimir_cancelado_envia_nada(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dialogo = self._dialogo()
        qtbot.addWidget(dialogo)
        printer_mock = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.dialogo_factura.QPrinter",
            MagicMock(return_value=printer_mock),
        )
        dialogo_impresion = MagicMock()
        dialogo_impresion.exec.return_value = QDialog.DialogCode.Rejected
        monkeypatch.setattr(
            "sistema_financiero.ui.dialogo_factura.QPrintDialog",
            MagicMock(return_value=dialogo_impresion),
        )
        doc_mock = MagicMock()
        monkeypatch.setattr(dialogo, "_documento", MagicMock(return_value=doc_mock))

        dialogo._imprimir()

        dialogo_impresion.exec.assert_called_once()
        doc_mock.print.assert_not_called()


class _ResultadoVacio:
    # Devuelve una lista vacia (sin resultados).
    def all(self) -> list:
        return []


class _SesionVacia:
    # Entra en el contexto de la sesion vacia.
    def __enter__(self) -> _SesionVacia:
        return self

    # Cierra el contexto de la sesion sin efectos.
    def __exit__(self, *args: object) -> None:
        return None

    # Ejecuta cualquier consulta y devuelve un resultado vacio.
    def exec(self, _stmt: object) -> _ResultadoVacio:
        return _ResultadoVacio()


@pytest.mark.integracion
class TestDashboardRefrescoBcv:
    # El refresco del dashboard no toca la BD real en estos tests.
    @pytest.fixture(autouse=True)
    def _sin_bd_dashboard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """El refresco del dashboard no toca la BD real en estos tests."""
        monkeypatch.setattr(
            "sistema_financiero.ui.dashboard_pagina.obtener_sesion",
            _SesionVacia,
        )

    # Reemplaza _iniciar_fetch_bcv por un espia que marca el fetch activo.
    @staticmethod
    def _espia_fetch(monkeypatch: pytest.MonkeyPatch) -> list:
        """Reemplaza _iniciar_fetch_bcv por un espia que marca el fetch activo."""
        llamadas: list = []

        # Espia el fetch BCV y marca el estado de descarga activa.
        def _espia(self: DashboardPagina) -> None:
            llamadas.append(True)
            self._bcv_fetching = True

        monkeypatch.setattr(DashboardPagina, "_iniciar_fetch_bcv", _espia)
        return llamadas

    # Crea un DashboardPagina con un controlador de tasas mockeado.
    @staticmethod
    def _pagina(qtbot: QtBot, tasa: object) -> DashboardPagina:
        controlador = MagicMock()
        controlador.tasa_activa.return_value = tasa
        pagina = DashboardPagina(controlador)
        qtbot.addWidget(pagina)
        return pagina

    # Sin tasa BCV activa, refrescar() consulta aunque la ultima.
    def test_refrescar_sin_tasa_de_hoy_consulta(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin tasa BCV activa, refrescar() consulta aunque la ultima
        consulta haya sido hace un instante (la tasa es prioridad)."""
        llamadas = self._espia_fetch(monkeypatch)
        pagina = self._pagina(qtbot, tasa=None)
        pagina._ultima_consulta_bcv = ahora() - timedelta(seconds=5)
        pagina._bcv_fetching = False

        pagina.refrescar()

        assert len(llamadas) == 1
        assert pagina._bcv_fetching is True

    # Con la tasa de hoy presente y SIN intervalo cumplido, refrescar().
    def test_refrescar_dentro_del_intervalo_no_reconsulta(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Con la tasa de hoy presente y SIN intervalo cumplido, refrescar()
        no inicia otra consulta (navegar entre paginas no spammea la red)."""
        llamadas = self._espia_fetch(monkeypatch)
        pagina = self._pagina(
            qtbot,
            tasa=SimpleNamespace(fecha=hoy(), tasa_venta=Decimal("857.01")),
        )

        pagina.refrescar()
        assert len(llamadas) == 1
        pagina._bcv_fetching = False

        pagina.refrescar()
        assert len(llamadas) == 1

    # Tras el intervalo (10 min), refrescar() re-consulta aunque la.
    def test_refrescar_tras_intervalo_reconsulta(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tras el intervalo (10 min), refrescar() re-consulta aunque la
        tasa de hoy exista: la fila de hoy se puede actualizar en el dia."""
        llamadas = self._espia_fetch(monkeypatch)
        pagina = self._pagina(
            qtbot,
            tasa=SimpleNamespace(fecha=hoy(), tasa_venta=Decimal("857.01")),
        )
        pagina._ultima_consulta_bcv = ahora() - timedelta(
            seconds=INTERVALO_BCV_SEGUNDOS + 1,
        )
        pagina._bcv_fetching = False

        pagina.refrescar()

        assert len(llamadas) == 1
        assert pagina._bcv_fetching is True
