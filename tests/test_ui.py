# ============================================================
# ARCHIVO: tests/test_ui.py
# mypy: allow-untyped-calls = True
# ============================================================
# Tests para los componentes visuales (PyQt6) de la aplicacion.
#
# QUE PRUEBA:
#   - VentanaLogin: apertura, widgets, validacion de campos.
#   - VentanaPrincipal: creacion con usuario, navegacion, cambio de paginas.
#   - FormularioProducto: modo crear y editar, campos del formulario.
#   - FormularioVenta: apertura, widgets principales.
#
# REQUIERE: pytest-qt (proporciona el fixture "qtbot").
#
# El fixture "qtbot" permite:
#   - qtbot.addWidget(widget): registrar un widget para que pytest-qt
#     lo cierre/limpie automaticamente despues del test.
#   - qtbot.mouseClick(boton, ...): simular clics del mouse.
#   - qtbot.keyClicks(widget, texto): simular escritura de texto.
#   - qtbot.wait(...): esperar un tiempo o condicion.
#
# NOTA SOBRE LA BD:
#   Estos tests NO tocan la base de datos real.
#   Cuando un componente necesita datos (ej. productos en el combo),
#   usamos monkeypatch para simular las respuestas del controlador.
# ============================================================
import gc
import logging
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import bcrypt
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
)
from pytestqt.qtbot import QtBot
from sqlmodel import Session

# Importamos los componentes UI que vamos a probar.
from sistema_financiero.core.caja_service import CajaService
from sistema_financiero.models.modelos import Caja, Producto, Usuario
from sistema_financiero.ui.dashboard_pagina import DashboardPagina
from sistema_financiero.ui.formulario_cambio_contrasena import FormularioCambioContrasena
from sistema_financiero.ui.formulario_producto import FormularioProducto
from sistema_financiero.ui.formulario_venta import FormularioVenta

# NOTA: VentanaPrincipal se prueba con un fixture especial porque requiere
# un usuario real (objeto Usuario). Lo definimos abajo.
from sistema_financiero.ui.interfaz import VentanaPrincipal
from sistema_financiero.ui.inventario_pagina import InventarioPagina
from sistema_financiero.ui.usuarios_pagina import UsuariosPagina
from sistema_financiero.ui.ventana_login import VentanaLogin
from sistema_financiero.ui.ventas_pagina import VentasPagina
from sistema_financiero.utils import METODOS_PAGO

# ============================================================
# FIXTURES (compartidos entre los tests de este archivo)
# ============================================================
# Estos fixtures crean objetos reutilizables para los tests.
# A diferencia de conftest.py, estos son ESPECIFICOS de UI.
# ============================================================


@pytest.fixture()
def usuario_admin() -> Usuario:
    """Crea un objeto Usuario simulado (sin BD) para los tests de UI.

    Crea un Usuario como si fuera un registro de la BD, pero SIN
    guardarlo en ninguna base de datos. Solo existe en memoria para
    que VentanaPrincipal pueda usarlo al inicializarse.
    """
    return Usuario(
        id=1,
        usuario="admin",
        contrasena="hash_falso",
        nombre_completo="Administrador",
        activo=True,
    )


@pytest.fixture(autouse=True)
def _sin_fetch_bcv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evita que el dashboard consulte el BCV por red durante los tests de UI.

    DashboardPagina.refrescar() lanza un BcvFetchThread cuando no hay
    tasa registrada para hoy. En los tests de UI NO se debe tocar la
    red (el sandbox/CI la bloquea y el hilo QThread provoca un segfault
    nativo de Qt al cerrarse la ventana). Parcheamos el metodo que
    inicia el hilo para que sea un no-op.
    """

    def _iniciar_fetch_sin_red(self: DashboardPagina) -> None:
        self._bcv_fetching = False

    monkeypatch.setattr(DashboardPagina, "_iniciar_fetch_bcv", _iniciar_fetch_sin_red)


@pytest.fixture(autouse=True)
def _liberar_conexiones_sqlite() -> Iterator[None]:
    """Fuerza la recoleccion de sesiones de BD tras cada test de UI.

    Cada VentanaPrincipal abre varias Session de SQLModel (caja, ventas,
    productos, tasas, usuarios). Una Session forma ciclos de referencias,
    asi que la conexion solo vuelve al QueuePool cuando el recolector de
    basura la destruye. Sin forzar el GC, la suite acumula conexiones y
    agota el pool (size 5 + overflow 10) en los tests que crean ventanas:
    el fallo aparece como sqlalchemy TimeoutError tras 30s de espera.
    """
    yield
    gc.collect()


@pytest.fixture(autouse=True, scope="module")
def _sin_dialogos_reales_al_cerrar_ventana():
    """Evita modales reales cuando pytest-qt cierra VentanaPrincipal (teardown).

    VentanaPrincipal.closeEvent() pregunta por la caja abierta antes de
    cerrar. En el teardown de cada test, pytest-qt llama close() a las
    ventanas registradas y, si la BD real tuviera una caja ABIERTA, se
    abriria un QMessageBox REAL que bloquearia la suite.

    Este parche (scope module, autouse) dura MAS que cualquier teardown
    de test y responde "Si" a la confirmacion para que el cierre de
    teardown sea limpio. Los tests que necesitan respuestas especificas
    lo sobrescriben con su propio monkeypatch.
    """
    with patch(
        "sistema_financiero.ui.interfaz.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        yield


# ============================================================
# TESTS: VentanaLogin
# ============================================================
# Verificamos que el dialogo de login se crea correctamente,
# que tiene los campos esperados y que valida datos vacios.
# ============================================================


class TestVentanaLogin:
    """Pruebas para la ventana de inicio de sesion (VentanaLogin)."""

    def test_crear_dialogo(self, qtbot: QtBot) -> None:
        """Verifica que VentanaLogin se crea con el titulo correcto.

        Crea el dialogo y comprueba:
        - El titulo de la ventana contiene "Iniciar Sesion".
        - La ventana se puede cerrar (sin crashear).
        """
        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        # Verificar titulo de la ventana.
        assert "Iniciar Sesión" in dialogo.windowTitle()

    def test_widgets_existen(self, qtbot: QtBot) -> None:
        """Verifica que los widgets del login se crearon correctamente.

        Comprueba que los campos de texto y botones existen y son
        del tipo correcto. Esto asegura que _setup_ui() se ejecuto.
        """
        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        # Verificar que los atributos existen (los crea _setup_ui).
        assert hasattr(dialogo, "txt_usuario")
        assert hasattr(dialogo, "txt_contrasena")

        # Verificar que son del tipo correcto (QLineEdit).
        assert isinstance(dialogo.txt_usuario, QLineEdit)
        assert isinstance(dialogo.txt_contrasena, QLineEdit)

        # Verificar que la contrasena oculta el texto (EchoMode.Password).
        assert dialogo.txt_contrasena.echoMode() == QLineEdit.EchoMode.Password

    def test_validacion_campos_vacios(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que el login rechaza campos vacios.

        Simula hacer clic en "Ingresar" sin escribir nada y verifica
        que se muestra un mensaje de advertencia (QMessageBox.warning).

        monkeypatch: reemplazamos QMessageBox.warning por un mock
        para capturar la llamada sin mostrar la ventana emergente real.
        """
        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        # Reemplazar QMessageBox.warning con un MagicMock.
        # El mock registra que fue llamado pero no muestra la ventana.
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.QMessageBox.warning",
            mock_warning,
        )

        # Simular clic en el boton "Ingresar".
        # Buscamos el boton por su texto entre los hijos del dialogo.
        btn_ingresar = dialogo.findChild(QPushButton, "")
        assert btn_ingresar is not None

        qtbot.mouseClick(btn_ingresar, Qt.MouseButton.LeftButton)

        # Verificar que se llamo a QMessageBox.warning (hay campos vacios).
        mock_warning.assert_called_once()

    def test_validar_login_incorrecto(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que credenciales incorrectas muestran error.

        Escribe un usuario y contrasena que no existen en la BD y
        verifica que se muestra el mensaje de error.

        monkeypatch: reemplazamos obtener_sesion para que devuelva
        una sesion que no encuentra ningun usuario.
        """
        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        # Reemplazar QMessageBox.warning con mock.
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.QMessageBox.warning",
            mock_warning,
        )

        # Reemplazar obtener_sesion para que devuelva un context manager
        # con una sesion mockeada que no encuentra ningun usuario.
        # obtener_sesion es un context manager (usa "with obtener_sesion() as session").
        # Creamos un MagicMock que funciona como context manager usando __enter__.
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None

        class MockContextManager:
            def __enter__(self) -> MockContextManager:
                return mock_session

            def __exit__(self, *args: object) -> None:
                pass

        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.obtener_sesion",
            MockContextManager,
        )

        # Escribir credenciales que no existen.
        qtbot.keyClicks(dialogo.txt_usuario, "usuario_inexistente")
        qtbot.keyClicks(dialogo.txt_contrasena, "clave_incorrecta")

        # Hacer clic en Ingresar.
        btn_ingresar = dialogo.findChild(QPushButton, "")
        qtbot.mouseClick(btn_ingresar, Qt.MouseButton.LeftButton)

        # Verificar que se mostro el warning (credenciales incorrectas).
        mock_warning.assert_called_once()

    def test_login_sin_olvide_contrasena(self, qtbot: QtBot) -> None:
        """Verifica que NO existe el boton "olvide mi contrasena".

        Eliminado por seguridad: permite resetear credenciales sin
        identificarse (mala practica). El cambio de contrasena solo
        es posible con sesion iniciada o por el administrador.
        """
        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        botones = dialogo.findChildren(QPushButton)
        nombres = [b.text().lower() for b in botones]
        assert not any("olvid" in t for t in nombres), (
            "El login no debe ofrecer recuperar la contrasena"
        )

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
            def __enter__(self) -> MagicMock:
                return mock_session

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
            def __enter__(self) -> MagicMock:
                return mock_session

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


# ============================================================
# TESTS: VentanaPrincipal
# ============================================================
# Verificamos que la ventana principal se crea correctamente,
# que tiene la barra de navegacion y las paginas del sistema.
# ============================================================


class TestVentanaPrincipal:
    """Pruebas para la ventana principal (VentanaPrincipal)."""

    def test_crear_ventana(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que VentanaPrincipal se crea con el titulo correcto.

        Crea la ventana principal con un usuario simulado y verifica
        que el titulo incluye el nombre del usuario.
        """
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        # El titulo debe contener el nombre completo del usuario.
        assert "Administrador" in ventana.windowTitle()

    def test_barra_navegacion_existe(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que la barra lateral de navegacion se creo.

        La barra de navegacion es un QListWidget con los nombres
        de los modulos del sistema.
        """
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        # Verificar que el atributo barra_navegacion existe.
        assert hasattr(ventana, "barra_navegacion")

        # Debe tener 5 items: Dashboard, Ventas, Productos, Inventario, Reportes.
        # (La caja esta UNIDA a la pagina de Ventas: un solo item.)
        assert ventana.barra_navegacion.count() == 5

        # Verificar los nombres de los items.
        nombres = []
        for i in range(ventana.barra_navegacion.count()):
            item = ventana.barra_navegacion.item(i)
            assert item is not None, f"item({i}) es None"
            nombres.append(item.text())
        assert nombres == [
            "Dashboard",
            "Ventas",
            "Productos",
            "Inventario",
            "Reportes",
        ]

    def test_paginas_existen(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que las 6 paginas del sistema estan en el QStackedWidget.

        VentanaPrincipal usa un QStackedWidget que contiene una pagina
        por cada modulo (incluyendo Usuarios). Verificamos que hay 6 paginas
        (la caja vive dentro de la pagina de Ventas, no es una pagina aparte).
        """
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        # El QStackedWidget debe tener 6 paginas (una por modulo).
        assert ventana.paginas.count() == 6

    def test_cambiar_pagina(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que se puede cambiar de pagina usando la barra lateral.

        Simula la seleccion de cada item de navegacion y verifica
        que la pagina activa del QStackedWidget cambia correctamente.
        """
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        # Probar cada indice de pagina.
        for i in range(ventana.barra_navegacion.count()):
            # Simular clic en el item i de la barra de navegacion.
            ventana.barra_navegacion.setCurrentRow(i)

            # Verificar que la pagina activa es la que elegimos.
            assert ventana.paginas.currentIndex() == i

    def test_controladores_creados(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que los controladores se crearon al iniciar VentanaPrincipal.

        VentanaPrincipal crea los controladores/servicios en su __init__
        (incluye controlador_caja: la caja vive unida a la pagina de ventas).
        Verificamos que todos existen y tienen los metodos esperados.
        """
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        # Lista de (nombre_atributo, clase_esperada).
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


# ============================================================
# TESTS: FormularioProducto
# ============================================================
# Verificamos que el dialogo de productos funciona en ambos modos:
#   - Modo CREAR: campos vacios, se puede escribir en ellos.
#   - Modo EDITAR: campos precargados con datos del producto.
# ============================================================


class TestFormularioProducto:
    """Pruebas para el dialogo de crear/editar productos (FormularioProducto)."""

    def test_crear_dialogo_modo_crear(self, qtbot: QtBot) -> None:
        """Verifica que FormularioProducto se abre en modo crear.

        Modo crear = sin pasarle un producto existente.
        El titulo debe decir "Agregar producto".
        """
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        assert "Agregar producto" in dialogo.windowTitle()

    def test_crear_dialogo_modo_editar(self, qtbot: QtBot) -> None:
        """Verifica que FormularioProducto se abre en modo editar.

        Modo editar = pasandole un producto existente.
        El titulo debe decir "Editar producto: <nombre>".
        """
        producto = Producto(
            nombre_producto="Arroz",
            categoria="ALIMENTOS",
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

    def test_campos_existen_en_modo_crear(self, qtbot: QtBot) -> None:
        """Verifica que los campos del formulario existen en modo crear.

        Comprueba que FormularioProducto tiene todos los atributos
        de sus campos de formulario.
        """
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        # Lista de campos que debe tener el formulario.
        campos = [
            "txt_nombre",
            "txt_categoria",
            "spin_precio_compra",
            "spin_precio_venta_bs",
            "spin_precio_venta_usd",
            "spin_stock_actual",
            "spin_stock_minimo",
            "txt_unidad",
        ]
        for campo in campos:
            assert hasattr(dialogo, campo), f"Falta el campo: {campo}"

    def test_campos_precargados_en_editar(self, qtbot: QtBot) -> None:
        """Verifica que los campos se precargan en modo editar.

        Crea un producto, abre el dialogo en modo editar y verifica
        que los campos contienen los valores del producto.
        """
        producto = Producto(
            nombre_producto="Leche",
            categoria="LACTEOS",
            precio_compra=Decimal("0.80"),
            precio_venta_bs=Decimal("1.20"),
            precio_venta_usd=Decimal("0.40"),
            stock_actual=Decimal("50"),
            stock_minimo=Decimal("10"),
            unidad="LTS",
        )
        dialogo = FormularioProducto(producto=producto)
        qtbot.addWidget(dialogo)

        # Verificar que los campos estan precargados.
        assert dialogo.txt_nombre.text() == "Leche"
        assert dialogo.txt_categoria.text() == "LACTEOS"
        assert dialogo.txt_unidad.text() == "LTS"

    def test_validacion_nombre_vacio(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que el dialogo rechaza guardar sin nombre.

        Simula hacer clic en Guardar sin escribir el nombre y
        verifica que se muestra una advertencia (QMessageBox.warning).
        """
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        # Mockear QMessageBox.warning para capturar la llamada.
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_producto.QMessageBox.warning",
            mock_warning,
        )

        # Buscar el boton Guardar por su texto.
        for btn in dialogo.findChildren(QPushButton):
            if btn.text() == "Guardar":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        # Debe mostrar advertencia porque el nombre esta vacio.
        mock_warning.assert_called_once()


# ============================================================
# TESTS: FormularioVenta
# ============================================================
# Verificamos que el dialogo de ventas se crea correctamente
# y tiene los widgets necesarios para registrar una venta.
# ============================================================


class TestFormularioVenta:
    """Pruebas para el POS de nueva venta (FormularioVenta)."""

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

    @staticmethod
    def _producto_peso() -> Producto:
        """Helper: producto por PESO con stock 10 (se agrega por defecto 0.100)."""
        return Producto(
            idproducto=1,
            nombre_producto="Carne",
            categoria="CHARCUTERIA",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )

    def test_crear_dialogo(self, qtbot: QtBot) -> None:
        """Verifica que FormularioVenta se crea con el titulo correcto."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        assert "Nueva Venta" in dialogo.windowTitle()

    def test_widgets_principales_existen(self, qtbot: QtBot) -> None:
        """Verifica que los widgets del POS existen.

        FormularioVenta tiene: campo de busqueda, grid de catalogo,
        tabla del ticket, totales y campos de pago.
        """
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        # Widgets del catalogo.
        assert hasattr(dialogo, "campo_busqueda")
        assert hasattr(dialogo, "grid_productos")

        # Widgets del ticket.
        assert hasattr(dialogo, "tabla_productos_venta")
        assert hasattr(dialogo, "lbl_total")
        assert hasattr(dialogo, "lbl_subtotal")
        assert hasattr(dialogo, "lbl_iva")
        assert hasattr(dialogo, "lbl_total_usd")

        # Widgets del desglose de pago (multi-pago).
        assert hasattr(dialogo, "spin_monto")
        assert hasattr(dialogo, "campo_referencia")
        assert hasattr(dialogo, "tabla_pagos")
        assert hasattr(dialogo, "lbl_equivalencia")
        assert hasattr(dialogo, "lbl_cubierto")
        assert hasattr(dialogo, "lbl_restante")
        assert hasattr(dialogo, "btn_agregar_pago")
        assert len(dialogo._botones_metodo) == 6

        # Botones de accion del ticket.
        assert hasattr(dialogo, "btn_anular")
        assert hasattr(dialogo, "btn_cobrar")

    def test_boton_cobrar_existe(self, qtbot: QtBot) -> None:
        """Verifica que el boton 'COBRAR (F12)' esta en el dialogo."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        botones = dialogo.findChildren(QPushButton)
        btn_cobrar = [b for b in botones if b.text() == "COBRAR (F12)"]
        assert len(btn_cobrar) > 0

    def test_venta_vacia_muestra_error(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que COBRAR sin productos muestra error.

        Sin agregar productos, hacer clic en COBRAR debe mostrar
        un mensaje de advertencia.
        """
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        # Mockear QMessageBox.warning para capturar la llamada.
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        # Hacer clic en "COBRAR (F12)".
        for btn in dialogo.findChildren(QPushButton):
            if btn.text() == "COBRAR (F12)":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        # Debe mostrar advertencia porque no hay productos.
        mock_warning.assert_called_once()

    def test_pago_oculto_hasta_agregar_producto(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica la visibilidad progresiva de la seccion de pago.

        La seccion "Metodo de Pago" debe estar oculta al abrir el dialogo,
        mostrarse al agregar un producto y volver a ocultarse al quitarlo.
        Se usa isHidden() (no isVisible()) porque el dialogo no se muestra
        en el test y isVisible() depende de los ancestros.
        """
        producto = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            categoria="ALIMENTOS",
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

        # Al abrir no hay productos => pago oculto.
        assert dialogo.productos_venta == []
        assert dialogo.grupo_pago.isHidden()

        # Agregar un producto => pago visible.
        self._agregar_producto_al_ticket(dialogo, producto, monkeypatch)
        assert len(dialogo.productos_venta) == 1
        assert not dialogo.grupo_pago.isHidden()

        # Quitar el unico producto => pago oculto de nuevo.
        dialogo._eliminar_producto_venta(0)
        assert dialogo.productos_venta == []
        assert dialogo.grupo_pago.isHidden()

    def test_agregar_unidad_y_peso_por_defecto(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica la cantidad por defecto al hacer clic en el catalogo.

        UNIDAD → 1 pieza; PESO → 0.100 kg (producto a granel).
        """
        producto_unidad = Producto(
            idproducto=1,
            nombre_producto="Aceite",
            categoria="ALIMENTOS",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("10.00"),
            precio_venta_usd=Decimal("0.20"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        producto_peso = Producto(
            idproducto=2,
            nombre_producto="Carne",
            categoria="CHARCUTERIA",
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
        assert dialogo.productos_venta[1]["cantidad"] == Decimal("0.100")

    def test_catalogo_busca_y_filtra_por_categoria(self, qtbot: QtBot) -> None:
        """Verifica que la busqueda y la categoria filtran el catalogo."""
        producto_arroz = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            categoria="ALIMENTOS",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("10.00"),
            precio_venta_usd=Decimal("0.20"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        producto_leche = Producto(
            idproducto=2,
            nombre_producto="Leche",
            categoria="LACTEOS",
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

        # Todos los productos visibles al inicio.
        assert dialogo.grid_productos.count() == 2

        # Busqueda filtra en vivo.
        dialogo.campo_busqueda.setText("arroz")
        assert dialogo.grid_productos.count() == 1

        # Limpiar busqueda y filtrar por categoria.
        dialogo.campo_busqueda.setText("")
        dialogo._seleccionar_categoria("LACTEOS")
        assert dialogo.grid_productos.count() == 1

        # Volver a "Todos" restaura el catalogo completo.
        dialogo._seleccionar_categoria("Todos")
        assert dialogo.grid_productos.count() == 2

    def test_editar_peso_recalcula_total(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica que editar Cant/Peso en el ticket recalcula el total."""
        producto_peso = Producto(
            idproducto=1,
            nombre_producto="Carne",
            categoria="CHARCUTERIA",
            tipo_venta="PESO",
            precio_venta_bs=Decimal("12.00"),
            precio_venta_usd=Decimal("0.30"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto_peso, monkeypatch)

        # Peso por defecto 0.100 => subtotal 1.20 en total.
        assert dialogo.total_bs == Decimal("1.20")

        # Editar la celda Cant/Peso (fila 0, columna 1) a 0.500 kg.
        celda = dialogo.tabla_productos_venta.item(0, 1)
        assert celda is not None
        celda.setText("0.500")

        # 0.500 * 12.00 = 6.00 => total actualizado.
        assert dialogo.total_bs == Decimal("6.00")

    def test_editar_cantidad_invalida_revierte(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un valor no numerico en Cant/Peso deja el ticket intacto."""
        producto_peso = self._producto_peso()
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto_peso, monkeypatch)

        # Editar con texto invalido: se revierte a la cantidad almacenada.
        celda = dialogo.tabla_productos_venta.item(0, 1)
        assert celda is not None
        celda.setText("abc")

        assert dialogo.productos_venta[0]["cantidad"] == Decimal("0.100")
        assert dialogo.total_bs == Decimal("1.20")
        celda_revertida = dialogo.tabla_productos_venta.item(0, 1)
        assert celda_revertida is not None
        assert celda_revertida.text() == "0.100"

    def test_editar_cantidad_mayor_al_stock_revierte(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Una cantidad mayor al stock avisa y revierte el valor editado."""
        producto_peso = self._producto_peso()
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto_peso, monkeypatch)

        # Este mock se instala DESPUES del helper para capturar el aviso.
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        # Stock disponible: 10. Pedir 99 debe avisar y revertir.
        celda = dialogo.tabla_productos_venta.item(0, 1)
        assert celda is not None
        celda.setText("99")

        mock_warning.assert_called_once()
        assert dialogo.productos_venta[0]["cantidad"] == Decimal("0.100")
        assert dialogo.total_bs == Decimal("1.20")
        celda_revertida = dialogo.tabla_productos_venta.item(0, 1)
        assert celda_revertida is not None
        assert celda_revertida.text() == "0.100"

    def test_anular_limpia_el_ticket(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que ANULAR VENTA vacia el ticket actual."""
        producto = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            categoria="ALIMENTOS",
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

    def test_totales_iva_informativo(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica el desglose: subtotal sin IVA + IVA 16% = total.

        El concepto elegido: los precios YA incluyen IVA, por lo que el
        total cobrado es la suma de subtotales y el desglose se calcula
        hacia atras (base = total / 1.16).
        """
        producto = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            categoria="ALIMENTOS",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal("11.60"),
            precio_venta_usd=Decimal("0.24"),
            stock_actual=Decimal("10"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        self._agregar_producto_al_ticket(dialogo, producto, monkeypatch)

        # Total cobrado = precio (IVA incluido).
        assert dialogo.total_bs == Decimal("11.60")
        # Base sin IVA = 11.60 / 1.16 = 10.00; IVA = 1.60.
        assert "10,00" in dialogo.lbl_subtotal.text()
        assert "1,60" in dialogo.lbl_iva.text()
        assert "11,60" in dialogo.lbl_total.text()

    def test_total_usd_con_tasa(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que el total en USD usa la tasa activa."""
        producto = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            categoria="ALIMENTOS",
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
        # La tasa se captura al abrir el dialogo: forzamos esa lectura.
        dialogo._actualizar_tasa()
        self._agregar_producto_al_ticket(dialogo, producto, monkeypatch)

        # 100.00 Bs / 40.00 = 2.50 USD.
        celda_total_usd = dialogo.lbl_total_usd
        assert celda_total_usd is not None
        assert "2.50" in celda_total_usd.text()

    def test_atajo_f12_cobra(self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que F12 esta ligado a la finalizacion de la venta.

        Sin productos, activar el atajo debe mostrar la advertencia de
        venta vacia.

        NOTA: se emite la senal del QShortcut en lugar de simular la
        tecla. Un QShortcut con contexto "WindowShortcut" solo se activa
        si la ventana esta activa, y en los tests de UI el dialogo no se
        muestra (keyClick no lo dispara).
        """
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        # Mockear QMessageBox.warning para capturar la llamada.
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        # El atajo usa la tecla F12 y al activarse llama a _finalizar_venta.
        atajo = dialogo._atajo_cobrar
        assert atajo.key().toString() == "F12"
        atajo.activated.emit()

        mock_warning.assert_called_once()

    # ------------------------------------------------------------------
    # Multi-pago: metodos, monto aplicado, resumen y envio al controlador
    # ------------------------------------------------------------------
    def _abrir_pos_con_ticket(
        self,
        qtbot: QtBot,
        monkeypatch: pytest.MonkeyPatch,
        precio: str = "100.00",
        tasa: str = "50.00",
    ) -> FormularioVenta:
        """Helper: POS abierto con 1 producto en el ticket y tasa simulada."""
        producto = Producto(
            idproducto=1,
            nombre_producto="Arroz",
            categoria="ALIMENTOS",
            tipo_venta="UNIDAD",
            precio_venta_bs=Decimal(precio),
            precio_venta_usd=Decimal("2.00"),
            stock_actual=Decimal("100"),
            stock_minimo=Decimal("1"),
        )
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)
        # La tasa se simula: los tests de UI nunca tocan la BD ni la red.
        tasa_mock = MagicMock()
        tasa_mock.tasa_venta = Decimal(tasa)
        tasa_mock.fecha = "2026-09-17"
        dialogo._tasa = tasa_mock
        dialogo.controlador_tasas = MagicMock()
        dialogo.controlador_tasas.tasa_activa.return_value = tasa_mock
        self._agregar_producto_al_ticket(dialogo, producto, monkeypatch)
        return dialogo

    def test_metodos_de_pago_en_botones(self, qtbot: QtBot) -> None:
        """Los 6 metodos existen como botones y sin elegir uno no hay pago."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        assert sorted(dialogo._botones_metodo) == sorted(METODOS_PAGO)
        assert dialogo.pagos == []
        assert dialogo.spin_monto.isEnabled() is False
        assert dialogo.btn_agregar_pago.isEnabled() is False
        assert "Selecciona un metodo" in dialogo.lbl_equivalencia.text()

    def test_seleccionar_metodo_prellena_el_faltante(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Elegir metodo resalta el boton y pre-llena el monto con el faltante."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        assert dialogo.total_bs == Decimal("100.00")

        dialogo._seleccionar_metodo("efectivo_bs")
        assert dialogo._botones_metodo["efectivo_bs"].property("rol") == "metodo_activo"
        assert dialogo.spin_monto.value() == 100.0
        # En Bs. la equivalencia informativa es el monto en USD.
        assert "2.00" in dialogo.lbl_equivalencia.text()

        # En USD se pre-llena el equivalente (100.00 / 50.00 = 2.00) y la
        # equivalencia informativa es el monto en Bs.
        dialogo._seleccionar_metodo("efectivo_usd")
        assert dialogo.spin_monto.value() == 2.0
        assert "100,00" in dialogo.lbl_equivalencia.text()

    def test_agregar_pago_registra_solo_lo_aplicado(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Efectivo: si se teclea de mas, se aplica solo lo que cubre."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)

        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_monto.setValue(500.0)
        dialogo._agregar_pago()

        assert len(dialogo.pagos) == 1
        # Se guarda lo RECIBIDO (500.00) y aparte lo APLICADO (100.00).
        assert dialogo.pagos[0]["monto"] == Decimal("500.00")
        assert dialogo.pagos[0]["monto_bs"] == Decimal("100.00")
        assert dialogo.pagos[0]["vuelto_bs"] == Decimal("400.00")
        assert dialogo.tabla_pagos.rowCount() == 1
        celda_vuelto = dialogo.tabla_pagos.item(0, 3)
        assert celda_vuelto is not None
        assert "400,00" in celda_vuelto.text()
        assert dialogo._monto_restante_bs() == Decimal("0.00")
        assert "PAGO COMPLETO" in dialogo.lbl_restante.text()

    def test_pago_en_usd_con_tasa_no_redonda_cobra_en_un_paso(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regresion: USD cuando la tasa no divide exacto (100.00 / 30.00).

        3.33 USD dejaban 0.10 Bs. sin cubrir y 3.34 USD se pasaban 0.20 Bs.
        Antes el POS se bloqueaba en ambos sentidos; ahora aplica el faltante
        exacto (100.00) y muestra el vuelto por redondeo (0.20).
        """
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

        # El pre-llenado en USD es el equivalente redondeado hacia arriba:
        # existe una combinacion de centavos en USD que nunca cuadra.
        dialogo._seleccionar_metodo("efectivo_usd")
        assert dialogo.spin_monto.value() == 3.34
        dialogo._agregar_pago()

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
        # El monto APLICADO va al controlador: la suma cuadra al centimo.
        assert kwargs["pagos"][0]["monto_bs"] == Decimal("100.00")

    def test_alto_de_la_tabla_de_pagos_acompana_a_las_filas(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regresion: con el alto fijo de 88 px solo se veia la PRIMERA fila.

        El viewport util era de 56 px con filas de 30 px y el scroll no
        aparecia: los pagos 2..N quedaban invisibles e inborrables.
        """
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch, precio="5000.00")
        tabla = dialogo.tabla_pagos
        alto_minimo = tabla.height()

        # 2 pagos: siguen entrando en el minimo (2 filas).
        for _ in range(2):
            dialogo._seleccionar_metodo("efectivo_bs")
            dialogo.spin_monto.setValue(10.0)
            dialogo._agregar_pago()
        assert tabla.height() == alto_minimo

        # 3 y 4 pagos: la tabla crece una fila por vez.
        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_monto.setValue(10.0)
        dialogo._agregar_pago()
        alto_3 = tabla.height()
        assert alto_3 > alto_minimo

        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_monto.setValue(10.0)
        dialogo._agregar_pago()
        alto_4 = tabla.height()
        assert alto_4 > alto_3

        # 5 pagos: tope, las extra quedan accesibles por la scrollbar.
        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_monto.setValue(10.0)
        dialogo._agregar_pago()
        assert tabla.rowCount() == 5
        assert tabla.height() == alto_4

        # Al borrar todos vuelve al minimo.
        while dialogo.pagos:
            dialogo._eliminar_pago(0)
        assert tabla.rowCount() == 0
        assert tabla.height() == alto_minimo

    def test_tabla_de_pagos_no_desborda_el_viewport(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """La ultima columna (Borrar) queda fija y ninguna seccion desborda.

        Regresion: el boton Borrar tenia un sizeHint de 81 px (padding
        generico del QSS) en una columna de 58 px, asi que se salia cortado.
        """
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_monto.setValue(10.0)
        dialogo._agregar_pago()
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
        # sizeHint() del estilo (81px) no manda: la celda impone min/max.
        assert boton.minimumWidth() <= anchos[4]
        assert boton.maximumWidth() <= anchos[4]

    def test_cambio_de_tasa_descarta_el_vuelto_por_redondeo(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Si la tasa cambia, el recorte anterior deja de ser valido."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch, tasa="30.00")
        dialogo.controlador_ventas = MagicMock()
        dialogo._seleccionar_metodo("efectivo_usd")
        dialogo._agregar_pago()
        assert dialogo.pagos[0]["vuelto_bs"] == Decimal("0.20")

        # La tasa se refresca antes de cobrar (mismo pago, otra tasa).
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

    def test_varios_pagos_y_eliminar_uno(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Con dos pagos el resumen cuadra; borrar uno vuelve a faltar."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)

        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_monto.setValue(60.0)
        dialogo._agregar_pago()

        # El efectivo USD se pre-llena con lo que falta (40.00 / 50.00).
        dialogo._seleccionar_metodo("efectivo_usd")
        dialogo._agregar_pago()

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

    def test_equivalencia_avisa_el_cambio(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Si el monto supera el faltante, se muestra el cambio a devolver."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)

        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_monto.setValue(150.0)

        assert "CAMBIO" in dialogo.lbl_equivalencia.text()
        assert "50,00" in dialogo.lbl_equivalencia.text()

    def test_agregar_pago_sin_metodo_avisa(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin metodo elegido no se agrega nada y se avisa al usuario."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        dialogo._agregar_pago()

        mock_warning.assert_called_once()
        assert dialogo.pagos == []

    def test_efectivo_usd_sin_tasa_queda_deshabilitado(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin tasa activa no se puede convertir ni cobrar en USD."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo._tasa = None

        dialogo._seleccionar_metodo("efectivo_usd")

        assert dialogo.spin_monto.isEnabled() is False
        assert dialogo.btn_agregar_pago.isEnabled() is False
        assert "Sin tasa" in dialogo.lbl_equivalencia.text()

    def test_ticket_vacio_descarta_el_desglose(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Quitar el ultimo producto descarta los pagos de esa venta."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)

        dialogo._seleccionar_metodo("tarjeta")
        dialogo.spin_monto.setValue(30.0)
        dialogo._agregar_pago()
        assert len(dialogo.pagos) == 1

        dialogo._eliminar_producto_venta(0)

        assert dialogo.pagos == []
        assert dialogo.tabla_pagos.rowCount() == 0
        assert dialogo.grupo_pago.isHidden()

    def test_anular_tambien_limpia_el_desglose(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ANULAR VENTA limpia el ticket y su desglose de pagos."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)

        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_monto.setValue(100.0)
        dialogo._agregar_pago()
        assert len(dialogo.pagos) == 1

        dialogo._limpiar_ticket()

        assert dialogo.pagos == []
        assert dialogo._metodo_actual is None
        assert dialogo.tabla_pagos.rowCount() == 0
        assert dialogo.btn_agregar_pago.isEnabled() is False

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

    def test_cobrar_con_pago_parcial_avisa(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Si falta por cubrir, COBRAR avisa y no registra la venta."""
        dialogo = self._abrir_pos_con_ticket(qtbot, monkeypatch)
        dialogo.controlador_ventas = MagicMock()
        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_monto.setValue(30.0)
        dialogo._agregar_pago()

        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        dialogo._finalizar_venta()

        mock_warning.assert_called_once()
        assert "Falta por cubrir" in str(mock_warning.call_args)
        dialogo.controlador_ventas.crear.assert_not_called()

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

        dialogo._seleccionar_metodo("efectivo_bs")
        dialogo.spin_monto.setValue(60.0)
        dialogo._agregar_pago()
        dialogo._seleccionar_metodo("efectivo_usd")
        dialogo._agregar_pago()

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


# ============================================================
# FIXTURES COMPARTIDOS
# ============================================================


@pytest.fixture()
def producto_ejemplo() -> Producto:
    """Producto de prueba para tests de inventario."""
    return Producto(
        idproducto=1,
        nombre_producto="Arroz",
        categoria="ALIMENTOS",
        precio_compra=Decimal("1.00"),
        precio_venta_bs=Decimal("1.50"),
        precio_venta_usd=Decimal("0.50"),
        stock_actual=Decimal("10"),
        stock_minimo=Decimal("5"),
        unidad="KG",
    )


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


# ============================================================
# TESTS: FormularioCambioContrasena
# ============================================================


class TestFormularioCambioContrasena:
    """Pruebas para el dialogo de cambio de contrasena/usuario."""

    def test_crear_dialogo(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que el dialogo se crea con el titulo correcto."""
        dialogo = FormularioCambioContrasena(usuario=usuario_admin)
        qtbot.addWidget(dialogo)

        assert "Cambiar Contraseña / Usuario" in dialogo.windowTitle()

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

    def test_campos_precargados(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que los campos se precargan con datos del usuario."""
        dialogo = FormularioCambioContrasena(usuario=usuario_admin)
        qtbot.addWidget(dialogo)

        assert dialogo.txt_nombre_completo.text() == "Administrador"

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


# ============================================================
# TESTS: InventarioPagina
# ============================================================


class TestInventarioPagina:
    """Pruebas para la pagina de inventario."""

    def test_crear_pagina(self, qtbot: QtBot, producto_ejemplo: Producto) -> None:
        """Verifica que la pagina se crea sin errores."""
        mock_controlador_inv = MagicMock()
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        label = pagina.findChild(QLabel)
        assert label is not None
        assert "Inventario" in label.text()

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

    def test_tabla_movimientos_vacia(self, qtbot: QtBot, producto_ejemplo: Producto) -> None:
        """Verifica que la tabla se muestra vacia cuando no hay movimientos."""
        mock_controlador_inv = MagicMock()
        mock_controlador_inv.movimientos_recientes.return_value = []
        mock_controlador_prod = MagicMock()
        mock_controlador_prod.listar_todos.return_value = [producto_ejemplo]

        pagina = InventarioPagina(mock_controlador_inv, mock_controlador_prod)
        qtbot.addWidget(pagina)

        assert pagina.tabla_movimientos.rowCount() == 0

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


# ============================================================
# TESTS: UsuariosPagina
# ============================================================


class TestUsuariosPagina:
    """Pruebas para la pagina de gestion de usuarios."""

    def test_crear_pagina(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que la pagina se crea sin errores."""

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        label = pagina.findChild(QLabel)
        assert label is not None
        assert "Usuarios" in label.text()

    def test_widgets_perfil_existen(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que los labels del perfil existen."""

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        assert hasattr(pagina, "lbl_nombre")
        assert hasattr(pagina, "lbl_usuario")
        assert hasattr(pagina, "lbl_rol")
        assert "Administrador" in pagina.lbl_nombre.text()

    def test_botones_perfil_existen(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que los botones de perfil existen."""

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        botones = [btn.text() for btn in pagina.findChildren(QPushButton)]
        assert "Editar Perfil" in botones
        assert "Cambiar Contraseña" in botones

    def test_tabla_usuarios_vacia(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que la tabla de usuarios se crea correctamente."""

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        assert hasattr(pagina, "tabla_usuarios")
        assert pagina.tabla_usuarios.rowCount() == 0

    def test_botones_admin_existen(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que los botones de admin existen."""

        pagina = UsuariosPagina(usuario_actual=usuario_admin)
        qtbot.addWidget(pagina)

        botones = [btn.text() for btn in pagina.findChildren(QPushButton)]
        assert "+ Crear Usuario" in botones
        assert "Resetear Contraseña" in botones
        assert "Activar / Desactivar" in botones

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


# ============================================================
# TESTS: VentanaPrincipal con rol ADMINISTRADOR
# ============================================================


class TestVentanaPrincipalAdmin:
    """Pruebas para VentanaPrincipal con usuario ADMINISTRADOR."""

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

    def test_menu_incluye_usuarios(self, qtbot: QtBot, usuario_real_admin: Usuario) -> None:
        """Verifica que el menu incluye 'Usuarios' para admin."""
        ventana = VentanaPrincipal(usuario_real_admin)
        qtbot.addWidget(ventana)

        assert ventana.barra_navegacion.count() == 6

        nombres = []
        for i in range(ventana.barra_navegacion.count()):
            item = ventana.barra_navegacion.item(i)
            assert item is not None
            nombres.append(item.text())
        assert "Usuarios" in nombres

    def test_paginas_con_admin(self, qtbot: QtBot, usuario_real_admin: Usuario) -> None:
        """Verifica que hay 6 paginas para admin."""
        ventana = VentanaPrincipal(usuario_real_admin)
        qtbot.addWidget(ventana)

        assert ventana.paginas.count() == 6

    def test_menu_sin_usuarios_para_vendedor(self, qtbot: QtBot, usuario_admin: Usuario) -> None:
        """Verifica que el menu NO incluye 'Usuarios' para vendedor."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)

        assert ventana.barra_navegacion.count() == 5

        nombres = []
        for i in range(ventana.barra_navegacion.count()):
            item = ventana.barra_navegacion.item(i)
            assert item is not None
            nombres.append(item.text())
        assert "Usuarios" not in nombres


# ============================================================
# TESTS: VentasPagina (anulacion de ventas)
# ============================================================
# Verificamos que el boton "Anular Venta" NUNCA falla en silencio:
#   - Sin fila seleccionada → aviso claro (antes hacia un return mudo).
#   - Si el controlador lanza una excepcion no-ValueError → se registra
#     en el log y se muestra un dialogo critico (antes era invisible).
# ============================================================


class TestVentasPagina:
    """Pruebas del boton Anular Venta de la pagina de Ventas."""

    def test_anular_sin_fila_seleccionada_muestra_aviso(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin fila seleccionada, clic en Anular muestra un aviso informativo."""
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        pagina = ventana.pagina_ventas

        # Asegurar que NO hay ninguna fila seleccionada.
        pagina.tabla_ventas.clearSelection()

        mock_informacion = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.information",
            mock_informacion,
        )

        pagina.btn_anular.click()

        mock_informacion.assert_called_once()
        mensaje = mock_informacion.call_args.args[2]
        assert "Selecciona primero" in mensaje

    def test_anular_muestra_error_si_el_controlador_falla(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Si anular() lanza un error no esperado, se muestra dialogo critico.

        Tambien se registra la excepcion en el log (nunca invisible).
        """
        ventana = VentanaPrincipal(usuario_admin)
        qtbot.addWidget(ventana)
        pagina = ventana.pagina_ventas

        if pagina.tabla_ventas.rowCount() == 0:
            pytest.skip("No hay ventas en la BD para probar la anulacion.")

        # Seleccionar la primera venta de la tabla.
        pagina.tabla_ventas.selectRow(0)

        # Confirmar la anulacion.
        mock_question = MagicMock(return_value=QMessageBox.StandardButton.Yes)
        monkeypatch.setattr(
            "sistema_financiero.ui.ventas_pagina.QMessageBox.question",
            mock_question,
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

        # El controlador falla con un error INESPERADO (no ValueError).
        def _fallar(*args: object, **kwargs: object) -> None:
            raise RuntimeError("error inesperado de prueba")

        monkeypatch.setattr(pagina.controlador_ventas, "anular", _fallar)

        pagina.btn_anular.click()

        # Se registro el error y se mostro el dialogo critico.
        mock_registrar.assert_called_once()
        mock_critico.assert_called_once()
        mensaje = mock_critico.call_args.args[2]
        assert "No se pudo anular" in mensaje


# ============================================================
# TESTS: Cierre de caja desde la pagina de Ventas
# ============================================================
# Verificamos que el boton "Cerrar Caja" cierra de verdad y que
# NUNCA falla en silencio:
#   - Flujo completo (arqueo) sobre BD en memoria: caja queda CERRADA.
#   - Si el usuario cancela el arqueo, la caja NO se cierra (sin error).
#   - Si regenerar el reporte falla, la caja YA quedo cerrada y solo
#     se avisa aparte (antes parecia que fallaba el cierre).
# Requiere la fixture "session" (BD en memoria) de tests/conftest.py.
# ============================================================


class TestCierreCajaPagina:
    """Pruebas del boton Cerrar Caja (flujo de arqueo)."""

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

        # Abrir una caja real en la BD en memoria y refrescar el panel.
        caja_service = pagina.caja_service
        caja_service.abrir_caja(Decimal("100.00"), 1)
        pagina._actualizar_estado_caja()

        # Simular los dialogos del arqueo y el aviso final.
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

        # La caja se cerro de verdad y se mostro el aviso de exito.
        assert caja_service.obtener_caja_abierta() is None
        mock_informacion.assert_called_once()
        mensaje = mock_informacion.call_args.args[2]
        assert "cerrada correctamente" in mensaje

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

        # El usuario cancela el dialogo de billetes: no se cierra nada.
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

        # La caja sigue abierta y no se mostro ni exito ni error.
        assert caja_service.obtener_caja_abierta() is not None
        mock_informacion.assert_not_called()
        mock_critico.assert_not_called()

    def test_cerrar_sin_caja_abierta_muestra_aviso(
        self,
        qtbot: QtBot,
        usuario_admin: Usuario,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Cerrar Caja sin caja abierta: aviso claro, sin error.

        El boton esta deshabilitado cuando la caja esta cerrada (Qt
        ignora click() sobre botones disabled), asi que se prueba el
        handler directamente.
        """
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

        # La caja SI quedo cerrada y se mostro el exito...
        assert caja_service.obtener_caja_abierta() is None
        mock_informacion.assert_called_once()
        # ...y ademas se aviso por separado que el reporte no se regenero.
        mock_aviso.assert_called_once()
        mensaje = mock_aviso.call_args.args[2]
        assert "no se pudo regenerar el reporte" in mensaje
        mock_registrar.assert_called_once()


# ============================================================
# TESTS: Salida de la app con caja abierta (closeEvent)
# ============================================================
# Regla de negocio: con la caja del turno ABIERTA no se puede salir
# sin avisar. Se permite forzar la salida SOLO con doble confirmacion:
#   1. Sin caja abierta → la ventana se cierra normal.
#   2. Con caja abierta → pregunta "Salir de todas formas?".
#      - No → se cancela la salida y se lleva a la pagina de Ventas.
#      - Si → segunda confirmacion: Si sale, No cancela la salida.
#   3. Si consultar la caja falla → NO bloquear (evita quedar atrapado).
# ============================================================


class TestSalidaConCajaAbierta:
    """Pruebas del bloqueo de salida cuando hay una caja abierta."""

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

        # La salida se cancelo y el usuario fue llevado a la pagina de Ventas.
        assert not evento.isAccepted()
        assert ventana.paginas.currentIndex() == 1

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

        # Salio: se pidio confirmacion dos veces.
        assert evento.isAccepted()
        assert mock_question.call_count == 2

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
                # Valores para el cierre que pytest-qt hace en el teardown
                # (primera y segunda pregunta del closeEvent): No dan problemas
                # porque solo se usan si la ventana sigue registrada.
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

        # Solo se pregunto 2 veces durante la prueba: la primera Si y la
        # segunda No (el tercer valor del side_effect es para el cierre
        # que pytest-qt hace en el teardown, no para esta prueba).
        assert mock_question.call_count == 2
        assert not evento.isAccepted()

    def test_error_al_consultar_caja_no_bloquea_la_salida(
        self, qtbot: QtBot, usuario_admin: Usuario, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Si consultar la caja falla, NO bloquear la salida (evita quedar atrapado)."""

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

        # No bloquea la salida y registra el error en el log.
        assert evento.isAccepted()
        mock_registrar.assert_called_once()
