# ============================================================
# ARCHIVO: ui/ventana_login.py  (VENTANA DE INICIO DE SESION)
# ============================================================
# QDialog es una ventana MODAL: bloquea la interaccion con otras
# ventanas hasta que se cierra. Ideal para login.
#
# Flujo:
#   1. __main__.py crea VentanaLogin y lo muestra con .exec()
#   2. El usuario ingresa usuario + contrasena
#   3. _validar_login() verifica contra la BD usando bcrypt
#   4. Si es correcto → self.accept() (cierra el dialogo con exito)
#   5. Si es incorrecto → QMessageBox.warning() (muestra error)
#   6. __main__.py revisa si login fue aceptado o rechazado
#
# --- NO TOCAR: nombre de las clases (VentanaLogin, DialogoRestablecerContrasena),
#     logica de validacion con bcrypt, consulta a BD.
# --- MODIFICABLE: estilos (ESTILO_INPUT, ESTILO_COMBO, ESTILO_LABEL),
#     textos, placeholders, colores, tamanos.
# ============================================================
import bcrypt
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from sqlmodel import select

# --- NO TOCAR: importaciones de core y modelos.
from ..core import AuthService
from ..core.auth_service import LONGITUD_MINIMA_CONTRASENA
from ..models import Usuario, obtener_sesion

# --- MODIFICABLE: estilos de los inputs, combo y labels del login.
ESTILO_INPUT = (
    "QLineEdit { padding: 6px; font-size: 13px; border: 1px solid #ccc;"
    " border-radius: 4px; }"
    " QLineEdit:focus { border-color: #89b4fa; }"
)
ESTILO_COMBO = (
    "QComboBox { padding: 6px; font-size: 13px; border: 1px solid #ccc;"
    " border-radius: 4px; }"
)
ESTILO_LABEL = "font-size: 13px; font-weight: bold; color: #1e1e2e;"


# ============ DIALOGO RESTABLECER CONTRASENA (DESDE LOGIN) ============
# --- NO TOCAR: clase, logica de validacion y guardado.
# --- MODIFICABLE: estilos, textos, placeholders, roles disponibles.
class DialogoRestablecerContrasena(QDialog):
    """Dialogo desde el login: cambiar usuario, contrasena y/o rol."""

    _user: Usuario | None = None

    # --- NO TOCAR: firma del constructor.
    def __init__(self, parent: QDialog | None = None) -> None:
        super().__init__(parent)
        # --- NO TOCAR: servicio de autenticacion.
        self.auth_service = AuthService()

        # --- MODIFICABLE: titulo, tamaño, color de fondo.
        self.setWindowTitle("Cambiar Contraseña / Usuario")
        self.setFixedSize(400, 320)
        self.setStyleSheet("background-color: #f5f5f5;")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- MODIFICABLE: formulario completo (etiquetas, placeholders, estilos).
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("Tu nombre de usuario")
        self.txt_usuario.setStyleSheet(ESTILO_INPUT)

        self.txt_contrasena_actual = QLineEdit()
        self.txt_contrasena_actual.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_contrasena_actual.setPlaceholderText("Requerido para verificar")
        self.txt_contrasena_actual.setStyleSheet(ESTILO_INPUT)

        self.txt_nuevo_usuario = QLineEdit()
        self.txt_nuevo_usuario.setPlaceholderText("Dejar vacio para mantener el actual")
        self.txt_nuevo_usuario.setStyleSheet(ESTILO_INPUT)

        self.txt_nueva_contrasena = QLineEdit()
        self.txt_nueva_contrasena.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_nueva_contrasena.setPlaceholderText("Dejar vacio para no cambiar")
        self.txt_nueva_contrasena.setStyleSheet(ESTILO_INPUT)

        self.txt_confirmar_contrasena = QLineEdit()
        self.txt_confirmar_contrasena.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_confirmar_contrasena.setPlaceholderText("Confirmar nueva contraseña")
        self.txt_confirmar_contrasena.setStyleSheet(ESTILO_INPUT)

        self.cmb_rol = QComboBox()
        # --- MODIFICABLE: opciones de rol disponibles.
        self.cmb_rol.addItems(["VENDEDOR", "ADMINISTRADOR"])
        self.cmb_rol.setStyleSheet(ESTILO_COMBO)

        form.addRow("Usuario:", self.txt_usuario)
        form.addRow("Contraseña actual:", self.txt_contrasena_actual)
        form.addRow("Nuevo usuario:", self.txt_nuevo_usuario)
        form.addRow("Nueva contraseña:", self.txt_nueva_contrasena)
        form.addRow("Confirmar:", self.txt_confirmar_contrasena)
        form.addRow("Rol:", self.cmb_rol)

        layout.addLayout(form)

        # --- MODIFICABLE: estilo de los botones.
        btn_layout = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setStyleSheet(
            "padding: 8px 20px; font-size: 13px; border-radius: 4px;",
        )
        btn_cancelar.clicked.connect(self.reject)

        btn_guardar = QPushButton("Guardar Cambios")
        btn_guardar.setStyleSheet(
            "background-color: #89b4fa; color: #1e1e2e;"
            " font-weight: bold; padding: 8px 20px; font-size: 13px;"
            " border-radius: 4px;",
        )
        # --- NO TOCAR: conexion a _guardar.
        btn_guardar.clicked.connect(self._guardar)

        btn_layout.addWidget(btn_cancelar)
        btn_layout.addWidget(btn_guardar)
        layout.addLayout(btn_layout)

    # --- NO TOCAR: carga usuario desde BD.
    def _cargar_usuario(self, usuario: str) -> bool:
        user = self.auth_service.obtener_por_usuario(usuario)
        if user is None:
            return False
        self._user = user
        self.txt_nuevo_usuario.setPlaceholderText(user.usuario)
        idx = self.cmb_rol.findText(user.rol)
        if idx >= 0:
            self.cmb_rol.setCurrentIndex(idx)
        return True

    # --- MODIFICABLE: logica de validacion (mensajes, longitud minima).
    def _validar(self) -> list[str]:
        usuario = self.txt_usuario.text().strip()
        contrasena_actual = self.txt_contrasena_actual.text()
        nueva_contrasena = self.txt_nueva_contrasena.text()
        confirmar = self.txt_confirmar_contrasena.text()

        errores: list[str] = []
        if not usuario or not contrasena_actual:
            errores.append("Usuario y contraseña actual son requeridos.")

        if nueva_contrasena and nueva_contrasena != confirmar:
            errores.append("Las contraseñas nuevas no coinciden.")

        if nueva_contrasena and len(nueva_contrasena) < LONGITUD_MINIMA_CONTRASENA:
            errores.append(
                f"La contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres.",
            )
        return errores

    # --- NO TOCAR: logica de guardado (orquesta validacion, carga, aplicacion).
    def _guardar(self) -> None:
        errores = self._validar()
        if errores:
            QMessageBox.warning(self, "Error", "\n".join(errores))
            return

        usuario = self.txt_usuario.text().strip()
        contrasena_actual = self.txt_contrasena_actual.text()

        if not self._cargar_usuario(usuario):
            QMessageBox.warning(self, "Error", "El usuario no existe.")
            return

        user = self._user
        if user is None or user.id is None:
            return

        # --- NO TOCAR: verificacion de contrasena con bcrypt.
        if not self.auth_service.verificar_login(usuario, contrasena_actual):
            QMessageBox.warning(self, "Error", "Usuario o contraseña actual incorrectos.")
            return

        self._aplicar_cambios(user)

    # --- NO TOCAR: logica de aplicacion de cambios via AuthService.
    def _aplicar_cambios(self, user: Usuario) -> None:
        assert user.id is not None
        nuevo_usuario = self.txt_nuevo_usuario.text().strip()
        nueva_contrasena = self.txt_nueva_contrasena.text()
        contrasena_actual = self.txt_contrasena_actual.text()
        nuevo_rol = self.cmb_rol.currentText()

        cambios = False
        errores: list[str] = []

        if nuevo_usuario and nuevo_usuario != user.usuario:
            try:
                self.auth_service.actualizar(user.id, usuario=nuevo_usuario)
                user.usuario = nuevo_usuario
                cambios = True
            except ValueError as e:
                errores.append(str(e))

        if nuevo_rol != user.rol:
            try:
                self.auth_service.actualizar(user.id, rol=nuevo_rol)
                user.rol = nuevo_rol
                cambios = True
            except ValueError as e:
                errores.append(str(e))

        if nueva_contrasena:
            try:
                if self.auth_service.cambiar_contrasena(
                    user.id, contrasena_actual, nueva_contrasena,
                ):
                    cambios = True
                else:
                    errores.append("No se pudo cambiar la contraseña.")
            except ValueError as e:
                errores.append(str(e))

        if errores:
            QMessageBox.warning(self, "Errores", "\n".join(errores))
            return

        if cambios:
            QMessageBox.information(self, "Éxito", "Datos actualizados correctamente.")
            self.accept()
        else:
            QMessageBox.information(self, "Sin cambios", "No se realizaron cambios.")
            self.reject()


# ============ VENTANA DE LOGIN PRINCIPAL ============
# --- NO TOCAR: clase, logica de validacion con bcrypt y BD.
# --- MODIFICABLE: estilos, textos, placeholders, colores, tamaño.
class VentanaLogin(QDialog):
    # --- NO TOCAR: almacenamiento del usuario logueado.
    usuario_actual: Usuario | None = None

    # --- NO TOCAR: firma del constructor.
    def __init__(self) -> None:
        super().__init__()

        # --- MODIFICABLE: titulo, tamaño y color de fondo.
        self.setWindowTitle("Sistema Financiero — Iniciar Sesión")
        self.setFixedSize(360, 240)
        self.setStyleSheet("background-color: white;")

        self._setup_ui()

    # --- MODIFICABLE: construccion de la interfaz (campos, botones, estilos).
    def _setup_ui(self) -> None:
        """Construye los campos de usuario, contrasena y botones."""

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("Nombre de usuario")

        self.txt_contrasena = QLineEdit()
        self.txt_contrasena.setPlaceholderText("Contraseña")
        self.txt_contrasena.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Usuario:", self.txt_usuario)
        form.addRow("Contraseña:", self.txt_contrasena)

        layout.addLayout(form)

        # --- MODIFICABLE: textos de botones y estilos.
        btn_layout = QHBoxLayout()

        btn_ingresar = QPushButton("Ingresar")
        # --- NO TOCAR: conexion a _validar_login.
        btn_ingresar.clicked.connect(self._validar_login)

        btn_salir = QPushButton("Salir")
        btn_salir.clicked.connect(self.reject)

        btn_layout.addWidget(btn_ingresar)
        btn_layout.addWidget(btn_salir)

        layout.addLayout(btn_layout)

        # --- MODIFICABLE: texto y estilo del boton "Olvide mi contrasena".
        btn_olvide = QPushButton("¿Olvidaste tu contraseña?")
        btn_olvide.setFlat(True)
        btn_olvide.setStyleSheet(
            "color: #89b4fa; font-size: 11px; text-decoration: underline;",
        )
        # --- NO TOCAR: conexion al dialogo de restablecer.
        btn_olvide.clicked.connect(self._abrir_restablecer)
        layout.addWidget(btn_olvide, alignment=Qt.AlignmentFlag.AlignCenter)

    # --- NO TOCAR: apertura del dialogo de restablecer contrasena.
    def _abrir_restablecer(self) -> None:
        dialogo = DialogoRestablecerContrasena(self)
        dialogo.exec()

    # --- NO TOCAR: logica de validacion de credenciales con bcrypt y BD.
    def _validar_login(self) -> None:
        """Verifica credenciales contra la BD."""
        usuario = self.txt_usuario.text().strip()
        contrasena = self.txt_contrasena.text().strip()

        if not usuario or not contrasena:
            QMessageBox.warning(self, "Error", "Usuario y contraseña son requeridos.")
            return

        # --- NO TOCAR: consulta a BD y verificacion bcrypt.
        with obtener_sesion() as session:
            user = session.exec(select(Usuario).where(Usuario.usuario == usuario)).first()

        if user is None or not bcrypt.checkpw(
            contrasena.encode("utf-8"),
            user.contrasena.encode("utf-8"),
        ):
            QMessageBox.warning(self, "Error", "Usuario o contraseña incorrectos.")
            return

        # --- NO TOCAR: almacenamiento del usuario y cierre exitoso.
        self.usuario_actual = user
        self.accept()

