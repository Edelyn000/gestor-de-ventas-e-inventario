from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.auth_service import AuthService
from ..models import Usuario
from ..utils.constantes import ROL_ADMINISTRADOR
from ..utils.logging_setup import registrar_excepcion


# DialogoAnulacion: Anulacion de venta con doble autorizacion.
class DialogoAnulacion(QDialog):
    """Solicita motivo de anulacion + credenciales de un administrador."""

    # Configura el dialogo de doble autorizacion para anular una venta.
    def __init__(
        self,
        parent: QWidget | None = None,
        numero_factura: str | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        super().__init__(parent)

        self.auth_service = auth_service if auth_service is not None else AuthService()
        self._usuario_autorizante: Usuario | None = None
        self._motivo: str = ""

        self.setWindowTitle("Anular Venta")
        self.setFixedSize(430, 230)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        factura = numero_factura or ""
        layout.addWidget(
            QLabel(
                f"Venta: {factura}\n"
                "Esta accion devolvera el stock de los productos y la venta "
                "dejara de contar en reportes y arqueos.",
            ),
        )

        form = QFormLayout()
        form.setSpacing(8)

        self.txt_motivo = QLineEdit()
        self.txt_motivo.setPlaceholderText("Motivo de la anulacion (obligatorio)")
        self.txt_motivo.textChanged.connect(self._actualizar_estado_boton)
        form.addRow("Motivo:", self.txt_motivo)

        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("Usuario administrador")
        form.addRow("Autorizado por:", self.txt_usuario)

        self.txt_contrasena = QLineEdit()
        self.txt_contrasena.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_contrasena.setPlaceholderText("Contraseña del administrador")
        form.addRow("Contraseña:", self.txt_contrasena)

        layout.addLayout(form)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        self.btn_anular = QPushButton("Anular Venta")
        self.btn_anular.setProperty("rol", "peligro")
        self.btn_anular.clicked.connect(self._validar)
        self.btn_anular.setEnabled(False)
        btn_layout.addWidget(self.btn_anular)

        layout.addLayout(btn_layout)

    # El motivo es obligatorio para poder anular.
    def _actualizar_estado_boton(self) -> None:
        """El motivo es obligatorio para poder anular."""
        self.btn_anular.setEnabled(bool(self.txt_motivo.text().strip()))

    # Valida credenciales de administrador y cierra con exito si pasan.
    def _validar(self) -> None:
        """Valida credenciales de administrador y cierra con exito si pasan."""
        motivo = self.txt_motivo.text().strip()
        if not motivo:
            QMessageBox.warning(self, "Anular Venta", "Debes indicar el motivo de la anulacion.")
            return

        usuario_txt = self.txt_usuario.text().strip()
        contrasena = self.txt_contrasena.text()
        if not usuario_txt or not contrasena:
            QMessageBox.warning(
                self,
                "Anular Venta",
                "Ingresa el usuario y la contrasena del administrador que autoriza.",
            )
            return

        try:
            usuario = self.auth_service.verificar_login(usuario_txt, contrasena)
        except Exception as e:
            registrar_excepcion(e, "DialogoAnulacion._validar")
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo verificar las credenciales.\n{e}",
            )
            return

        if usuario is None:
            QMessageBox.warning(self, "Anular Venta", "Usuario o contrasena incorrectos.")
            return

        if usuario.rol != ROL_ADMINISTRADOR:
            QMessageBox.warning(
                self,
                "Anular Venta",
                "Solo un administrador puede anular ventas.",
            )
            return

        self._usuario_autorizante = usuario
        self._motivo = motivo
        self.accept()

    # Motivo de anulacion validado (vacio si el dialogo fue cancelado).
    def motivo(self) -> str:
        """Motivo de anulacion validado (vacio si el dialogo fue cancelado)."""
        return self._motivo

    # Administrador que autorizo la anulacion (None si se cancelo).
    def usuario_autorizante(self) -> Usuario | None:
        """Administrador que autorizo la anulacion (None si se cancelo)."""
        return self._usuario_autorizante

