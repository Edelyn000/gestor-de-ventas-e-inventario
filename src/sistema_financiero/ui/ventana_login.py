# ============================================================
# ARCHIVO: ui/ventana_login.py  (VENTANA DE INICIO DE SESION)
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
# bcrypt: lo usamos para verificar la contrasena del usuario
#   en el login. Comparamos el hash guardado con el ingresado.
import bcrypt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from sqlmodel import select

from ..models import Usuario, get_session


class VentanaLogin(QDialog):
    usuario_actual: Usuario | None = None

    # __init__: constructor de la clase. Se ejecuta cuando se crea el dialogo.
    def __init__(self) -> None:
        # super().__init__(): llama al constructor de QDialog (clase padre).
        # Esto asegura que la ventana se configure correctamente.
        super().__init__()

        # setWindowTitle: texto que aparece en la barra de titulo de la ventana.
        self.setWindowTitle("Sistema Financiero — Iniciar Sesión")

        # setFixedSize: la ventana NO se puede redimensionar (ancho x alto).
        # Elegimos 360x200 porque es suficientemente grande para el formulario
        # pero no ocupa toda la pantalla.
        self.setFixedSize(360, 200)
        self.setStyleSheet("background-color: white;")

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

        # Guardar el usuario logueado para que VentanaPrincipal lo use.
        self.usuario_actual = user

        # accept(): cierra el dialogo con codigo de "aceptado".
        # __main__.py detecta esto y abre VentanaPrincipal.
        self.accept()

