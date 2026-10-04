# dialogo_primer_uso.py: Creacion del administrador cuando no hay usuarios.
import logging

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..core.auth_service import AuthService
from ..utils import LONGITUD_MINIMA_CONTRASENA, ROL_ADMINISTRADOR
from ..utils.logging_setup import registrar_evento, registrar_excepcion


# DialogoPrimerUso: Crea el administrador en el primer inicio.
class DialogoPrimerUso(QDialog):
    # Monta el formulario de creacion del administrador.
    def __init__(self) -> None:
        super().__init__()

        self.auth_service = AuthService()

        self.setWindowTitle("Gestor de Ventas e Inventario — Configuración inicial")
        self.setFixedSize(400, 360)

        self._setup_ui()

    # Construye la cabecera, los campos y los botones.
    def _setup_ui(self) -> None:
        """Construye la cabecera, los campos y los botones."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        cabecera = QFrame()
        cabecera.setProperty("rol", "cabecera_aplicacion")
        cabecera.setFixedHeight(48)
        layout_cabecera = QHBoxLayout(cabecera)
        layout_cabecera.setContentsMargins(16, 0, 16, 0)
        lbl_titulo = QLabel("Configuración inicial")
        lbl_titulo.setProperty("rol", "cabecera_aplicacion_titulo")
        layout_cabecera.addWidget(lbl_titulo)
        layout.addWidget(cabecera)

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(18, 14, 18, 12)
        cuerpo.setSpacing(8)

        aviso = QLabel("Crea el usuario administrador. No hay ninguna contraseña por defecto.")
        aviso.setWordWrap(True)
        cuerpo.addWidget(aviso)

        form = QFormLayout()
        form.setSpacing(8)

        self.txt_nombre_completo = QLineEdit()
        self.txt_nombre_completo.setPlaceholderText("Opcional")
        form.addRow("Nombre completo:", self.txt_nombre_completo)

        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("Nombre de usuario")
        form.addRow("Usuario:", self.txt_usuario)

        self.txt_contrasena = QLineEdit()
        self.txt_contrasena.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_contrasena.setPlaceholderText(
            f"Mínimo {LONGITUD_MINIMA_CONTRASENA} caracteres",
        )
        form.addRow("Contraseña:", self.txt_contrasena)

        self.txt_confirmar = QLineEdit()
        self.txt_confirmar.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_confirmar.setPlaceholderText("Repite la contraseña")
        form.addRow("Repetir contraseña:", self.txt_confirmar)

        cuerpo.addLayout(form)

        btn_layout = QHBoxLayout()

        btn_salir = QPushButton("Salir")
        btn_salir.clicked.connect(self.reject)

        btn_crear = QPushButton("Crear Administrador")
        btn_crear.setProperty("rol", "primario")
        btn_crear.setDefault(True)
        btn_crear.clicked.connect(self._crear)

        btn_layout.addWidget(btn_salir)
        btn_layout.addWidget(btn_crear)

        cuerpo.addLayout(btn_layout)
        layout.addLayout(cuerpo)

    # Crea el administrador si los campos son validos.
    def _crear(self) -> None:
        """Crea el administrador si los campos son validos."""
        nombre = self.txt_nombre_completo.text().strip()
        usuario = self.txt_usuario.text().strip()
        contrasena = self.txt_contrasena.text()
        confirmar = self.txt_confirmar.text()

        errores = self._validar(usuario, contrasena, confirmar)
        if errores:
            QMessageBox.warning(self, "Error", "\n".join(errores))
            return

        try:
            self.auth_service.crear_usuario(
                usuario=usuario,
                contrasena=contrasena,
                nombre_completo=nombre or None,
                rol=ROL_ADMINISTRADOR,
            )
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        except Exception as e:
            registrar_excepcion(e, "DialogoPrimerUso._crear")
            QMessageBox.warning(
                self,
                "Error",
                f"Error inesperado al crear el administrador: {e}",
            )
            return

        registrar_evento(logging.INFO, f"Primer inicio: administrador '{usuario}' creado.")
        self.accept()

    # Revisa los campos escritos y devuelve la lista de errores.
    def _validar(self, usuario: str, contrasena: str, confirmar: str) -> list[str]:
        """Revisa los campos escritos y devuelve la lista de errores."""
        errores: list[str] = []

        if not usuario:
            errores.append("El nombre de usuario es obligatorio.")

        if not contrasena:
            errores.append("La contraseña es obligatoria.")
        elif len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
            errores.append(
                f"La contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres.",
            )
        elif contrasena == usuario:
            errores.append("La contraseña no puede ser igual al nombre de usuario.")

        if not confirmar:
            errores.append("Debes repetir la contraseña.")
        elif confirmar != contrasena:
            errores.append("Las contraseñas no coinciden.")

        return errores
