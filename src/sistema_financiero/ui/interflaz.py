# ============================================================
# IMPORTACIONES
# ============================================================
# bcrypt: lo usamos para verificar la contrasena del usuario
#   en el login. Comparamos el hash guardado con el ingresado.
from datetime import date, datetime
from decimal import Decimal

import bcrypt

# pyqtgraph: libreria de graficos cientificos para PyQt6.
#   - PlotWidget: widget de grafico incrustable (igual que un QLabel pero dibuja graficos).
#   - BarGraphItem: dibuja barras verticales (como un grafico de barras).
#
# Por que pyqtgraph y no matplotlib?
#   - matplotlib es lento y pesado para apps en tiempo real.
#   - pyqtgraph es nativo de Qt (se integra directamente con PyQt6).
#   - pyqtgraph es mas rapido para graficos simples como barras y lineas.
import pyqtgraph as pg
from PyQt6.QtCore import QDate, QSize, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlmodel import select

from ..core.inventario_service import InventarioService
from ..core.producto_controller import ProductoController
from ..core.reporte_service import ReporteService
from ..core.tasa_cambio_service import TasaCambioService
from ..core.venta_controller import VentaController
from ..models import Producto, Usuario, Venta, get_session

# ============================================================
# ARCHIVO: ui/interflaz.py  (INTERFAZ DE USUARIO)
# ============================================================
# Este archivo contiene TODOS los widgets visuales de la aplicacion.
# Piensa en esto como el "escenario" donde se mueven los actores.
#
# LoginDialog: la puerta de entrada (pide usuario y contrasena).
# MainWindow:  el escenario principal con navegacion y vistas.
#
# REGLA IMPORTANTE:
#   - La UI SOLO llama a los metodos de core/.
#   - La UI NUNCA debe contener logica de negocio directamente.
#   - Si necesitas una validacion o calculo, hazlo en core/ y llamalo desde aca.
# ============================================================


# ============================================================
# LOGINDIALOG: Ventana de inicio de sesion
# ============================================================
# QDialog es una ventana MODAL: bloquea la interaccion con otras
#   ventanas hasta que se cierra. Ideal para login porque obliga
#   al usuario a identificarse antes de usar el sistema.
#
# Flujo:
#   1. __main__.py crea LoginDialog y lo muestra con .exec()
#   2. El usuario ingresa usuario + contrasena
#   3. _validar_login() verifica contra la BD usando bcrypt
#   4. Si es correcto → self.accept() (cierra el dialogo con exito)
#   5. Si es incorrecto → QMessageBox.warning() (muestra error)
#   6. __main__.py revisa si login fue aceptado o rechazado
# ============================================================
class LoginDialog(QDialog):
    # Type hint: le decimos a Python que usuario_actual sera un objeto Usuario.
    # Aunque se inicializa como None, cuando el login es exitoso tendra un valor.
    usuario_actual: Usuario

    # __init__: constructor de la clase. Se ejecuta cuando se crea el dialogo.
    def __init__(self) -> None:
        # super().__init__(): llama al constructor de QDialog (clase padre).
        # Esto asegura que la ventana se configure correctamente.
        super().__init__()

        # Inicializamos usuario_actual como None.
        # El comentario "type: ignore[assignment]" en la siguiente linea
        # le dice a mypy que ignore que None no es del tipo Usuario.
        self.usuario_actual = None  # type: ignore[assignment]

        # setWindowTitle: texto que aparece en la barra de titulo de la ventana.
        self.setWindowTitle("Sistema Financiero — Iniciar Sesión")

        # setFixedSize: la ventana NO se puede redimensionar (ancho x alto).
        # Elegimos 360x200 porque es suficientemente grande para el formulario
        # pero no ocupa toda la pantalla.
        self.setFixedSize(360, 200)

        # Llamamos al metodo que construye los widgets visuales.
        self._setup_ui()

    # _setup_ui: metodo privado (empieza con _) que construye la interfaz.
    # Lo separamos del __init__ para mantener el codigo organizado.
    def _setup_ui(self) -> None:
        """Construye los campos de usuario, contrasena y botones."""

        # QVBoxLayout: layout vertical. Los widgets se apilan de arriba a abajo.
        # Le pasamos self (el QDialog) como padre, asi el layout se asocia a la ventana.
        layout = QVBoxLayout(self)

        # QFormLayout: layout de formulario. Cada fila tiene una etiqueta a la izquierda
        #   y un campo a la derecha. Ideal para formularios como login.
        form = QFormLayout()

        # QLineEdit: campo de texto de una sola linea.
        self.txt_usuario = QLineEdit()
        # setPlaceholderText: texto gris que aparece dentro del campo cuando esta vacio.
        # Sirve como ayuda para el usuario.
        self.txt_usuario.setPlaceholderText("Nombre de usuario")

        self.txt_contrasena = QLineEdit()
        self.txt_contrasena.setPlaceholderText("Contraseña")
        # setEchoMode: controla como se muestra el texto ingresado.
        # Password: muestra asteriscos en lugar del texto real (seguridad).
        self.txt_contrasena.setEchoMode(QLineEdit.EchoMode.Password)

        # addRow: agrega una fila al formulario (etiqueta, campo).
        form.addRow("Usuario:", self.txt_usuario)
        form.addRow("Contraseña:", self.txt_contrasena)

        # addLayout: agrega el formulario al layout vertical principal.
        layout.addLayout(form)

        # QHBoxLayout: layout horizontal. Los botones estaran uno al lado del otro.
        btn_layout = QHBoxLayout()

        # QPushButton: boton clickeable.
        btn_ingresar = QPushButton("Ingresar")
        # clicked.connect(): conecta la senal "click" del boton a una funcion.
        # Cuando el usuario hace clic, se ejecuta self._validar_login().
        # Esto se llama "programacion orientada a eventos".
        btn_ingresar.clicked.connect(self._validar_login)

        btn_salir = QPushButton("Salir")
        # reject(): cierra el dialogo con codigo de "rechazado".
        # __main__.py detecta esto y cierra la aplicacion.
        btn_salir.clicked.connect(self.reject)

        # Agregar los botones al layout horizontal.
        btn_layout.addWidget(btn_ingresar)
        btn_layout.addWidget(btn_salir)

        # Agregar el layout de botones al layout vertical principal.
        layout.addLayout(btn_layout)

    # _validar_login: verifica las credenciales contra la base de datos.
    def _validar_login(self) -> None:
        """Verifica credenciales contra la BD."""
        # .text(): obtiene el texto ingresado en el QLineEdit.
        # .strip(): elimina espacios al inicio y final.
        usuario = self.txt_usuario.text().strip()
        contrasena = self.txt_contrasena.text().strip()

        # Validar que los campos no esten vacios.
        if not usuario or not contrasena:
            # QMessageBox.warning(): muestra una ventana emergente de advertencia.
            # Parametros: (widget_padre, titulo, mensaje).
            QMessageBox.warning(self, "Error", "Usuario y contraseña son requeridos.")
            return  # Salir del metodo sin hacer nada mas.

        # get_session(): abre una conexion a la base de datos.
        # "with" asegura que la sesion se cierre automaticamente al terminar.
        with get_session() as session:
            # session.exec(): ejecuta una consulta SELECT.
            # select(Usuario): selecciona TODOS los usuarios.
            # .where(Usuario.usuario == usuario): filtra por el nombre ingresado.
            # .first(): devuelve el primer resultado (o None si no existe).
            user = session.exec(select(Usuario).where(Usuario.usuario == usuario)).first()

        # Verificar si el usuario existe Y la contrasena coincide.
        # bcrypt.checkpw(): compara la contrasena ingresada (en bytes) con
        #   el hash guardado en la BD. Devuelve True si coinciden.
        if user is None or not bcrypt.checkpw(
            contrasena.encode("utf-8"),  # Convertir string a bytes.
            user.contrasena.encode("utf-8"),  # El hash tambien debe ser bytes.
        ):
            QMessageBox.warning(self, "Error", "Usuario o contraseña incorrectos.")
            return  # No revelamos si el usuario existe o no (seguridad).

        # Guardar el usuario logueado para que MainWindow lo use.
        self.usuario_actual = user

        # accept(): cierra el dialogo con codigo de "aceptado".
        # __main__.py detecta esto y abre MainWindow.
        self.accept()


# ============================================================
# MAINWINDOW: Ventana principal de la aplicacion
# ============================================================
# QMainWindow es una ventana principal COMPLETA que ya incluye:
#   - Barra de titulo (arriba)
#   - Barra de menu (opcional)
#   - Barra de herramientas (opcional)
#   - Widget central (obligatorio) → el contenido principal
#   - Barra de estado (abajo)
#
# Estructura visual que vamos a crear:
#
#   ┌──────────────────────────────────────────┐
#   │  Sistema Financiero — Administrador      │ ← Barra de titulo
#   ├──────────┬───────────────────────────────┤
#   │          │                               │
#   │  Dashboard│  [Aqui va la vista activa]    │
#   │  Productos│                               │
#   │  Ventas   │    QStackedWidget             │
#   │  Inventario│   (solo se ve 1 pagina)      │
#   │  Reportes │                               │
#   │          │                               │
#   │  Cerrar   │                               │
#   │  Sesion   │                               │
#   ├──────────┴───────────────────────────────┤
#   │  Usuario: admin  |  Sistema Financiero   │ ← Barra de estado
#   └──────────────────────────────────────────┘
#
# Por que QStackedWidget?
#   - Es como un "mazo de cartas": solo se ve la carta de arriba.
#   - Cuando el usuario selecciona "Productos" en la lista lateral,
#     mostramos la pagina de productos del QStackedWidget.
#   - Es mas eficiente que crear/destruir widgets cada vez.
# ============================================================
class MainWindow(QMainWindow):
    # __init__: recibe el usuario que hizo login.
    def __init__(self, usuario: Usuario) -> None:
        # Llamar al constructor de QMainWindow.
        super().__init__()

        # Guardar el usuario logueado para usarlo en toda la ventana.
        self.usuario_actual = usuario

        # Establecer el titulo de la ventana.
        # Muestra: "Sistema Financiero — Administrador" (o el nombre del usuario).
        self.setWindowTitle(f"Sistema Financiero — {usuario.nombre_completo or usuario.usuario}")

        # Tamanio inicial de la ventana: 1024x680 pixeles.
        # El usuario puede redimensionarla porque NO usamos setFixedSize.
        self.resize(1024, 680)

        # ----------------------------------------------------------
        # CREAR LOS CONTROLADORES (UNA SOLA VEZ)
        # ----------------------------------------------------------
        # Los guardamos como atributos de self para usarlos en cualquier
        # metodo de la clase. Si los creasemos dentro de cada metodo,
        # se estarian creando y destruyendo constantemente (gasto de memoria).
        self.controlador_productos = ProductoController()
        self.controlador_inventario = InventarioService()
        self.controlador_tasas = TasaCambioService()
        self.controlador_ventas = VentaController()
        self.controlador_reportes = ReporteService()

        # ----------------------------------------------------------
        # CONSTRUIR LA INTERFAZ
        # ----------------------------------------------------------
        # Llamamos al metodo que arma toda la interfaz grafica.
        self._setup_ui()

    # ------------------------------------------------------------------
    # _setup_ui: construye todos los widgets de la ventana principal.
    # ------------------------------------------------------------------
    # Este metodo es el "arquitecto" de la interfaz:
    #   1. Crea la barra lateral (menu de navegacion)
    #   2. Crea las paginas de contenido (una por cada modulo)
    #   3. Las organiza en un layout horizontal
    #   4. Configura la barra de estado
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        """Construye la barra lateral, las vistas y la barra de estado."""

        # ----------------------------------------------------------
        # 1. CREAR EL WIDGET CENTRAL Y SU LAYOUT PRINCIPAL
        # ----------------------------------------------------------
        # QMainWindow necesita un "widget central" obligatoriamente.
        # Creamos un QWidget generico que contendra TODO el contenido.
        widget_central = QWidget()
        # QHBoxLayout: los elementos se colocan en HORIZONTAL.
        # A la izquierda: la lista de navegacion.
        # A la derecha: el QStackedWidget con las vistas.
        layout_principal = QHBoxLayout(widget_central)
        # Eliminar los margenes para que la barra lateral se vea pegada al borde.
        layout_principal.setContentsMargins(0, 0, 0, 0)
        # Sin espacio entre los widgets.
        layout_principal.setSpacing(0)

        # ----------------------------------------------------------
        # 2. BARRA LATERAL DE NAVEGACION (QListWidget)
        # ----------------------------------------------------------
        # QListWidget: una lista vertical donde cada item es seleccionable.
        # Vamos a usarla como menu de navegacion.
        self.barra_navegacion = QListWidget()
        # Ancho fijo de 200 pixeles. El alto se ajusta automaticamente.
        self.barra_navegacion.setFixedWidth(200)
        # Color de fondo oscuro (valor hexadecimal RGB).
        # #1a1a2e es un azul oscuro elegante.
        self.barra_navegacion.setStyleSheet("background-color: #1a1a2e; color: white;")
        # Tamanio de cada item de la lista (ancho x alto).
        self.barra_navegacion.setIconSize(QSize(0, 0))
        # Espaciado entre items.
        self.barra_navegacion.setSpacing(5)

        # Crear los items del menu con sus nombres.
        # Cada item tiene un texto que identifica la pagina.
        items_menu = ["Dashboard", "Productos", "Ventas", "Inventario", "Reportes"]

        # Recorrer la lista de nombres y crear un QListWidgetItem por cada uno.
        for nombre_item in items_menu:
            # QListWidgetItem: un elemento de la lista.
            item = QListWidgetItem(nombre_item)
            # Alinear el texto en el CENTRO del item.
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # Agregar el item a la barra de navegacion.
            self.barra_navegacion.addItem(item)

        # Conectar la senal "currentRowChanged" al metodo que cambia de pagina.
        # Cada vez que el usuario selecciona un item diferente, se ejecuta
        # self._cambiar_pagina() con el indice del item seleccionado.
        # El indice empieza en 0 (Dashboard = 0, Productos = 1, etc.).
        self.barra_navegacion.currentRowChanged.connect(self._cambiar_pagina)

        # Agregar la barra lateral al layout principal (izquierda).
        layout_principal.addWidget(self.barra_navegacion)

        # ----------------------------------------------------------
        # 3. QStackedWidget: contenedor de paginas
        # ----------------------------------------------------------
        # QStackedWidget solo muestra UNA pagina a la vez.
        # Las paginas se agregan con addWidget() y se muestran con setCurrentIndex().
        self.paginas = QStackedWidget()
        # Fondo blanco para el area de contenido.
        self.paginas.setStyleSheet("background-color: #f5f5f5;")

        # Crear cada pagina y agregarla al QStackedWidget.
        # El ORDEN debe coincidir con items_menu.
        self._crear_pagina_dashboard()
        self._crear_pagina_productos()
        self._crear_pagina_ventas()
        self._crear_pagina_inventario()
        self._crear_pagina_reportes()

        # Agregar el QStackedWidget al layout principal (derecha).
        # Ocupa todo el espacio restante porque QStackedWidget tiene
        # QSizePolicy.Expanding por defecto.
        layout_principal.addWidget(self.paginas, 1)  # El 1 = factor de estiramiento.

        # Establecer el widget central de la ventana.
        self.setCentralWidget(widget_central)

        # ----------------------------------------------------------
        # 4. BARRA DE ESTADO
        # ----------------------------------------------------------
        # QStatusBar: barra en la parte inferior que muestra informacion.
        # QMainWindow ya crea una barra de estado por defecto.
        barra_estado = QStatusBar()
        self.setStatusBar(barra_estado)

        # Mostrar el nombre del usuario logueado en la barra de estado.
        # Esto le recuerda al usuario quien esta usando el sistema.
        barra_estado.showMessage(
            f"Usuario: {self.usuario_actual.usuario} | {self.usuario_actual.nombre_completo}"
        )

        # Seleccionar el primer item (Dashboard) por defecto.
        # Esto muestra la pagina de inicio cuando se abre la ventana.
        self.barra_navegacion.setCurrentRow(0)

    # ------------------------------------------------------------------
    # _cambiar_pagina: cambia la pagina visible en el QStackedWidget
    # ------------------------------------------------------------------
    # Este metodo se ejecuta AUTOMATICAMENTE cuando el usuario hace clic
    # en un item de la barra lateral (gracias a currentRowChanged).
    #
    # Parametro: indice (int) = posicion del item seleccionado (0, 1, 2...).
    #   Coincide con el orden en que agregamos las paginas al QStackedWidget.
    # ------------------------------------------------------------------
    def _cambiar_pagina(self, indice: int) -> None:
        """Muestra la pagina del QStackedWidget que corresponde al indice."""
        # setCurrentIndex(): muestra la pagina en la posicion "indice".
        # La pagina 0 = Dashboard, 1 = Productos, etc.
        self.paginas.setCurrentIndex(indice)

    # ================================================================
    # PAGINAS DEL SISTEMA
    # ================================================================
    # Cada metodo _crear_pagina_*() crea un QWidget con el contenido
    # de ese modulo y lo agrega al QStackedWidget.
    #
    # Por ahora son PAGINAS TEMPORALES (placeholder) con un titulo.
    # Cuando implementes los modulos completos, reemplazaras el contenido
    # de estos widgets con tablas, formularios, etc.
    #
    # La estructura basica de cada pagina es:
    #   1. QWidget como contenedor principal
    #   2. QVBoxLayout para organizar los elementos verticalmente
    #   3. QLabel con el titulo del modulo
    #   4. addWidget() al QStackedWidget
    # ================================================================

    # ------------------------------------------------------------------
    # PAGINA: Dashboard (inicio / resumen)
    # ------------------------------------------------------------------
    # Esta es la PRIMERA pagina que ve el usuario al iniciar sesion.
    #
    # Contenido:
    #   1. 4 tarjetas resumen (Ventas Hoy, Stock Bajo, Sin Stock, Tasa BCV).
    #   2. Grafico de barras (pyqtgraph) con ventas de los ultimos 7 dias.
    #   3. Tabla de productos con stock bajo.
    #
    # Por que QFrame para las tarjetas?
    #   - QFrame proporciona bordes y fondos personalizables via stylesheet.
    #   - Es mas ligero que QGroupBox (que agrega un titulo que no necesitamos).
    #   - Podemos darle estilo CSS (background, border-radius, sombras).
    # ------------------------------------------------------------------
    def _crear_pagina_dashboard(self) -> None:
        """Crea la pagina de inicio con resumen, graficos y alertas."""
        # QWidget: contenedor generico para esta pagina.
        pagina = QWidget()
        # Layout vertical: tarjetas → grafico → tabla.
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # ----------------------------------------------------------
        # TITULO DE LA PAGINA
        # ----------------------------------------------------------
        lbl_titulo = QLabel("Dashboard")
        fuente_titulo = QFont()
        fuente_titulo.setPointSize(24)
        fuente_titulo.setBold(True)
        lbl_titulo.setFont(fuente_titulo)
        layout.addWidget(lbl_titulo)

        # ----------------------------------------------------------
        # TARJETAS DE RESUMEN
        # ----------------------------------------------------------
        # Extraemos la creacion de tarjetas a un metodo separado
        # (_crear_tarjetas_resumen) para mantener _crear_pagina_dashboard
        # dentro del limite de 50 declaraciones que exige Ruff.
        layout.addLayout(self._crear_tarjetas_resumen())

        # ----------------------------------------------------------
        # GRAFICO DE VENTAS (pyqtgraph)
        # ----------------------------------------------------------
        # pg.PlotWidget: widget que dibuja un grafico (barras, lineas, etc).
        # Se comporta como cualquier otro QWidget (se agrega con addWidget).
        lbl_grafico = QLabel("Ventas de los Ultimos 7 Dias")
        lbl_grafico.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(lbl_grafico)

        # Crear el widget de grafico.
        # setBackground("w"): fondo blanco (w = white).
        # showGrid(x=True, y=True): mostrar cuadricula.
        self.grafico_ventas = pg.PlotWidget()
        self.grafico_ventas.setBackground("w")
        self.grafico_ventas.showGrid(x=True, y=True, alpha=0.3)
        # Altura fija del grafico.
        self.grafico_ventas.setMinimumHeight(250)
        layout.addWidget(self.grafico_ventas)

        # ----------------------------------------------------------
        # TABLA: Productos con stock bajo
        # ----------------------------------------------------------
        lbl_stock = QLabel("Productos con Stock Bajo")
        lbl_stock.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(lbl_stock)

        # QTableWidget: tabla con columnas editables.
        self.tabla_stock_bajo = QTableWidget()
        self.tabla_stock_bajo.setColumnCount(5)
        self.tabla_stock_bajo.setHorizontalHeaderLabels(
            ["Producto", "Categoria", "Stock Actual", "Stock Minimo", "Estado"]
        )
        # El encabezado se estira para llenar el ancho disponible.
        self.tabla_stock_bajo.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        # No permitir edicion.
        self.tabla_stock_bajo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Seleccionar filas completas.
        self.tabla_stock_bajo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # Altura maxima de la tabla.
        self.tabla_stock_bajo.setMaximumHeight(200)
        layout.addWidget(self.tabla_stock_bajo)

        # Espacio flexible al final.
        layout.addStretch()

        # Agregar la pagina al QStackedWidget (indice 0).
        self.paginas.addWidget(pagina)

        # ----------------------------------------------------------
        # Cargar datos iniciales en el dashboard
        # ----------------------------------------------------------
        # Llenamos las tarjetas, el grafico y la tabla con datos reales.
        self._refrescar_dashboard()

    # ------------------------------------------------------------------
    # _crear_tarjetas_resumen(): crea las 4 tarjetas de resumen
    # ------------------------------------------------------------------
    # Cada tarjeta es un QFrame con estilo CSS que contiene:
    #   - Un icono (grande, arriba)
    #   - Un titulo (descripcion)
    #   - Un valor numerico (grande, en negrita)
    #
    # Separamos esto en un metodo aparte para evitar que
    # _crear_pagina_dashboard() exceda las 50 declaraciones
    # (limite de Ruff/PLR0915).
    #
    # Retorna: QHBoxLayout con las 4 tarjetas.
    # ------------------------------------------------------------------
    def _crear_tarjetas_resumen(self) -> QHBoxLayout:
        """Crea las 4 tarjetas de resumen (Ventas Hoy, Stock Bajo, Sin Stock, Tasa BCV)."""
        fila_tarjetas = QHBoxLayout()
        fila_tarjetas.setSpacing(15)

        datos_tarjetas = [
            ("ventas_hoy", "Ventas Hoy", "💰"),
            ("stock_bajo", "Stock Bajo", "⚠️"),
            ("sin_stock", "Sin Stock", "🚫"),
            ("tasa_bcv", "Tasa BCV", "💵"),
        ]

        self._dashboard_labels = {}

        for clave, titulo, icono in datos_tarjetas:
            tarjeta = QFrame()
            tarjeta.setStyleSheet(
                "QFrame { background-color: white; border-radius: 10px; padding: 15px; }"
            )
            tarjeta.setMinimumHeight(100)

            layout_tarjeta = QVBoxLayout(tarjeta)
            layout_tarjeta.setContentsMargins(10, 10, 10, 10)
            layout_tarjeta.setSpacing(5)

            lbl_icono = QLabel(icono)
            fuente_icono = QFont()
            fuente_icono.setPointSize(28)
            lbl_icono.setFont(fuente_icono)
            layout_tarjeta.addWidget(lbl_icono)

            lbl_titulo_tarjeta = QLabel(titulo)
            lbl_titulo_tarjeta.setStyleSheet("color: #666; font-size: 12px;")
            layout_tarjeta.addWidget(lbl_titulo_tarjeta)

            lbl_valor = QLabel("—")
            lbl_valor.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a1a2e;")
            layout_tarjeta.addWidget(lbl_valor)

            self._dashboard_labels[clave] = lbl_valor

            fila_tarjetas.addWidget(tarjeta)

        return fila_tarjetas

    # ------------------------------------------------------------------
    # _refrescar_dashboard(): actualiza todos los datos del dashboard
    # ------------------------------------------------------------------
    # Se llama al CREAR la pagina y puede llamarse manualmente si se
    # necesita refrescar (ej: despues de una venta).
    #
    # Que actualiza:
    #   1. Totales de las tarjetas (ventas hoy, stock, tasa).
    #   2. Grafico de ventas de los ultimos 7 dias.
    #   3. Tabla de productos con stock bajo.
    # ------------------------------------------------------------------
    def _refrescar_dashboard(self) -> None:
        """Refresca los datos del dashboard (tarjetas, grafico, tabla)."""
        # ----------------------------------------------------------
        # 1. Calcular ventas del dia de hoy
        # ----------------------------------------------------------
        # Obtenemos la fecha actual.
        hoy = datetime.now()
        desde_hoy = datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0)
        hasta_hoy = datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59)

        with get_session() as session:
            ventas_hoy = session.exec(
                select(Venta).where(
                    Venta.fecha_venta >= desde_hoy,  # type: ignore[operator]
                    Venta.fecha_venta <= hasta_hoy,  # type: ignore[operator]
                    Venta.estado == "COMPLETADA",
                )
            ).all()
            total_ventas_hoy = sum(v.total_bs for v in ventas_hoy)

            # Contar stock bajo y sin stock.
            productos = session.exec(select(Producto)).all()
            stock_bajo = sum(1 for p in productos if 0 < p.stock_actual <= p.stock_minimo)
            sin_stock = sum(1 for p in productos if p.stock_actual == 0)

            # Obtener la tasa activa.
            tasa = self.controlador_tasas.tasa_activa()

        # Actualizar las etiquetas de las tarjetas.
        self._dashboard_labels["ventas_hoy"].setText(f"Bs. {total_ventas_hoy:,.2f}")
        self._dashboard_labels["stock_bajo"].setText(f"{stock_bajo} productos")
        self._dashboard_labels["sin_stock"].setText(f"{sin_stock} productos")
        self._dashboard_labels["tasa_bcv"].setText(
            f"Bs. {float(tasa.tasa_venta):,.2f}" if tasa else "Sin tasa"
        )

        # ----------------------------------------------------------
        # 2. Grafico de ventas de los ultimos 7 dias
        # ----------------------------------------------------------
        # Para cada uno de los ultimos 7 dias, calculamos el total de ventas.
        # Usamos una lista de 7 fechas (de hoy hacia atras).
        fechas: list[str] = []
        ventas_diarias: list[float] = []
        for i in range(6, -1, -1):  # 6, 5, 4, 3, 2, 1, 0 (de mas viejo a mas nuevo)
            # Restar i dias a la fecha actual.
            dia = date.today()
            # QDate.addDays(): suma/resta dias a una fecha.
            fecha_dia = QDate(dia.year, dia.month, dia.day).addDays(-i)
            desde = datetime(fecha_dia.year(), fecha_dia.month(), fecha_dia.day(), 0, 0, 0)
            hasta = datetime(fecha_dia.year(), fecha_dia.month(), fecha_dia.day(), 23, 59, 59)

            with get_session() as session:
                ventas_del_dia = session.exec(
                    select(Venta).where(
                        Venta.fecha_venta >= desde,  # type: ignore[operator]
                        Venta.fecha_venta <= hasta,  # type: ignore[operator]
                        Venta.estado == "COMPLETADA",
                    )
                ).all()
                total = sum(v.total_bs for v in ventas_del_dia)

            # Etiqueta de la fecha (dd/mm).
            fechas.append(fecha_dia.toString("dd/MM"))
            ventas_diarias.append(float(total))

        # Limpiar el grafico anterior.
        self.grafico_ventas.clear()

        # Crear el grafico de barras.
        # BarGraphItem recibe:
        #   - x: posiciones de las barras en el eje X.
        #   - height: alturas de las barras (valores de ventas).
        #   - width: ancho de cada barra (0.6 = 60% del espacio entre barras).
        #   - brush: color de relleno.
        barras = pg.BarGraphItem(
            x=list(range(len(ventas_diarias))),
            height=ventas_diarias,
            width=0.6,
            brush="#4CAF50",  # Verde.
        )
        self.grafico_ventas.addItem(barras)

        # Configurar los ejes.
        # Eje X: etiquetas de fechas (rotadas 45 grados si hay muchas).
        eje_x = self.grafico_ventas.getAxis("bottom")
        eje_x.setTicks([list(enumerate(fechas))])
        # Eje Y: etiqueta "Bs."
        eje_y = self.grafico_ventas.getAxis("left")
        eje_y.setLabel("Bs.")

        # Ajustar los limites del grafico para que se vea bien.
        self.grafico_ventas.setLimits(
            xMin=-0.5,
            xMax=len(ventas_diarias) - 0.5,
        )

        # ----------------------------------------------------------
        # 3. Tabla de productos con stock bajo (extraido a metodo)
        # ----------------------------------------------------------
        self._refrescar_tabla_stock_bajo()

    # ------------------------------------------------------------------
    # _refrescar_tabla_stock_bajo(): llena la tabla de stock bajo
    # ------------------------------------------------------------------
    # Extraemos esto a un metodo separado para reducir el numero de
    # declaraciones en _refrescar_dashboard (cumplir PLR0915).
    # ------------------------------------------------------------------
    def _refrescar_tabla_stock_bajo(self) -> None:
        """Llena la tabla de productos con stock bajo / sin stock en el dashboard."""
        with get_session() as session:
            todos = session.exec(select(Producto)).all()
            productos_alerta = [p for p in todos if p.stock_actual <= p.stock_minimo]

        self.tabla_stock_bajo.setRowCount(len(productos_alerta))
        for fila, prod in enumerate(productos_alerta):
            self.tabla_stock_bajo.setItem(fila, 0, QTableWidgetItem(prod.nombre_producto))
            self.tabla_stock_bajo.setItem(fila, 1, QTableWidgetItem(prod.categoria or ""))
            self.tabla_stock_bajo.setItem(fila, 2, QTableWidgetItem(str(prod.stock_actual)))
            self.tabla_stock_bajo.setItem(fila, 3, QTableWidgetItem(str(prod.stock_minimo)))
            estado = "SIN STOCK" if prod.stock_actual == 0 else "STOCK BAJO"
            item_estado = QTableWidgetItem(estado)
            if prod.stock_actual == 0:
                item_estado.setBackground(Qt.GlobalColor.red)
                item_estado.setForeground(Qt.GlobalColor.white)
            else:
                item_estado.setBackground(Qt.GlobalColor.darkYellow)
                item_estado.setForeground(Qt.GlobalColor.white)
            self.tabla_stock_bajo.setItem(fila, 4, item_estado)

        self.tabla_stock_bajo.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # PAGINA: Productos (CRUD de productos)
    # ------------------------------------------------------------------
    # Esta pagina tiene:
    #   1. Barra superior: buscador + botones de accion
    #   2. Tabla con todos los productos
    #   3. Doble clic en una fila → abre el dialogo de edicion
    #
    # Flujo de datos:
    #   UI (tabla) ←→ ProductoController ←→ BD (SQLite)
    #
    # La UI NUNCA toca la BD directamente. Siempre a traves del controlador.
    # ------------------------------------------------------------------
    def _crear_pagina_productos(self) -> None:
        """Crea la pagina de gestion de productos con tabla y botones."""
        pagina = QWidget()
        # Layout vertical: titulo → barra de herramientas → tabla
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(40, 40, 40, 40)

        # ----------------------------------------------------------
        # TITULO DE LA PAGINA
        # ----------------------------------------------------------
        lbl_titulo = QLabel("Productos")
        fuente = QFont()
        fuente.setPointSize(24)
        fuente.setBold(True)
        lbl_titulo.setFont(fuente)
        layout.addWidget(lbl_titulo)

        # ----------------------------------------------------------
        # BARRA DE HERRAMIENTAS (buscador + botones)
        # ----------------------------------------------------------
        # QHBoxLayout: el buscador a la izquierda, los botones a la derecha.
        barra = QHBoxLayout()

        # QLineEdit: campo de busqueda en tiempo real.
        self.txt_buscar_producto = QLineEdit()
        self.txt_buscar_producto.setPlaceholderText("Buscar producto por nombre o categoria...")
        # textChanged: se dispara CADA VEZ que el usuario escribe (sin esperar Enter).
        # Conectamos a self._buscar_producto para filtrar en vivo.
        self.txt_buscar_producto.textChanged.connect(self._buscar_producto)
        barra.addWidget(self.txt_buscar_producto, 1)  # El 1 = ocupa todo el espacio disponible.

        # Boton: Refrescar (recarga la tabla desde la BD).
        btn_refrescar = QPushButton("Refrescar")
        btn_refrescar.clicked.connect(self._cargar_productos)
        barra.addWidget(btn_refrescar)

        # Boton: Agregar producto (abre dialogo en modo crear).
        btn_agregar = QPushButton("Agregar")
        btn_agregar.clicked.connect(self._agregar_producto)
        barra.addWidget(btn_agregar)

        # Boton: Editar producto (abre dialogo en modo editar).
        btn_editar = QPushButton("Editar")
        btn_editar.clicked.connect(self._editar_producto)
        barra.addWidget(btn_editar)

        # Boton: Eliminar producto (pide confirmacion y elimina).
        btn_eliminar = QPushButton("Eliminar")
        btn_eliminar.clicked.connect(self._eliminar_producto)
        barra.addWidget(btn_eliminar)

        # Agregar la barra de herramientas al layout principal.
        layout.addLayout(barra)
        layout.addSpacing(10)

        # ----------------------------------------------------------
        # TABLA DE PRODUCTOS (QTableWidget)
        # ----------------------------------------------------------
        # QTableWidget: tabla con filas y columnas.
        # Cada fila = un producto, cada columna = un atributo.
        self.tabla_productos = QTableWidget()
        # Configurar las columnas: (nombre_columna, ancho en pixeles)
        columnas = [
            ("ID", 50),
            ("Nombre", 200),
            ("Categoria", 120),
            ("Precio Bs", 100),
            ("Precio USD", 100),
            ("Stock", 70),
            ("Stock Min", 70),
            ("Unidad", 80),
        ]
        self.tabla_productos.setColumnCount(len(columnas))
        self.tabla_productos.setHorizontalHeaderLabels([c[0] for c in columnas])

        # Ajustar el ancho de cada columna.
        for i, (_, ancho) in enumerate(columnas):
            self.tabla_productos.setColumnWidth(i, ancho)

        # Comportamiento de la tabla:
        # - SelectionBehavior.SelectRows: selecciona la fila completa al hacer clic.
        # - setEditTriggers.NoEditTriggers: NO se puede editar directamente en la celda.
        # - setSelectionMode.SingleSelection: solo se puede seleccionar UNA fila a la vez.
        self.tabla_productos.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_productos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla_productos.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        # Header (encabezados) se estira para llenar el espacio horizontal.
        self.tabla_productos.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]

        # cellDoubleClicked: cuando el usuario hace doble clic en una celda,
        # abrimos el dialogo de edicion (es mas rapido que buscar el boton).
        self.tabla_productos.cellDoubleClicked.connect(self._editar_producto)

        # Agregar la tabla al layout. El factor 1 hace que ocupe todo el espacio
        # vertical disponible, empujando el titulo hacia arriba.
        layout.addWidget(self.tabla_productos, 1)

        # Guardar la pagina en el QStackedWidget (indice 1 = Productos).
        self.paginas.addWidget(pagina)

        # ----------------------------------------------------------
        # CARGAR LOS DATOS INICIALES
        # ----------------------------------------------------------
        self._cargar_productos()

    # ------------------------------------------------------------------
    # _cargar_productos(): llena la tabla con todos los productos
    # ------------------------------------------------------------------
    # Se llama al: abrir la pagina, hacer clic en Refrescar,
    #   o despues de agregar/editar/eliminar un producto.
    # ------------------------------------------------------------------
    def _cargar_productos(self) -> None:
        """Carga todos los productos desde la BD a la tabla."""
        # Pedir la lista al controlador (el controlador habla con la BD).
        productos = self.controlador_productos.listar_todos()

        # Configurar el numero de filas de la tabla.
        self.tabla_productos.setRowCount(len(productos))

        # Recorrer cada producto y crear una fila en la tabla.
        for fila, producto in enumerate(productos):
            # QTableWidgetItem: representa una celda de la tabla.
            # El texto se convierte automaticamente a string con str().

            # Columna 0: ID del producto.
            self.tabla_productos.setItem(fila, 0, QTableWidgetItem(str(producto.idproducto)))

            # Columna 1: Nombre.
            item_nombre = QTableWidgetItem(producto.nombre_producto)
            self.tabla_productos.setItem(fila, 1, item_nombre)

            # Columna 2: Categoria (o "-" si es None).
            categoria = producto.categoria if producto.categoria else "-"
            self.tabla_productos.setItem(fila, 2, QTableWidgetItem(categoria))

            # Columna 3: Precio venta en Bs (con 2 decimales).
            self.tabla_productos.setItem(
                fila, 3, QTableWidgetItem(f"Bs. {producto.precio_venta_bs:.2f}")
            )

            # Columna 4: Precio venta en USD.
            self.tabla_productos.setItem(
                fila, 4, QTableWidgetItem(f"$ {producto.precio_venta_usd:.2f}")
            )

            # Columna 5: Stock actual.
            # Si el stock es 0 o bajo, lo coloreamos para alertar visualmente.
            item_stock = QTableWidgetItem(str(producto.stock_actual))
            if producto.stock_actual == 0:
                # Rojo: sin stock.
                item_stock.setForeground(Qt.GlobalColor.red)
            elif producto.stock_actual <= producto.stock_minimo:
                # Naranja: stock bajo.
                item_stock.setForeground(Qt.GlobalColor.darkYellow)
            self.tabla_productos.setItem(fila, 5, item_stock)

            # Columna 6: Stock minimo.
            self.tabla_productos.setItem(fila, 6, QTableWidgetItem(str(producto.stock_minimo)))

            # Columna 7: Unidad de medida.
            self.tabla_productos.setItem(fila, 7, QTableWidgetItem(producto.unidad))

    # ------------------------------------------------------------------
    # _buscar_producto(): filtra productos mientras el usuario escribe
    # ------------------------------------------------------------------
    # textChanged se dispara en CADA TECLA que presiona el usuario.
    # Si el texto esta vacio, recarga todos los productos.
    # ------------------------------------------------------------------
    def _buscar_producto(self, texto: str) -> None:
        """Filtra la tabla de productos mientras el usuario escribe."""
        texto = texto.strip()
        if not texto:
            # Si el buscador esta vacio, mostrar todos.
            self._cargar_productos()
            return

        # Buscar productos que coincidan con el texto.
        productos = self.controlador_productos.buscar(texto)

        # Actualizar la tabla con los resultados.
        self.tabla_productos.setRowCount(len(productos))
        for fila, producto in enumerate(productos):
            self.tabla_productos.setItem(fila, 0, QTableWidgetItem(str(producto.idproducto)))
            self.tabla_productos.setItem(fila, 1, QTableWidgetItem(producto.nombre_producto))
            categoria = producto.categoria if producto.categoria else "-"
            self.tabla_productos.setItem(fila, 2, QTableWidgetItem(categoria))
            self.tabla_productos.setItem(
                fila, 3, QTableWidgetItem(f"Bs. {producto.precio_venta_bs:.2f}")
            )
            self.tabla_productos.setItem(
                fila, 4, QTableWidgetItem(f"$ {producto.precio_venta_usd:.2f}")
            )
            self.tabla_productos.setItem(fila, 5, QTableWidgetItem(str(producto.stock_actual)))
            self.tabla_productos.setItem(fila, 6, QTableWidgetItem(str(producto.stock_minimo)))
            self.tabla_productos.setItem(fila, 7, QTableWidgetItem(producto.unidad))

    # ------------------------------------------------------------------
    # _obtener_fila_seleccionada(): helper para obtener el ID de la fila activa
    # ------------------------------------------------------------------
    # currentRow(): devuelve el indice de la fila seleccionada (-1 si no hay).
    # Luego extraemos el ID de la columna 0.
    # Retorna (fila, id) o (-1, None) si no hay seleccion.
    # ------------------------------------------------------------------
    def _obtener_fila_seleccionada(self) -> tuple[int, int | None]:
        """Devuelve (fila, idproducto) de la fila seleccionada."""
        fila = self.tabla_productos.currentRow()
        if fila < 0:
            return -1, None
        # El ID esta en la columna 0 como texto, lo convertimos a int.
        item_id = self.tabla_productos.item(fila, 0)
        if item_id is None:
            return -1, None
        return fila, int(item_id.text())

    # ------------------------------------------------------------------
    # _agregar_producto(): abre dialogo para crear un nuevo producto
    # ------------------------------------------------------------------
    def _agregar_producto(self) -> None:
        """Abre el dialogo para agregar un producto."""
        dialogo = ProductoDialog(self, controlador_productos=self.controlador_productos)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            # Si el usuario hizo clic en "Guardar", recargar la tabla.
            self._cargar_productos()

    # ------------------------------------------------------------------
    # _editar_producto(): abre dialogo para editar el producto seleccionado
    # ------------------------------------------------------------------
    # Se llama desde el boton Editar o al hacer doble clic en una fila.
    # ------------------------------------------------------------------
    def _editar_producto(self) -> None:
        """Abre el dialogo para editar el producto seleccionado."""
        fila, idproducto = self._obtener_fila_seleccionada()
        if idproducto is None:
            QMessageBox.information(self, "Editar", "Selecciona un producto para editar.")
            return

        # Obtener el producto completo desde la BD.
        producto = self.controlador_productos.obtener_por_id(idproducto)
        if producto is None:
            QMessageBox.warning(self, "Error", "El producto ya no existe en la BD.")
            return

        # Abrir el dialogo en modo editar (pasandole el producto existente y el controlador).
        dialogo = ProductoDialog(
            self,
            producto=producto,
            controlador_productos=self.controlador_productos,
        )
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self._cargar_productos()

    # ------------------------------------------------------------------
    # _eliminar_producto(): elimina el producto seleccionado (con confirmacion)
    # ------------------------------------------------------------------
    def _eliminar_producto(self) -> None:
        """Elimina el producto seleccionado previa confirmacion."""
        fila, idproducto = self._obtener_fila_seleccionada()
        if idproducto is None:
            QMessageBox.information(self, "Eliminar", "Selecciona un producto para eliminar.")
            return

        # Obtener el nombre del producto para mostrarlo en la confirmacion.
        producto = self.controlador_productos.obtener_por_id(idproducto)
        if producto is None:
            QMessageBox.warning(self, "Error", "El producto ya no existe.")
            return

        # Preguntar confirmacion antes de eliminar.
        # QMessageBox.question: muestra Si/No y devuelve la opcion elegida.
        respuesta = QMessageBox.question(
            self,
            "Confirmar eliminacion",
            f"Seguro que deseas eliminar '{producto.nombre_producto}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if respuesta == QMessageBox.StandardButton.Yes:
            self.controlador_productos.eliminar(idproducto)
            self._cargar_productos()

    # ------------------------------------------------------------------
    # PAGINA: Ventas (registro e historial de ventas)
    # ------------------------------------------------------------------
    # Esta pagina tiene:
    #   1. Titulo y barra de herramientas (Nueva Venta, Anular, Refrescar)
    #   2. Filtro de fechas (Desde / Hasta) para el historial
    #   3. Tabla con las ventas del periodo seleccionado
    #   4. Doble clic → muestra detalle de la venta (productos vendidos)
    #
    # Flujo de "Nueva Venta":
    #   Clic "Nueva Venta" → VentaDialog (elige productos, cantidades, pago)
    #   → VentaController.crear() → descuenta inventario → recarga tabla
    #
    # Flujo de "Anular":
    #   Seleccionar venta → clic "Anular" → confirmar
    #   → VentaController.anular() → devuelve stock → recarga tabla
    # ------------------------------------------------------------------
    def _crear_pagina_ventas(self) -> None:  # noqa: PLR0915
        """Crea la pagina de gestion de ventas con tabla y botones."""
        pagina = QWidget()
        # Layout vertical: titulo → barra → filtro fechas → tabla
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(40, 40, 40, 40)

        # ----------------------------------------------------------
        # TITULO DE LA PAGINA
        # ----------------------------------------------------------
        lbl_titulo = QLabel("Ventas")
        fuente = QFont()
        fuente.setPointSize(24)
        fuente.setBold(True)
        lbl_titulo.setFont(fuente)
        layout.addWidget(lbl_titulo)

        # ----------------------------------------------------------
        # BARRA DE HERRAMIENTAS (botones de accion)
        # ----------------------------------------------------------
        barra = QHBoxLayout()

        # Boton: Nueva Venta (abre dialogo para crear venta).
        btn_nueva = QPushButton("+ Nueva Venta")
        btn_nueva.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px;"
        )
        btn_nueva.clicked.connect(self._nueva_venta)
        barra.addWidget(btn_nueva)

        # Boton: Anular venta (cambia estado a ANULADA y devuelve stock).
        btn_anular = QPushButton("Anular Venta")
        btn_anular.setStyleSheet("background-color: #f44336; color: white; padding: 8px 16px;")
        btn_anular.clicked.connect(self._anular_venta)
        barra.addWidget(btn_anular)

        # Boton: Refrescar (recarga la tabla desde la BD).
        btn_refrescar = QPushButton("Refrescar")
        btn_refrescar.clicked.connect(self._cargar_ventas)
        barra.addWidget(btn_refrescar)

        # addStretch(): empuja los botones a la izquierda.
        barra.addStretch()

        layout.addLayout(barra)
        layout.addSpacing(10)

        # ----------------------------------------------------------
        # FILTRO DE FECHAS (Desde / Hasta)
        # ----------------------------------------------------------
        # QHBoxLayout horizontal para los selectores de fecha.
        filtro_fechas = QHBoxLayout()

        # QLabel: texto "Desde:" antes del selector.
        filtro_fechas.addWidget(QLabel("Desde:"))

        # QDateEdit: selector de fecha con calendario emergente.
        # calendarPopup=True: muestra un calendario al hacer clic.
        self.fecha_desde = QDateEdit()
        self.fecha_desde.setCalendarPopup(True)
        # setDate(): fecha actual.
        self.fecha_desde.setDate(self.fecha_desde.date().addDays(-30))
        # Mostrar la fecha hace 30 dias por defecto.
        filtro_fechas.addWidget(self.fecha_desde)

        filtro_fechas.addWidget(QLabel("Hasta:"))

        self.fecha_hasta = QDateEdit()
        self.fecha_hasta.setCalendarPopup(True)
        self.fecha_hasta.setDate(self.fecha_hasta.date())
        filtro_fechas.addWidget(self.fecha_hasta)

        # Boton "Filtrar": aplica el rango de fechas.
        btn_filtrar = QPushButton("Filtrar")
        btn_filtrar.clicked.connect(self._cargar_ventas)
        filtro_fechas.addWidget(btn_filtrar)

        # addStretch(): empuja el filtro a la izquierda.
        filtro_fechas.addStretch()

        layout.addLayout(filtro_fechas)
        layout.addSpacing(10)

        # ----------------------------------------------------------
        # TABLA DE VENTAS
        # ----------------------------------------------------------
        self.tabla_ventas = QTableWidget()
        # Columnas de la tabla de ventas.
        columnas = [
            ("ID", 50),
            ("Factura", 140),
            ("Fecha", 150),
            ("Total Bs", 100),
            ("Total USD", 100),
            ("Estado", 100),
        ]
        self.tabla_ventas.setColumnCount(len(columnas))
        self.tabla_ventas.setHorizontalHeaderLabels([c[0] for c in columnas])

        for i, (_, ancho) in enumerate(columnas):
            self.tabla_ventas.setColumnWidth(i, ancho)

        # Comportamiento: seleccionar fila completa, solo lectura.
        self.tabla_ventas.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_ventas.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla_ventas.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla_ventas.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]

        # Doble clic: muestra el detalle de la venta (productos vendidos).
        self.tabla_ventas.cellDoubleClicked.connect(self._detalle_venta)

        # Agregar la tabla al layout. El factor 1 = ocupa todo el espacio.
        layout.addWidget(self.tabla_ventas, 1)

        self.paginas.addWidget(pagina)  # Indice 2

        # Cargar los datos iniciales.
        self._cargar_ventas()

    # ------------------------------------------------------------------
    # _cargar_ventas(): llena la tabla con ventas del rango de fechas
    # ------------------------------------------------------------------
    def _cargar_ventas(self) -> None:
        """Carga las ventas del rango de fechas seleccionado."""
        # Convertir QDate a datetime de Python.
        # QDate.toPyDate(): convierte QDate a date de Python.
        desde = datetime.combine(self.fecha_desde.date().toPyDate(), datetime.min.time())
        hasta = datetime.combine(self.fecha_hasta.date().toPyDate(), datetime.max.time())

        # Pedir las ventas al controlador.
        ventas = self.controlador_ventas.historial_por_fecha(desde, hasta)

        # Configurar el numero de filas.
        self.tabla_ventas.setRowCount(len(ventas))

        # Recorrer cada venta y crear una fila.
        for fila, venta in enumerate(ventas):
            # Columna 0: ID.
            self.tabla_ventas.setItem(fila, 0, QTableWidgetItem(str(venta.idventa)))

            # Columna 1: Numero de factura.
            factura = venta.numero_factura or "-"
            self.tabla_ventas.setItem(fila, 1, QTableWidgetItem(factura))

            # Columna 2: Fecha de la venta (formateada).
            fv = venta.fecha_venta
            fecha_str = fv.strftime("%d/%m/%Y %H:%M") if fv else "-"
            self.tabla_ventas.setItem(fila, 2, QTableWidgetItem(fecha_str))

            # Columna 3: Total en Bs.
            self.tabla_ventas.setItem(fila, 3, QTableWidgetItem(f"Bs. {venta.total_bs:.2f}"))

            # Columna 4: Total en USD.
            self.tabla_ventas.setItem(fila, 4, QTableWidgetItem(f"$ {venta.total_usd:.2f}"))

            # Columna 5: Estado (COMPLETADA o ANULADA).
            # Coloreamos el estado para que sea facil distinguir.
            item_estado = QTableWidgetItem(venta.estado)
            if venta.estado == "ANULADA":
                item_estado.setForeground(Qt.GlobalColor.red)
            else:
                item_estado.setForeground(Qt.GlobalColor.darkGreen)
            self.tabla_ventas.setItem(fila, 5, item_estado)

    # ------------------------------------------------------------------
    # _nueva_venta(): abre el dialogo para crear una venta
    # ------------------------------------------------------------------
    def _nueva_venta(self) -> None:
        """Abre el dialogo para registrar una nueva venta."""
        dialogo = VentaDialog(
            self,
            controlador_productos=self.controlador_productos,
            controlador_ventas=self.controlador_ventas,
            controlador_tasas=self.controlador_tasas,
        )
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            # Si la venta se creo correctamente, recargar la tabla.
            self._cargar_ventas()

    # ------------------------------------------------------------------
    # _anular_venta(): anula la venta seleccionada
    # ------------------------------------------------------------------
    def _anular_venta(self) -> None:
        """Anula la venta seleccionada y devuelve el stock."""
        # Obtener la fila seleccionada.
        fila = self.tabla_ventas.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Anular", "Selecciona una venta para anular.")
            return

        # Obtener el ID de la venta (columna 0).
        item_id = self.tabla_ventas.item(fila, 0)
        if item_id is None:
            return
        idventa = int(item_id.text())

        # Obtener la venta para mostrar info en la confirmacion.
        venta = self.controlador_ventas.obtener_por_id(idventa)
        if venta is None:
            QMessageBox.warning(self, "Error", "La venta ya no existe.")
            return

        # No se puede anular una venta ya anulada.
        if venta.estado == "ANULADA":
            QMessageBox.information(self, "Anular", "Esta venta ya esta anulada.")
            return

        # Confirmar antes de anular.
        respuesta = QMessageBox.question(
            self,
            "Confirmar anulacion",
            f"Seguro que deseas anular la factura {venta.numero_factura}?\n"
            "El stock de los productos se devolvera automaticamente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if respuesta == QMessageBox.StandardButton.Yes:
            try:
                self.controlador_ventas.anular(idventa)
                QMessageBox.information(
                    self, "Exito", f"Venta {venta.numero_factura} anulada correctamente."
                )
                self._cargar_ventas()
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    # ------------------------------------------------------------------
    # _detalle_venta(): muestra los productos de una venta
    # ------------------------------------------------------------------
    # Se ejecuta al hacer doble clic en una fila de la tabla.
    # Muestra un QMessageBox con la lista de productos vendidos.
    # ------------------------------------------------------------------
    def _detalle_venta(self) -> None:
        """Muestra el detalle de productos de la venta seleccionada."""
        fila = self.tabla_ventas.currentRow()
        if fila < 0:
            return

        item_id = self.tabla_ventas.item(fila, 0)
        if item_id is None:
            return
        idventa = int(item_id.text())
        item_factura = self.tabla_ventas.item(fila, 1)
        factura = item_factura.text() if item_factura else "-"

        # Obtener los detalles (productos) de la venta.
        detalles = self.controlador_ventas.obtener_detalles(idventa)
        if not detalles:
            QMessageBox.information(self, "Detalle", "Esta venta no tiene productos registrados.")
            return

        # Construir el mensaje con todos los productos.
        # Usamos el controlador de productos para obtener el nombre de cada uno.
        lineas = [f"Factura: {factura}\n", "=" * 30]
        for det in detalles:
            producto = self.controlador_productos.obtener_por_id(det.producto_id)
            nombre = producto.nombre_producto if producto else f"ID {det.producto_id}"
            lineas.append(f"{det.cantidad}x {nombre} = Bs. {det.subtotal_bs:.2f}")
        lineas.append("=" * 30)

        # Mostrar en un cuadro de dialogo.
        QMessageBox.information(
            self,
            f"Detalle de Venta - {factura}",
            "\n".join(lineas),
        )

    # ------------------------------------------------------------------
    # PAGINA: Inventario (control de stock)
    # ------------------------------------------------------------------
    # Esta pagina permite VER todos los movimientos de inventario
    # y REGISTRAR entradas, salidas o ajustes de stock.
    #
    # Contenido:
    #   1. Barra superior: selector de producto + botones de accion.
    #   2. Tabla de movimientos del producto seleccionado.
    #
    # Flujo:
    #   Al hacer clic en "Entrada", "Salida" o "Ajuste" se abre un
    #   QDialog donde el usuario ingresa cantidad, motivo y observaciones.
    # ------------------------------------------------------------------
    def _crear_pagina_inventario(self) -> None:
        """Crea la pagina de control de inventario con movimientos y registro."""
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # ----------------------------------------------------------
        # TITULO DE LA PAGINA
        # ----------------------------------------------------------
        lbl_titulo = QLabel("Inventario")
        fuente = QFont()
        fuente.setPointSize(24)
        fuente.setBold(True)
        lbl_titulo.setFont(fuente)
        layout.addWidget(lbl_titulo)

        # ----------------------------------------------------------
        # BARRA DE HERRAMIENTAS SUPERIOR
        # ----------------------------------------------------------
        # Layout horizontal con: selector de producto + botones.
        barra = QHBoxLayout()
        barra.setSpacing(10)

        # QComboBox: lista desplegable para seleccionar un producto.
        # El primer item es "Todos los productos" (None = ver todos).
        self.cmb_producto_inventario = QComboBox()
        self.cmb_producto_inventario.setMinimumWidth(250)
        self.cmb_producto_inventario.setPlaceholderText("Seleccionar producto...")
        # Al cambiar la seleccion, refrescar la tabla de movimientos.
        self.cmb_producto_inventario.currentIndexChanged.connect(self._refrescar_tabla_movimientos)
        barra.addWidget(QLabel("Producto:"))
        barra.addWidget(self.cmb_producto_inventario)
        barra.addSpacing(20)

        # Botones para registrar movimientos.
        # Cada boton tiene un color distintivo para indicar su accion:
        #   - Entrada: verde (agrega stock).
        #   - Salida: rojo (reduce stock).
        #   - Ajuste: naranja (cambio manual).
        btn_entrada = QPushButton("➕ Entrada")
        btn_entrada.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        btn_entrada.clicked.connect(lambda: self._mostrar_dialogo_movimiento("ENTRADA"))
        barra.addWidget(btn_entrada)

        btn_salida = QPushButton("➖ Salida")
        btn_salida.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #da190b; }"
        )
        btn_salida.clicked.connect(lambda: self._mostrar_dialogo_movimiento("SALIDA"))
        barra.addWidget(btn_salida)

        btn_ajuste = QPushButton("🔄 Ajuste")
        btn_ajuste.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #e68a00; }"
        )
        btn_ajuste.clicked.connect(lambda: self._mostrar_dialogo_movimiento("AJUSTE"))
        barra.addWidget(btn_ajuste)

        # Boton refrescar.
        btn_refrescar = QPushButton("🔄 Refrescar")
        btn_refrescar.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0b7dda; }"
        )
        btn_refrescar.clicked.connect(self._refrescar_tabla_movimientos)
        barra.addWidget(btn_refrescar)

        barra.addStretch()
        layout.addLayout(barra)

        # ----------------------------------------------------------
        # TABLA DE MOVIMIENTOS
        # ----------------------------------------------------------
        # Muestra todos los movimientos (entradas, salidas, ajustes).
        # Filtrar por producto seleccionado en el QComboBox.
        self.tabla_movimientos = QTableWidget()
        self.tabla_movimientos.setColumnCount(7)
        self.tabla_movimientos.setHorizontalHeaderLabels(
            ["ID", "Fecha", "Producto", "Tipo", "Cantidad", "Stock Anterior", "Stock Nuevo"]
        )
        # Estirar la ultima columna para llenar el espacio.
        self.tabla_movimientos.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        # No permitir editar las celdas.
        self.tabla_movimientos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Seleccionar filas completas.
        self.tabla_movimientos.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.tabla_movimientos)

        # Agregar la pagina al QStackedWidget (indice 3).
        self.paginas.addWidget(pagina)

        # ----------------------------------------------------------
        # Cargar datos iniciales
        # ----------------------------------------------------------
        self._cargar_productos_en_combo(tipo="inventario")
        self._refrescar_tabla_movimientos()

    # ------------------------------------------------------------------
    # _cargar_productos_en_combo(): llena un QComboBox con productos
    # ------------------------------------------------------------------
    # Parametro "tipo": distingue si se llama desde inventario o ventas.
    #   - "inventario": incluye "Todos los productos" al inicio.
    #   - "ventas": solo productos con stock > 0 (para vender).
    #
    # Esto evita duplicar codigo entre metodos.
    # ------------------------------------------------------------------
    def _cargar_productos_en_combo(self, tipo: str = "ventas") -> None:
        """Llena el QComboBox con los productos disponibles."""
        productos = self.controlador_productos.listar_todos()

        if tipo == "inventario":
            # En la pagina de inventario, el primer item es "Todos".
            self.cmb_producto_inventario.clear()
            self.cmb_producto_inventario.addItem("Todos los productos", None)

        for prod in productos:
            # Incluir el stock en el texto para informacion visual.
            if tipo == "inventario":
                texto = f"{prod.nombre_producto} (Stock: {prod.stock_actual})"
                self.cmb_producto_inventario.addItem(texto, prod.idproducto)

    # ------------------------------------------------------------------
    # _refrescar_tabla_movimientos(): actualiza la tabla de movimientos
    # ------------------------------------------------------------------
    # Se ejecuta cuando:
    #   - Se cambia el producto seleccionado en el QComboBox.
    #   - Se registra un nuevo movimiento.
    #   - Se hace clic en "Refrescar".
    # ------------------------------------------------------------------
    def _refrescar_tabla_movimientos(self) -> None:
        """Refresca la tabla de movimientos segun el producto seleccionado."""
        # Obtener el ID del producto seleccionado (None = todos).
        producto_id = self.cmb_producto_inventario.currentData()

        # Obtener movimientos filtrados por producto (o todos).
        if producto_id is None:
            movimientos = self.controlador_inventario.movimientos_recientes(limite=500)
        else:
            movimientos = self.controlador_inventario.historial_por_producto(producto_id)

        # Llenar la tabla.
        self.tabla_movimientos.setRowCount(len(movimientos))
        for fila, mov in enumerate(movimientos):
            # Columna 0: ID del movimiento.
            self.tabla_movimientos.setItem(fila, 0, QTableWidgetItem(str(mov.id or "")))
            # Columna 1: Fecha del movimiento.
            fecha_str = (
                mov.fecha_movimiento.strftime("%d/%m/%Y %H:%M") if mov.fecha_movimiento else ""
            )
            self.tabla_movimientos.setItem(fila, 1, QTableWidgetItem(fecha_str))
            # Columna 2: Nombre del producto.
            nombre = mov.producto.nombre_producto if mov.producto else "—"
            self.tabla_movimientos.setItem(fila, 2, QTableWidgetItem(nombre))
            # Columna 3: Tipo de movimiento.
            item_tipo = QTableWidgetItem(mov.tipo)
            # Colorear segun el tipo.
            if mov.tipo == "ENTRADA":
                item_tipo.setBackground(Qt.GlobalColor.green)
                item_tipo.setForeground(Qt.GlobalColor.white)
            elif mov.tipo == "SALIDA":
                item_tipo.setBackground(Qt.GlobalColor.red)
                item_tipo.setForeground(Qt.GlobalColor.white)
            else:
                item_tipo.setBackground(Qt.GlobalColor.darkYellow)
                item_tipo.setForeground(Qt.GlobalColor.white)
            self.tabla_movimientos.setItem(fila, 3, item_tipo)
            # Columna 4: Cantidad.
            self.tabla_movimientos.setItem(fila, 4, QTableWidgetItem(str(mov.cantidad)))
            # Columna 5: Stock anterior.
            self.tabla_movimientos.setItem(fila, 5, QTableWidgetItem(str(mov.stock_anterior)))
            # Columna 6: Stock nuevo.
            self.tabla_movimientos.setItem(fila, 6, QTableWidgetItem(str(mov.stock_nuevo)))

        # Ajustar el ancho de las columnas al contenido.
        self.tabla_movimientos.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # _crear_formulario_movimiento(): construye el formulario
    #     para registrar un movimiento de inventario
    # ------------------------------------------------------------------
    # Extraemos la creacion del formulario a un metodo separado para
    # reducir la cantidad de declaraciones en _mostrar_dialogo_movimiento
    # (cumplir con PLR0915, maximo 50 declaraciones por metodo).
    #
    # Retorna una tupla con los widgets creados:
    #   (cmb_producto, spin_cantidad, cmb_motivo, txt_observaciones)
    # ------------------------------------------------------------------
    def _crear_formulario_movimiento(
        self,
        layout: QVBoxLayout,
        tipo: str,
    ) -> tuple[QComboBox, QSpinBox, QComboBox, QLineEdit]:
        """Crea los campos del formulario de movimiento de inventario."""
        form = QFormLayout()

        cmb_producto = QComboBox()
        cmb_producto.setMinimumWidth(250)
        productos = self.controlador_productos.listar_todos()
        for prod in productos:
            texto = f"{prod.nombre_producto} (Stock: {prod.stock_actual})"
            cmb_producto.addItem(texto, prod.idproducto)
        form.addRow("Producto:", cmb_producto)

        spin_cantidad = QSpinBox()
        spin_cantidad.setRange(1, 999999)
        spin_cantidad.setValue(1)
        form.addRow("Cantidad:", spin_cantidad)

        cmb_motivo = QComboBox()
        if tipo == "ENTRADA":
            cmb_motivo.addItems(["COMPRA", "DEVOLUCION", "TRASLADO", "OTRO"])
        elif tipo == "SALIDA":
            cmb_motivo.addItems(["VENTA", "PERDIDA", "VENCIMIENTO", "TRASLADO", "OTRO"])
        else:
            cmb_motivo.addItems(["INVENTARIO", "ROBO", "EXTRA", "OTRO"])
        form.addRow("Motivo:", cmb_motivo)

        txt_observaciones = QLineEdit()
        txt_observaciones.setPlaceholderText("Observaciones (opcional)")
        form.addRow("Observaciones:", txt_observaciones)

        layout.addLayout(form)

        return cmb_producto, spin_cantidad, cmb_motivo, txt_observaciones

    # ------------------------------------------------------------------
    # _mostrar_dialogo_movimiento(): abre un formulario para registrar
    #     un movimiento de inventario
    # ------------------------------------------------------------------
    # Dependiendo del tipo (ENTRADA/SALIDA/AJUSTE), el dialogo cambia:
    #   - ENTRADA: cantidad positiva + motivo (COMPRA, DEVOLUCION, etc.).
    #   - SALIDA: cantidad negativa + motivo (VENTA, PERDIDA, etc.).
    #   - AJUSTE: cantidad (positiva o negativa) + motivo (INVENTARIO, etc.).
    #
    # En lugar de crear 3 dialogos diferentes, creamos uno solo y
    # cambiamos el comportamiento segun el "tipo".
    # ------------------------------------------------------------------
    def _mostrar_dialogo_movimiento(self, tipo: str) -> None:
        """Abre un dialogo para registrar una entrada, salida o ajuste."""
        dialogo = QDialog(self)
        dialogo.setWindowTitle(f"Registrar {tipo}")
        dialogo.setFixedSize(400, 300)

        layout = QVBoxLayout(dialogo)
        layout.setContentsMargins(20, 20, 20, 20)

        # Crear los widgets del formulario usando un metodo auxiliar.
        cmb_producto, spin_cantidad, cmb_motivo, txt_observaciones = (
            self._crear_formulario_movimiento(layout, tipo)
        )

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.accepted.connect(dialogo.accept)
        botones.rejected.connect(dialogo.reject)
        layout.addWidget(botones)

        # Mostrar el dialogo y esperar la respuesta.
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        # Obtener los valores ingresados.
        producto_id = cmb_producto.currentData()
        cantidad = spin_cantidad.value()
        motivo = cmb_motivo.currentText()
        observaciones = txt_observaciones.text().strip()

        # Validar que se haya seleccionado un producto.
        if producto_id is None:
            QMessageBox.warning(dialogo, "Error", "Debe seleccionar un producto.")
            return

        # ----------------------------------------------------------
        # Registrar el movimiento segun el tipo
        # ----------------------------------------------------------
        try:
            if tipo == "ENTRADA":
                self.controlador_inventario.registrar_entrada(
                    producto_id=producto_id,
                    cantidad=cantidad,
                    motivo=motivo,
                    observaciones=observaciones or None,
                )
            elif tipo == "SALIDA":
                self.controlador_inventario.registrar_salida(
                    producto_id=producto_id,
                    cantidad=cantidad,
                    motivo=motivo,
                    observaciones=observaciones or None,
                )
            else:  # AJUSTE
                # PARA AJUSTE: obtener el producto para calcular stock_fisico.
                # stock_fisico = stock_actual + cantidad (delta).
                producto_actual = self.controlador_productos.obtener_por_id(producto_id)
                stock_fisico = (
                    (producto_actual.stock_actual + cantidad) if producto_actual else cantidad
                )
                self.controlador_inventario.registrar_ajuste(
                    producto_id=producto_id,
                    stock_fisico=stock_fisico,
                    motivo=motivo,
                    observaciones=observaciones or None,
                )

            mensaje = f"{tipo} registrada correctamente."
            QMessageBox.information(dialogo, "Exito", mensaje)

            # Refrescar la tabla de movimientos.
            self._refrescar_tabla_movimientos()

            # Tambien recargar el combo de productos (el stock cambio).
            self._cargar_productos_en_combo(tipo="inventario")

        except ValueError as e:
            QMessageBox.warning(dialogo, "Error", str(e))

    # ------------------------------------------------------------------
    # PAGINA: Reportes (reporte diario y exportacion)
    # ------------------------------------------------------------------
    # Esta pagina permite:
    #   1. Ver el historial de reportes diarios generados.
    #   2. Generar ("Cerrar Dia") un nuevo reporte para hoy.
    #   3. Exportar un reporte a Excel.
    #   4. Regenerar un reporte existente (si se anularon ventas).
    #
    # QUE ES UN "CIERRE DE DIA"?
    #   - Consolida TODAS las ventas COMPLETADA del dia en un ReporteDiario.
    #   - Calcula totales VES/USD y por metodo de pago.
    #   - Cuenta productos stock bajo/sin stock.
    #   - Se guarda en la BD para referencia futura.
    #   - No afecta las ventas ni el inventario (es solo un resumen).
    # ------------------------------------------------------------------
    def _crear_pagina_reportes(self) -> None:
        """Crea la pagina de reportes con cierre diario y exportacion."""
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # ----------------------------------------------------------
        # TITULO DE LA PAGINA
        # ----------------------------------------------------------
        lbl_titulo = QLabel("Reportes")
        fuente = QFont()
        fuente.setPointSize(24)
        fuente.setBold(True)
        lbl_titulo.setFont(fuente)
        layout.addWidget(lbl_titulo)

        # ----------------------------------------------------------
        # BARRA DE HERRAMIENTAS
        # ----------------------------------------------------------
        barra = QHBoxLayout()
        barra.setSpacing(10)

        # Filtro de fechas (desde / hasta).
        barra.addWidget(QLabel("Desde:"))
        self.fecha_desde_reporte = QDateEdit()
        self.fecha_desde_reporte.setCalendarPopup(True)
        self.fecha_desde_reporte.setDate(QDate.currentDate().addDays(-30))
        self.fecha_desde_reporte.dateChanged.connect(self._refrescar_tabla_reportes)
        barra.addWidget(self.fecha_desde_reporte)

        barra.addWidget(QLabel("Hasta:"))
        self.fecha_hasta_reporte = QDateEdit()
        self.fecha_hasta_reporte.setCalendarPopup(True)
        self.fecha_hasta_reporte.setDate(QDate.currentDate())
        self.fecha_hasta_reporte.dateChanged.connect(self._refrescar_tabla_reportes)
        barra.addWidget(self.fecha_hasta_reporte)

        barra.addSpacing(20)

        # Boton: Cerrar Dia (genera reporte para hoy).
        btn_cerrar_dia = QPushButton("🔒 Cerrar Día")
        btn_cerrar_dia.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        btn_cerrar_dia.clicked.connect(self._cerrar_dia)
        barra.addWidget(btn_cerrar_dia)

        # Boton: Exportar Excel.
        btn_exportar = QPushButton("📊 Exportar Excel")
        btn_exportar.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0b7dda; }"
        )
        btn_exportar.clicked.connect(self._exportar_reporte_excel)
        barra.addWidget(btn_exportar)

        # Boton: Regenerar reporte seleccionado.
        btn_regenerar = QPushButton("🔄 Regenerar")
        btn_regenerar.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #e68a00; }"
        )
        btn_regenerar.clicked.connect(self._regenerar_reporte)
        barra.addWidget(btn_regenerar)

        barra.addStretch()
        layout.addLayout(barra)

        # ----------------------------------------------------------
        # TABLA DE REPORTES
        # ----------------------------------------------------------
        # Muestra todos los reportes diarios generados.
        self.tabla_reportes = QTableWidget()
        self.tabla_reportes.setColumnCount(8)
        self.tabla_reportes.setHorizontalHeaderLabels(
            [
                "ID",
                "Fecha",
                "Ventas Bs.",
                "Ventas USD",
                "Cant. Ventas",
                "Stock Bajo",
                "Sin Stock",
                "Generado",
            ]
        )
        self.tabla_reportes.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        self.tabla_reportes.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla_reportes.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.tabla_reportes)

        # Agregar la pagina al QStackedWidget (indice 4).
        self.paginas.addWidget(pagina)

        # Cargar datos iniciales.
        self._refrescar_tabla_reportes()

    # ------------------------------------------------------------------
    # _refrescar_tabla_reportes(): actualiza la tabla de reportes
    # ------------------------------------------------------------------
    def _refrescar_tabla_reportes(self) -> None:
        """Refresca la tabla de reportes segun el filtro de fechas."""
        # Obtener las fechas del filtro.
        desde_qdate = self.fecha_desde_reporte.date()
        hasta_qdate = self.fecha_hasta_reporte.date()

        # Convertir QDate a date de Python.
        desde = date(desde_qdate.year(), desde_qdate.month(), desde_qdate.day())
        hasta = date(hasta_qdate.year(), hasta_qdate.month(), hasta_qdate.day())

        # Obtener los reportes del rango.
        reportes = self.controlador_reportes.listar_por_rango(desde, hasta)

        # Llenar la tabla.
        self.tabla_reportes.setRowCount(len(reportes))
        for fila, rep in enumerate(reportes):
            self.tabla_reportes.setItem(fila, 0, QTableWidgetItem(str(rep.id or "")))
            self.tabla_reportes.setItem(fila, 1, QTableWidgetItem(rep.fecha.isoformat()))
            self.tabla_reportes.setItem(
                fila, 2, QTableWidgetItem(f"Bs. {rep.total_ventas_bs:,.2f}")
            )
            self.tabla_reportes.setItem(
                fila, 3, QTableWidgetItem(f"USD {rep.total_ventas_usd:,.2f}")
            )
            self.tabla_reportes.setItem(fila, 4, QTableWidgetItem(str(rep.cantidad_ventas)))
            self.tabla_reportes.setItem(fila, 5, QTableWidgetItem(str(rep.productos_stock_bajo)))
            self.tabla_reportes.setItem(fila, 6, QTableWidgetItem(str(rep.productos_sin_stock)))
            fecha_gen = (
                rep.fecha_generacion.strftime("%d/%m/%Y %H:%M") if rep.fecha_generacion else ""
            )
            self.tabla_reportes.setItem(fila, 7, QTableWidgetItem(fecha_gen))

        self.tabla_reportes.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # _cerrar_dia(): genera el reporte diario para la fecha de hoy
    # ------------------------------------------------------------------
    # Llama a ReporteService.generar_reporte() que consolida todas
    # las ventas del dia en un ReporteDiario.
    #
    # Si ya existe un reporte para hoy, el servicio lo reemplaza
    # (elimina el viejo y crea uno nuevo).
    # ------------------------------------------------------------------
    def _cerrar_dia(self) -> None:
        """Genera el reporte diario para hoy y refresca la tabla."""
        try:
            reporte = self.controlador_reportes.generar_reporte()
            QMessageBox.information(
                self,
                "Cierre Exitoso",
                f"Reporte del {reporte.fecha} generado correctamente.\n"
                f"Ventas: {reporte.cantidad_ventas} | "
                f"Total Bs.: {reporte.total_ventas_bs:,.2f}",
            )
            self._refrescar_tabla_reportes()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al generar reporte:\n{str(e)}")

    # ------------------------------------------------------------------
    # _regenerar_reporte(): regenera (reemplaza) el reporte seleccionado
    # ------------------------------------------------------------------
    # Util cuando se anula una venta DESPUES de haber cerrado el dia:
    #   - El reporte existente ya no refleja las ventas reales.
    #   - Al regenerar, se elimina el reporte viejo y se crea uno
    #     nuevo con los datos actualizados.
    # ------------------------------------------------------------------
    def _regenerar_reporte(self) -> None:
        """Regenera el reporte de la fecha seleccionada."""
        fila = self.tabla_reportes.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Seleccion", "Seleccione un reporte de la tabla.")
            return

        # Obtener la fecha del reporte seleccionado.
        item_fecha = self.tabla_reportes.item(fila, 1)
        if item_fecha is None:
            return
        fecha_texto = item_fecha.text()

        # Convertir el texto de fecha (YYYY-MM-DD) a date.
        try:
            partes = fecha_texto.split("-")
            fecha_reporte = date(int(partes[0]), int(partes[1]), int(partes[2]))
        except IndexError, ValueError:
            QMessageBox.warning(self, "Error", "Fecha de reporte invalida.")
            return

        # Confirmar con el usuario.
        respuesta = QMessageBox.question(
            self,
            "Regenerar Reporte",
            f"Va a regenerar el reporte del {fecha_reporte}.\n"
            "Esto reemplazara el reporte existente. Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            reporte = self.controlador_reportes.generar_reporte(fecha_reporte)
            QMessageBox.information(
                self,
                "Regenerado",
                f"Reporte del {reporte.fecha} regenerado correctamente.",
            )
            self._refrescar_tabla_reportes()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al regenerar reporte:\n{str(e)}")

    # ------------------------------------------------------------------
    # _exportar_reporte_excel(): exporta el reporte seleccionado a Excel
    # ------------------------------------------------------------------
    # Abre un QFileDialog para que el usuario elija donde guardar
    # el archivo .xlsx y luego llama a ReporteService.exportar_excel().
    #
    # QFileDialog.GetSaveFileName: ventana para elegir ubicacion y
    # nombre del archivo a guardar.
    #   - Filtro: "*.xlsx" para que solo se vean archivos Excel.
    #   - Devuelve: (ruta_completa, filtro_seleccionado).
    # ------------------------------------------------------------------
    def _exportar_reporte_excel(self) -> None:
        """Exporta el reporte seleccionado a un archivo Excel."""
        fila = self.tabla_reportes.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Seleccion", "Seleccione un reporte de la tabla.")
            return

        # Obtener el ID del reporte seleccionado.
        item_id = self.tabla_reportes.item(fila, 0)
        if item_id is None:
            return
        reporte_id = int(item_id.text())

        # Abrir dialogo para elegir ubicacion del archivo.
        # QFileDialog.getSaveFileName: ventana de "Guardar como".
        ruta, _filtro = QFileDialog.getSaveFileName(
            self,
            "Guardar Reporte Excel",
            f"reporte_diario_{date.today().isoformat()}.xlsx",
            "Archivos Excel (*.xlsx)",
        )

        if not ruta:
            return  # El usuario cancelo.

        try:
            self.controlador_reportes.exportar_excel(reporte_id, ruta)
            QMessageBox.information(
                self,
                "Exportado",
                f"Reporte exportado correctamente a:\n{ruta}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al exportar:\n{str(e)}")


# ============================================================
# DIALOGO: ProductoDialog (crear / editar productos)
# ============================================================
# QDialog que se abre para AGREGAR o EDITAR un producto.
#
# Tiene DOS modos de uso:
#   1. Crear: ProductoDialog(padre) → campos vacios, crea un producto nuevo.
#   2. Editar: ProductoDialog(padre, producto=existente) → campos
#      pre-cargados, guarda los cambios sobre el mismo producto.
#
# Como se distingue entre crear y editar?
#   - Si producto es None (o no se pasa) → modo CREAR.
#   - Si producto tiene un valor → modo EDITAR.
#
# Layout del dialogo:
#   ┌─────────────────────────────────────┐
#   │  Nombre:    [____________________]  │
#   │  Categoria: [____________________]  │
#   │  Precio Compra:  [___0.00____]      │
#   │  Precio Venta Bs:[___0.00____]      │
#   │  Precio Venta USD:[___0.00____]     │
#   │  Stock Actual:   [___0_____]        │
#   │  Stock Minimo:   [___5_____]        │
#   │  Unidad:  [UNIDAD________________]  │
#   │                                     │
#   │          [Cancelar]  [Guardar]      │
#   └─────────────────────────────────────┘
# ============================================================
class ProductoDialog(QDialog):
    # __init__: recibe el widget padre y opcionalmente un producto para editar.
    def __init__(
        self,
        parent: QWidget | None = None,
        producto: Producto | None = None,
        controlador_productos: ProductoController | None = None,
    ) -> None:
        # Llamar al constructor de QDialog.
        super().__init__(parent)

        # Guardar el controlador de productos para usarlo en _guardar().
        # A diferencia de VentaDialog, ProductoDialog ANTES obtenia el
        # controlador via self.parent().controlador_productos, pero eso
        # causaba el error:
        #   "'QObject' object has no attribute 'controlador_productos'"
        # porque PyQt6 no sabe que el parent es un MainWindow.
        #
        # Ahora recibimos el controlador directamente como parametro,
        # asi no dependemos de self.parent() para nada.
        # Si no se pasa, _guardar() mostrara un error en lugar de crashear.
        self.controlador_productos = controlador_productos

        # Guardar el producto que se va a editar (None si es modo crear).
        self.producto = producto

        # Establecer el titulo segun el modo.
        if producto:
            self.setWindowTitle(f"Editar producto: {producto.nombre_producto}")
        else:
            self.setWindowTitle("Agregar producto")

        # Tamano fijo del dialogo.
        self.setFixedSize(420, 380)

        # Crear los campos del formulario.
        self._setup_ui()

        # Si estamos en modo editar, llenar los campos con los datos actuales.
        if producto:
            self._cargar_datos(producto)

    # ------------------------------------------------------------------
    # _setup_ui: construye los campos del formulario
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        """Crea todos los campos del formulario y los botones."""
        # Layout vertical principal.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # ----------------------------------------------------------
        # FORMULARIO (QFormLayout)
        # ----------------------------------------------------------
        # QFormLayout: organiza los campos en filas etiqueta + control.
        form = QFormLayout()

        # Campo: Nombre del producto (QLineEdit).
        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText("Nombre del producto")
        form.addRow("Nombre:", self.txt_nombre)

        # Campo: Categoria (QLineEdit).
        self.txt_categoria = QLineEdit()
        self.txt_categoria.setPlaceholderText("Ej: LACTEOS, BEBIDAS, etc.")
        form.addRow("Categoria:", self.txt_categoria)

        # Campo: Precio de compra (QDoubleSpinBox).
        # QDoubleSpinBox: campo numerico con decimales (igual a un "input type=number").
        # setRange(0, 999999): valores permitidos entre 0 y casi 1 millon.
        # setDecimals(2): 2 decimales (centimos).
        # setPrefix("Bs. "): texto que aparece ANTES del numero.
        self.spin_precio_compra = QDoubleSpinBox()
        self.spin_precio_compra.setRange(0, 999999)
        self.spin_precio_compra.setDecimals(2)
        self.spin_precio_compra.setPrefix("Bs. ")
        form.addRow("Precio Compra:", self.spin_precio_compra)

        # Campo: Precio venta en bolivares.
        self.spin_precio_venta_bs = QDoubleSpinBox()
        self.spin_precio_venta_bs.setRange(0, 999999)
        self.spin_precio_venta_bs.setDecimals(2)
        self.spin_precio_venta_bs.setPrefix("Bs. ")
        form.addRow("Precio Venta Bs:", self.spin_precio_venta_bs)

        # Campo: Precio venta en dolares.
        self.spin_precio_venta_usd = QDoubleSpinBox()
        self.spin_precio_venta_usd.setRange(0, 999999)
        self.spin_precio_venta_usd.setDecimals(2)
        self.spin_precio_venta_usd.setPrefix("$ ")
        form.addRow("Precio Venta USD:", self.spin_precio_venta_usd)

        # Campo: Stock actual (QSpinBox, solo enteros).
        self.spin_stock_actual = QSpinBox()
        self.spin_stock_actual.setRange(0, 999999)
        form.addRow("Stock Actual:", self.spin_stock_actual)

        # Campo: Stock minimo (para alertas de reabastecimiento).
        self.spin_stock_minimo = QSpinBox()
        self.spin_stock_minimo.setRange(1, 999999)
        self.spin_stock_minimo.setValue(5)  # Valor por defecto.
        form.addRow("Stock Minimo:", self.spin_stock_minimo)

        # Campo: Unidad de medida.
        self.txt_unidad = QLineEdit()
        self.txt_unidad.setPlaceholderText("UNIDAD, KG, LTS, etc.")
        self.txt_unidad.setText("UNIDAD")  # Valor por defecto.
        form.addRow("Unidad:", self.txt_unidad)

        # Agregar el formulario al layout principal.
        layout.addLayout(form)

        # ----------------------------------------------------------
        # BOTONES (Aceptar / Cancelar)
        # ----------------------------------------------------------
        layout.addSpacing(20)

        # Layout horizontal para los botones.
        btn_layout = QHBoxLayout()
        # addStretch(): agrega espacio flexible ANTES de los botones,
        #   empujandolos hacia la derecha.
        btn_layout.addStretch()

        # Boton Cancelar: cierra el dialogo sin guardar.
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        # Boton Guardar: valida y guarda el producto.
        btn_guardar = QPushButton("Guardar")
        btn_guardar.clicked.connect(self._guardar)
        btn_layout.addWidget(btn_guardar)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # _cargar_datos: llena los campos con los valores de un producto existente
    # ------------------------------------------------------------------
    # Solo se usa en modo editar.
    # ------------------------------------------------------------------
    def _cargar_datos(self, producto: Producto) -> None:
        """Rellena los campos con los datos del producto a editar."""
        self.txt_nombre.setText(producto.nombre_producto)
        if producto.categoria:
            self.txt_categoria.setText(producto.categoria)
        self.spin_precio_compra.setValue(float(producto.precio_compra))
        self.spin_precio_venta_bs.setValue(float(producto.precio_venta_bs))
        self.spin_precio_venta_usd.setValue(float(producto.precio_venta_usd))
        self.spin_stock_actual.setValue(producto.stock_actual)
        self.spin_stock_minimo.setValue(producto.stock_minimo)
        self.txt_unidad.setText(producto.unidad)

    # ------------------------------------------------------------------
    # _guardar: valida los campos y guarda el producto (crear o editar)
    # ------------------------------------------------------------------
    # Se ejecuta al hacer clic en "Guardar".
    # Si es modo crear: llama a controlador_productos.crear().
    # Si es modo editar: llama a controlador_productos.actualizar().
    # ------------------------------------------------------------------
    def _guardar(self) -> None:
        """Valida los campos y guarda el producto en la BD."""
        # ----------------------------------------------------------
        # PASO 1: Validar campos obligatorios
        # ----------------------------------------------------------
        nombre = self.txt_nombre.text().strip()
        if not nombre:
            # Mostrar advertencia y NO cerrar el dialogo.
            QMessageBox.warning(self, "Validacion", "El nombre es obligatorio.")
            self.txt_nombre.setFocus()  # Poner el cursor en el campo nombre.
            return

        # ----------------------------------------------------------
        # PASO 2: Obtener valores de los campos
        # ----------------------------------------------------------
        categoria = self.txt_categoria.text().strip() or None
        precio_compra = self.spin_precio_compra.value()
        precio_venta_bs = self.spin_precio_venta_bs.value()
        precio_venta_usd = self.spin_precio_venta_usd.value()
        stock_actual = self.spin_stock_actual.value()
        stock_minimo = self.spin_stock_minimo.value()
        unidad = self.txt_unidad.text().strip().upper() or "UNIDAD"

        # ----------------------------------------------------------
        # PASO 3: Guardar (crear o actualizar segun el modo)
        # ----------------------------------------------------------
        try:
            if self.producto:
                # MODO EDITAR: actualizar el producto existente.
                # Llamamos a actualizar() del controlador con los campos a modificar.
                self.producto.nombre_producto = nombre
                self.producto.categoria = categoria
                self.producto.precio_compra = Decimal(str(precio_compra))
                self.producto.precio_venta_bs = Decimal(str(precio_venta_bs))
                self.producto.precio_venta_usd = Decimal(str(precio_venta_usd))
                self.producto.stock_actual = stock_actual
                self.producto.stock_minimo = stock_minimo
                self.producto.unidad = unidad

                # Obtener el ID del producto (nunca es None porque el producto existe).
                producto_id = self.producto.idproducto
                assert producto_id is not None

                # Usar el controlador que recibimos en el constructor.
                # Antes usabamos self.parent().controlador_productos, pero eso
                # fallaba porque parent() devuelve QObject y PyQt6 no reconoce
                # los atributos personalizados de MainWindow.
                if not self.controlador_productos:
                    QMessageBox.critical(
                        self, "Error",
                        "Controlador de productos no disponible. "
                        "Contacte al administrador.",
                    )
                    return
                self.controlador_productos.actualizar(
                    producto_id,
                    nombre_producto=nombre,
                    categoria=categoria,
                    precio_compra=Decimal(str(precio_compra)),
                    precio_venta_bs=Decimal(str(precio_venta_bs)),
                    precio_venta_usd=Decimal(str(precio_venta_usd)),
                    stock_actual=stock_actual,
                    stock_minimo=stock_minimo,
                    unidad=unidad,
                )
            else:
                # MODO CREAR: crear un nuevo producto.
                # Construimos un objeto Producto con los datos del formulario.
                nuevo = Producto(
                    nombre_producto=nombre,
                    categoria=categoria,
                    precio_compra=Decimal(str(precio_compra)),
                    precio_venta_bs=Decimal(str(precio_venta_bs)),
                    precio_venta_usd=Decimal(str(precio_venta_usd)),
                    stock_actual=stock_actual,
                    stock_minimo=stock_minimo,
                    unidad=unidad,
                )
                if not self.controlador_productos:
                    QMessageBox.critical(
                        self, "Error",
                        "Controlador de productos no disponible. "
                        "Contacte al administrador.",
                    )
                    return
                self.controlador_productos.crear(nuevo)

            # Si todo salio bien, cerrar el dialogo con exito.
            self.accept()

        except ValueError as e:
            # ValueError es lanzado por el controlador si hay datos invalidos.
            QMessageBox.warning(self, "Error de validacion", str(e))
        except Exception as e:
            # Cualquier otro error inesperado.
            QMessageBox.critical(self, "Error inesperado", f"No se pudo guardar el producto:\n{e}")


# ============================================================
# DIALOGO: VentaDialog (crear una nueva venta)
# ============================================================
# Este dialogo guia al usuario paso a paso para crear una venta:
#
#   1. SELECCIONAR PRODUCTOS:
#      - Elige un producto de un QComboBox (desplegable con todos los productos).
#      - Indica la cantidad con un QSpinBox.
#      - Clic "Agregar" → se agrega a la tabla de productos de la venta.
#
#   2. REVISAR PRODUCTOS AGREGADOS:
#      - La tabla muestra: producto, cantidad, precio unitario, subtotal.
#      - Se puede eliminar un producto de la venta si me equivoco.
#      - El total se actualiza automaticamente.
#
#   3. METODO DE PAGO:
#      - Ingresar montos en efectivo Bs, efectivo USD, tarjeta, etc.
#      - El sistema valida que la suma de pagos cubra el total.
#
#   4. FINALIZAR:
#      - Clic "Finalizar Venta" → VentaController.crear() → descuenta stock.
#
# Layout visual:
#   ┌──────────────────────────────────────────────────┐
#   │  Producto: [QComboBox v]  Cant: [5] [Agregar]   │
#   ├──────────────────────────────────────────────────┤
#   │  Productos de la venta:                          │
#   │  ┌──────────┬──────┬────────┬──────────┬──────┐ │
#   │  │ Producto │ Cant │ P.Unit │ Subtotal │ Elim │ │
#   │  ├──────────┼──────┼────────┼──────────┼──────┤ │
#   │  │ Arroz    │  2   │ 1.50   │  3.00    │ [X]  │ │
#   │  │ Aceite   │  1   │ 2.50   │  2.50    │ [X]  │ │
#   │  └──────────┴──────┴────────┴──────────┴──────┘ │
#   │  TOTAL: Bs. 5.50                                 │
#   ├──────────────────────────────────────────────────┤
#   │  Metodo de Pago:                                 │
#   │  Efectivo Bs: [____] USD: [____]                 │
#   │  Tarjeta: [_____] PagoMovil: [___] BioPago:[__] │
#   ├──────────────────────────────────────────────────┤
#   │           [Cancelar]  [Finalizar Venta]          │
#   └──────────────────────────────────────────────────┘
# ============================================================
class VentaDialog(QDialog):
    # __init__: recibe el MainWindow como padre y los controladores.
    # En lugar de obtener los controladores via self.parent() como hace
    # ProductoDialog, los recibimos directamente como parametros.
    # Esto es MAS CLARO porque se ve explicitamente que controladores usa.
    def __init__(
        self,
        parent: QWidget | None = None,
        controlador_productos: ProductoController | None = None,
        controlador_ventas: VentaController | None = None,
        controlador_tasas: TasaCambioService | None = None,
    ) -> None:
        # Llamar al constructor de QDialog.
        super().__init__(parent)

        # Guardar los controladores para usarlos en los metodos.
        self.controlador_productos = controlador_productos
        self.controlador_ventas = controlador_ventas
        self.controlador_tasas = controlador_tasas

        # Configuracion basica de la ventana.
        self.setWindowTitle("Nueva Venta")
        self.resize(700, 600)  # Mas grande porque tiene muchos componentes.

        # Lista temporal: aqui guardamos los productos que se van agregando
        #   antes de enviarlos al controlador.
        # Cada elemento es un dict con: idproducto, nombre, cantidad, precio, subtotal.
        self.productos_venta: list[dict[str, object]] = []

        # Total acumulado de la venta en bolivares.
        self.total_bs = Decimal("0.00")

        # Construir la interfaz grafica.
        self._setup_ui()

        # Cargar los productos en el QComboBox para que el usuario pueda elegirlos.
        self._cargar_combo_productos()

        # Actualizar la tasa de cambio mostrada.
        self._actualizar_tasa()

    # ------------------------------------------------------------------
    # _setup_ui: construye todos los widgets del dialogo
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:  # noqa: PLR0915
        """Crea los widgets del dialogo de nueva venta."""
        # Layout vertical principal.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # ----------------------------------------------------------
        # SECCION: SELECCIONAR PRODUCTO
        # ----------------------------------------------------------
        # QGroupBox: un cuadro con borde y titulo para agrupar widgets relacionados.
        grupo_producto = QGroupBox("Agregar Producto")
        # Layout horizontal para el grupo.
        grupo_layout = QHBoxLayout(grupo_producto)

        # QComboBox: lista desplegable para elegir un producto.
        # El usuario hace clic y ve todos los productos disponibles.
        self.combo_producto = QComboBox()
        self.combo_producto.setMinimumWidth(300)
        self.combo_producto.setPlaceholderText("Selecciona un producto...")
        grupo_layout.addWidget(self.combo_producto)

        # QSpinBox: cantidad del producto a vender (minimo 1).
        self.spin_cantidad = QSpinBox()
        self.spin_cantidad.setRange(1, 9999)
        self.spin_cantidad.setValue(1)
        grupo_layout.addWidget(QLabel("Cant:"))
        grupo_layout.addWidget(self.spin_cantidad)

        # Boton: Agregar producto a la lista de la venta.
        btn_agregar = QPushButton("Agregar")
        btn_agregar.clicked.connect(self._agregar_producto_venta)
        grupo_layout.addWidget(btn_agregar)

        layout.addWidget(grupo_producto)

        # ----------------------------------------------------------
        # SECCION: TABLA DE PRODUCTOS DE LA VENTA
        # ----------------------------------------------------------
        layout.addSpacing(10)
        layout.addWidget(QLabel("Productos de la venta:"))

        self.tabla_productos_venta = QTableWidget()
        columnas = [
            ("Producto", 200),
            ("Cantidad", 60),
            ("P.Unit Bs", 100),
            ("Subtotal", 100),
            ("", 40),
        ]
        self.tabla_productos_venta.setColumnCount(len(columnas))
        self.tabla_productos_venta.setHorizontalHeaderLabels([c[0] for c in columnas])
        for i, (_, ancho) in enumerate(columnas):
            self.tabla_productos_venta.setColumnWidth(i, ancho)
        self.tabla_productos_venta.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabla_productos_venta.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # layout.addWidget con factor 1 para que ocupe espacio vertical.
        layout.addWidget(self.tabla_productos_venta, 1)

        # ----------------------------------------------------------
        # TOTAL DE LA VENTA
        # ----------------------------------------------------------
        # QLabel que muestra el total actualizado en tiempo real.
        self.lbl_total = QLabel("Total: Bs. 0.00")
        self.lbl_total.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.lbl_total)

        # Tasa de cambio activa (informativa).
        self.lbl_tasa = QLabel("Tasa BCV: ---")
        self.lbl_tasa.setStyleSheet("color: #666;")
        layout.addWidget(self.lbl_tasa)

        # ----------------------------------------------------------
        # SECCION: METODO DE PAGO
        # ----------------------------------------------------------
        layout.addSpacing(10)
        grupo_pago = QGroupBox("Metodo de Pago")
        form_pago = QFormLayout(grupo_pago)

        # Cada metodo de pago tiene su propio QDoubleSpinBox.
        # El usuario ingresa el monto recibido por cada metodo.

        self.spin_efectivo_bs = QDoubleSpinBox()
        self.spin_efectivo_bs.setRange(0, 999999)
        self.spin_efectivo_bs.setDecimals(2)
        self.spin_efectivo_bs.setPrefix("Bs. ")
        form_pago.addRow("Efectivo Bs:", self.spin_efectivo_bs)

        self.spin_efectivo_usd = QDoubleSpinBox()
        self.spin_efectivo_usd.setRange(0, 999999)
        self.spin_efectivo_usd.setDecimals(2)
        self.spin_efectivo_usd.setPrefix("$ ")
        form_pago.addRow("Efectivo USD:", self.spin_efectivo_usd)

        self.spin_tarjeta = QDoubleSpinBox()
        self.spin_tarjeta.setRange(0, 999999)
        self.spin_tarjeta.setDecimals(2)
        self.spin_tarjeta.setPrefix("Bs. ")
        form_pago.addRow("Tarjeta:", self.spin_tarjeta)

        self.spin_pago_movil = QDoubleSpinBox()
        self.spin_pago_movil.setRange(0, 999999)
        self.spin_pago_movil.setDecimals(2)
        self.spin_pago_movil.setPrefix("Bs. ")
        form_pago.addRow("Pago Movil:", self.spin_pago_movil)

        self.spin_bio_pago = QDoubleSpinBox()
        self.spin_bio_pago.setRange(0, 999999)
        self.spin_bio_pago.setDecimals(2)
        self.spin_bio_pago.setPrefix("Bs. ")
        form_pago.addRow("BioPago:", self.spin_bio_pago)

        layout.addWidget(grupo_pago)

        # ----------------------------------------------------------
        # BOTONES DE ACCION
        # ----------------------------------------------------------
        layout.addSpacing(10)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        # Boton "Finalizar Venta": verde para indicar accion positiva.
        btn_finalizar = QPushButton("Finalizar Venta")
        btn_finalizar.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px 20px;"
        )
        btn_finalizar.clicked.connect(self._finalizar_venta)
        btn_layout.addWidget(btn_finalizar)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # _cargar_combo_productos: llena el QComboBox con todos los productos
    # ------------------------------------------------------------------
    def _cargar_combo_productos(self) -> None:
        """Carga la lista de productos en el QComboBox."""
        if not self.controlador_productos:
            return

        # Obtener todos los productos.
        productos = self.controlador_productos.listar_todos()

        # Limpiar el combo por si ya tenia datos.
        self.combo_producto.clear()

        # Agregar cada producto como un item.
        # setItemData: guardamos el ID del producto como "user data"
        #   para recuperarlo despues sin tener que parsear el texto.
        for p in productos:
            texto = f"{p.nombre_producto} (Stock: {p.stock_actual})"
            self.combo_producto.addItem(texto, p.idproducto)

    # ------------------------------------------------------------------
    # _actualizar_tasa: muestra la tasa de cambio activa en la UI
    # ------------------------------------------------------------------
    def _actualizar_tasa(self) -> None:
        """Actualiza el label de la tasa de cambio."""
        if not self.controlador_tasas:
            return
        tasa = self.controlador_tasas.tasa_activa()
        if tasa:
            self.lbl_tasa.setText(f"Tasa BCV: Bs. {tasa.tasa_venta} / USD  (activa: {tasa.fecha})")
        else:
            self.lbl_tasa.setText("Tasa BCV: No hay tasa activa registrada.")

    # ------------------------------------------------------------------
    # _agregar_producto_venta: agrega el producto seleccionado a la venta
    # ------------------------------------------------------------------
    def _agregar_producto_venta(self) -> None:
        """Agrega el producto seleccionado a la lista de la venta."""
        # Asegurar que los controladores no sean None (se pasan en el constructor).
        assert self.controlador_productos is not None
        assert self.controlador_ventas is not None

        # Obtener el ID del producto seleccionado en el combo.
        # .currentData() devuelve el "user data" que guardamos con addItem.
        idproducto = self.combo_producto.currentData()
        if idproducto is None:
            QMessageBox.warning(self, "Agregar", "Selecciona un producto.")
            return

        # Obtener la cantidad del QSpinBox.
        cantidad = self.spin_cantidad.value()

        # Obtener el producto completo para saber su precio y nombre.
        producto = self.controlador_productos.obtener_por_id(int(idproducto))
        if not producto:
            QMessageBox.warning(self, "Error", "El producto no existe.")
            return

        # Validar stock disponible.
        if producto.stock_actual < cantidad:
            QMessageBox.warning(
                self,
                "Stock insuficiente",
                f"Stock disponible: {producto.stock_actual}. Solicitado: {cantidad}.",
            )
            return

        # Calcular subtotal.
        subtotal = producto.precio_venta_bs * Decimal(str(cantidad))

        # Agregar a la lista temporal.
        self.productos_venta.append(
            {
                "idproducto": producto.idproducto,
                "nombre": producto.nombre_producto,
                "cantidad": cantidad,
                "precio": producto.precio_venta_bs,
                "subtotal": subtotal,
            }
        )

        # Actualizar el total acumulado.
        self.total_bs += subtotal

        # Refrescar la tabla y el label de total.
        self._refrescar_tabla_productos()
        self._actualizar_total()

    # ------------------------------------------------------------------
    # _refrescar_tabla_productos: actualiza la tabla con los productos agregados
    # ------------------------------------------------------------------
    def _refrescar_tabla_productos(self) -> None:
        """Refresca la tabla de productos de la venta."""
        self.tabla_productos_venta.setRowCount(len(self.productos_venta))

        for fila, item in enumerate(self.productos_venta):
            self.tabla_productos_venta.setItem(
                fila, 0, QTableWidgetItem(str(item.get("nombre", "")))
            )
            self.tabla_productos_venta.setItem(
                fila, 1, QTableWidgetItem(str(item.get("cantidad", 0)))
            )
            precio = item.get("precio", Decimal("0.00"))
            self.tabla_productos_venta.setItem(fila, 2, QTableWidgetItem(f"Bs. {precio:.2f}"))
            subtotal = item.get("subtotal", Decimal("0.00"))
            self.tabla_productos_venta.setItem(fila, 3, QTableWidgetItem(f"Bs. {subtotal:.2f}"))

            # Boton "X" para eliminar el producto de la venta.
            # QPushButton dentro de la tabla usando setCellWidget.
            # Esto permite poner cualquier widget dentro de una celda.
            btn_eliminar = QPushButton("X")
            btn_eliminar.setStyleSheet("color: red; font-weight: bold;")
            btn_eliminar.clicked.connect(lambda _=False, f=fila: self._eliminar_producto_venta(f))
            self.tabla_productos_venta.setCellWidget(fila, 4, btn_eliminar)

    # ------------------------------------------------------------------
    # _actualizar_total: actualiza el QLabel del total y el total_usd
    # ------------------------------------------------------------------
    def _actualizar_total(self) -> None:
        """Actualiza el label del total de la venta."""
        self.lbl_total.setText(f"Total: Bs. {self.total_bs:.2f}")

    # ------------------------------------------------------------------
    # _eliminar_producto_venta: quita un producto de la lista temporal
    # ------------------------------------------------------------------
    def _eliminar_producto_venta(self, fila: int) -> None:
        """Elimina un producto de la lista de la venta."""
        if 0 <= fila < len(self.productos_venta):
            # Restar el subtotal del total acumulado.
            subtotal = Decimal(str(self.productos_venta[fila].get("subtotal", "0.00")))
            self.total_bs -= subtotal
            # Eliminar de la lista.
            self.productos_venta.pop(fila)
            # Refrescar la tabla y el total.
            self._refrescar_tabla_productos()
            self._actualizar_total()

    # ------------------------------------------------------------------
    # _finalizar_venta: valida y guarda la venta en la BD
    # ------------------------------------------------------------------
    def _finalizar_venta(self) -> None:
        """Valida los datos y finaliza la venta."""
        # ----------------------------------------------------------
        # PASO 1: Validar que haya al menos un producto en la venta.
        # ----------------------------------------------------------
        if not self.productos_venta:
            QMessageBox.warning(self, "Venta vacia", "Agrega al menos un producto a la venta.")
            return

        # ----------------------------------------------------------
        # PASO 2: Construir la lista de productos para el controlador.
        # ----------------------------------------------------------
        # El controlador espera: [{"idproducto": int, "cantidad": int}, ...]
        productos: list[dict[str, object]] = []
        for item in self.productos_venta:
            productos.append(
                {
                    "idproducto": int(str(item.get("idproducto", 0))),
                    "cantidad": int(str(item.get("cantidad", 1))),
                }
            )

        # ----------------------------------------------------------
        # PASO 3: Construir el diccionario de metodo de pago.
        # ----------------------------------------------------------
        # Usamos Decimal para mantener precision monetaria.
        metodo_pago: dict[str, object] = {
            "efectivo_bs": Decimal(str(self.spin_efectivo_bs.value())),
            "efectivo_usd": Decimal(str(self.spin_efectivo_usd.value())),
            "tarjeta": Decimal(str(self.spin_tarjeta.value())),
            "pago_movil": Decimal(str(self.spin_pago_movil.value())),
            "bio_pago": Decimal(str(self.spin_bio_pago.value())),
        }

        # ----------------------------------------------------------
        # PASO 4: Llamar al controlador para crear la venta.
        # ----------------------------------------------------------
        assert self.controlador_ventas is not None
        try:
            venta = self.controlador_ventas.crear(productos, metodo_pago)

            # Si llegamos aqui, la venta se creo correctamente.
            QMessageBox.information(
                self,
                "Venta exitosa",
                f"Venta registrada correctamente.\n"
                f"Factura: {venta.numero_factura}\n"
                f"Total: Bs. {venta.total_bs:.2f}",
            )

            # Cerrar el dialogo con exito.
            self.accept()

        except ValueError as e:
            # Error de validacion (stock insuficiente, pagos, etc.).
            QMessageBox.warning(self, "Error", str(e))
        except Exception as e:
            # Error inesperado.
            QMessageBox.critical(
                self,
                "Error inesperado",
                f"No se pudo crear la venta:\n{e}",
            )
