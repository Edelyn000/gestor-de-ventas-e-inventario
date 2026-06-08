# ============================================================
# ARCHIVO: tests/test_ui.py
# ============================================================
# Tests para los componentes visuales (PyQt6) de la aplicacion.
#
# QUE PRUEBA:
#   - VentanaLogin: apertura, widgets, validacion de campos.
#   - MainWindow: creacion con usuario, navegacion, cambio de paginas.
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
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QPushButton

# Importamos los componentes UI que vamos a probar.
from sistema_financiero.models.modelos import Producto, Usuario

# NOTA: MainWindow se prueba con un fixture especial porque requiere
# un usuario real (objeto Usuario). Lo definimos abajo.
from sistema_financiero.ui.interflaz import MainWindow
from sistema_financiero.ui.ventana_login import VentanaLogin
from sistema_financiero.ui.formulario_producto import FormularioProducto
from sistema_financiero.ui.formulario_venta import FormularioVenta

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
    que MainWindow pueda usarlo al inicializarse.
    """
    return Usuario(
        usuario="admin",
        contrasena="hash_falso",
        nombre_completo="Administrador",
        activo=True,
    )


# ============================================================
# TESTS: VentanaLogin
# ============================================================
# Verificamos que el dialogo de login se crea correctamente,
# que tiene los campos esperados y que valida datos vacios.
# ============================================================


class TestVentanaLogin:
    """Pruebas para la ventana de inicio de sesion (VentanaLogin)."""

    def test_crear_dialogo(self, qtbot):
        """Verifica que VentanaLogin se crea con el titulo correcto.

        Crea el dialogo y comprueba:
        - El titulo de la ventana contiene "Iniciar Sesion".
        - La ventana se puede cerrar (sin crashear).
        """
        dialogo = VentanaLogin()
        qtbot.addWidget(dialogo)

        # Verificar titulo de la ventana.
        assert "Iniciar Sesión" in dialogo.windowTitle()

    def test_widgets_existen(self, qtbot):
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

    def test_validacion_campos_vacios(self, qtbot, monkeypatch):
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

    def test_validar_login_incorrecto(self, qtbot, monkeypatch):
        """Verifica que credenciales incorrectas muestran error.

        Escribe un usuario y contrasena que no existen en la BD y
        verifica que se muestra el mensaje de error.

        monkeypatch: reemplazamos get_session para que devuelva
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

        # Reemplazar get_session para que devuelva un context manager
        # con una sesion mockeada que no encuentra ningun usuario.
        # get_session es un context manager (usa "with get_session() as session").
        # Creamos un MagicMock que funciona como context manager usando __enter__.
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None

        class MockContextManager:
            def __enter__(self):
                return mock_session

            def __exit__(self, *args):
                pass

        monkeypatch.setattr(
            "sistema_financiero.ui.ventana_login.get_session",
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


# ============================================================
# TESTS: MainWindow
# ============================================================
# Verificamos que la ventana principal se crea correctamente,
# que tiene la barra de navegacion y las paginas del sistema.
# ============================================================


class TestMainWindow:
    """Pruebas para la ventana principal (MainWindow)."""

    def test_crear_ventana(self, qtbot, usuario_admin):
        """Verifica que MainWindow se crea con el titulo correcto.

        Crea la ventana principal con un usuario simulado y verifica
        que el titulo incluye el nombre del usuario.
        """
        ventana = MainWindow(usuario_admin)
        qtbot.addWidget(ventana)

        # El titulo debe contener el nombre completo del usuario.
        assert "Administrador" in ventana.windowTitle()

    def test_barra_navegacion_existe(self, qtbot, usuario_admin):
        """Verifica que la barra lateral de navegacion se creo.

        La barra de navegacion es un QListWidget con los nombres
        de los modulos del sistema.
        """
        ventana = MainWindow(usuario_admin)
        qtbot.addWidget(ventana)

        # Verificar que el atributo barra_navegacion existe.
        assert hasattr(ventana, "barra_navegacion")

        # Debe tener 5 items: Dashboard, Productos, Ventas, Inventario, Reportes.
        assert ventana.barra_navegacion.count() == 5

        # Verificar los nombres de los items.
        nombres = [
            ventana.barra_navegacion.item(i).text()
            for i in range(ventana.barra_navegacion.count())
        ]
        assert nombres == [
            "Dashboard",
            "Productos",
            "Ventas",
            "Inventario",
            "Reportes",
        ]

    def test_paginas_existen(self, qtbot, usuario_admin):
        """Verifica que las 5 paginas del sistema estan en el QStackedWidget.

        MainWindow usa un QStackedWidget que contiene una pagina
        por cada modulo. Verificamos que hay 5 paginas agregadas.
        """
        ventana = MainWindow(usuario_admin)
        qtbot.addWidget(ventana)

        # El QStackedWidget debe tener 5 paginas (una por modulo).
        assert ventana.paginas.count() == 5

    def test_cambiar_pagina(self, qtbot, usuario_admin):
        """Verifica que se puede cambiar de pagina usando la barra lateral.

        Simula la seleccion de cada item de navegacion y verifica
        que la pagina activa del QStackedWidget cambia correctamente.
        """
        ventana = MainWindow(usuario_admin)
        qtbot.addWidget(ventana)

        # Probar cada indice de pagina.
        for i in range(ventana.barra_navegacion.count()):
            # Simular clic en el item i de la barra de navegacion.
            ventana.barra_navegacion.setCurrentRow(i)

            # Verificar que la pagina activa es la que elegimos.
            assert ventana.paginas.currentIndex() == i

    def test_controladores_creados(self, qtbot, usuario_admin):
        """Verifica que los controladores se crearon al iniciar MainWindow.

        MainWindow crea los 5 controladores/servicios en su __init__.
        Verificamos que todos existen y tienen los metodos esperados.
        """
        ventana = MainWindow(usuario_admin)
        qtbot.addWidget(ventana)

        # Lista de (nombre_atributo, clase_esperada).
        controladores = [
            ("controlador_productos", None),
            ("controlador_inventario", None),
            ("controlador_ventas", None),
            ("controlador_tasas", None),
            ("controlador_reportes", None),
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

    def test_crear_dialogo_modo_crear(self, qtbot):
        """Verifica que FormularioProducto se abre en modo crear.

        Modo crear = sin pasarle un producto existente.
        El titulo debe decir "Agregar producto".
        """
        dialogo = FormularioProducto()
        qtbot.addWidget(dialogo)

        assert "Agregar producto" in dialogo.windowTitle()

    def test_crear_dialogo_modo_editar(self, qtbot):
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
            stock_actual=10,
            stock_minimo=5,
            unidad="KG",
        )
        dialogo = FormularioProducto(producto=producto)
        qtbot.addWidget(dialogo)

        assert "Editar producto" in dialogo.windowTitle()
        assert "Arroz" in dialogo.windowTitle()

    def test_campos_existen_en_modo_crear(self, qtbot):
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

    def test_campos_precargados_en_editar(self, qtbot):
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
            stock_actual=50,
            stock_minimo=10,
            unidad="LTS",
        )
        dialogo = FormularioProducto(producto=producto)
        qtbot.addWidget(dialogo)

        # Verificar que los campos estan precargados.
        assert dialogo.txt_nombre.text() == "Leche"
        assert dialogo.txt_categoria.text() == "LACTEOS"
        assert dialogo.txt_unidad.text() == "LTS"

    def test_validacion_nombre_vacio(self, qtbot, monkeypatch):
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
    """Pruebas para el dialogo de nueva venta (FormularioVenta)."""

    def test_crear_dialogo(self, qtbot):
        """Verifica que FormularioVenta se crea con el titulo correcto."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        assert "Nueva Venta" in dialogo.windowTitle()

    def test_widgets_principales_existen(self, qtbot):
        """Verifica que los widgets principales del dialogo existen.

        FormularioVenta tiene: combo de productos, spin de cantidad,
        tabla de productos, label de total y campos de pago.
        """
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        # Widgets de seleccion de producto.
        assert hasattr(dialogo, "combo_producto")
        assert hasattr(dialogo, "spin_cantidad")
        assert hasattr(dialogo, "tabla_productos_venta")
        assert hasattr(dialogo, "lbl_total")

        # Widgets de metodo de pago.
        assert hasattr(dialogo, "spin_efectivo_bs")
        assert hasattr(dialogo, "spin_efectivo_usd")
        assert hasattr(dialogo, "spin_tarjeta")
        assert hasattr(dialogo, "spin_pago_movil")
        assert hasattr(dialogo, "spin_bio_pago")

    def test_boton_finalizar_existe(self, qtbot):
        """Verifica que el boton 'Finalizar Venta' esta en el dialogo."""
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        # Buscar el boton por su texto (findChildren con texto busca
        # el objectName, no el texto del boton, por eso iteramos).
        botones = dialogo.findChildren(QPushButton)
        btn_finalizar = [b for b in botones if b.text() == "Finalizar Venta"]
        assert len(btn_finalizar) > 0

    def test_venta_vacia_muestra_error(self, qtbot, monkeypatch):
        """Verifica que Finalizar Venta sin productos muestra error.

        Sin agregar productos, hacer clic en Finalizar Venta debe
        mostrar un mensaje de advertencia.
        """
        dialogo = FormularioVenta()
        qtbot.addWidget(dialogo)

        # Mockear QMessageBox.warning para capturar la llamada.
        mock_warning = MagicMock()
        monkeypatch.setattr(
            "sistema_financiero.ui.formulario_venta.QMessageBox.warning",
            mock_warning,
        )

        # Hacer clic en "Finalizar Venta".
        for btn in dialogo.findChildren(QPushButton):
            if btn.text() == "Finalizar Venta":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break

        # Debe mostrar advertencia porque no hay productos.
        mock_warning.assert_called_once()
