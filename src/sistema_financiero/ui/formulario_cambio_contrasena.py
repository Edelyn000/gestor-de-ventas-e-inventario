# ============================================================
# ARCHIVO: ui/formulario_cambio_contrasena.py
# ============================================================
# Dialogo para que el usuario cambie su nombre de usuario,
# nombre completo y contrasena desde la misma interfaz.
#
# QUE SE PUEDE MODIFICAR:
#   - Estilos, colores, fuentes, textos.
#   - Validaciones (longitud minima de contrasena).
#
# QUE NO SE DEBE TOCAR:
#   - Nombre de la clase (FormularioCambioContrasena).
#   - La logica de llamar a AuthService.
# ============================================================
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


class FormularioCambioContrasena(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        usuario: Usuario | None = None,
    ) -> None:
        super().__init__(parent)

        self.usuario = usuario
        self.auth_service = AuthService()

        self.setWindowTitle("Cambiar Contraseña / Usuario")
        self.setFixedSize(400, 300)
        self.setStyleSheet("background-color: white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel(f"Usuario actual: {usuario.usuario if usuario else ''}"))

        form = QFormLayout()

        self.txt_nombre_completo = QLineEdit()
        self.txt_nombre_completo.setText(usuario.nombre_completo if usuario else "")
        form.addRow("Nombre completo:", self.txt_nombre_completo)

        self.txt_nuevo_usuario = QLineEdit()
        self.txt_nuevo_usuario.setPlaceholderText("Dejar vacio para mantener el actual")
        form.addRow("Nuevo usuario:", self.txt_nuevo_usuario)

        self.txt_contrasena_actual = QLineEdit()
        self.txt_contrasena_actual.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_contrasena_actual.setPlaceholderText("Requerido para cambios")
        form.addRow("Contraseña actual:", self.txt_contrasena_actual)

        self.txt_nueva_contrasena = QLineEdit()
        self.txt_nueva_contrasena.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_nueva_contrasena.setPlaceholderText("Dejar vacio para no cambiar")
        form.addRow("Nueva contraseña:", self.txt_nueva_contrasena)

        layout.addLayout(form)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        btn_guardar = QPushButton("Guardar Cambios")
        btn_guardar.setStyleSheet(
            "background-color: #2196F3; color: white; font-weight: bold; padding: 8px 16px;"
        )
        btn_guardar.clicked.connect(self._guardar)
        btn_layout.addWidget(btn_guardar)

        layout.addLayout(btn_layout)

    def _guardar(self) -> None:  # noqa: PLR0912
        if self.usuario is None:
            return

        contrasena_actual = self.txt_contrasena_actual.text()
        if not contrasena_actual:
            QMessageBox.warning(self, "Error", "Debes ingresar tu contraseña actual.")
            return

        # Verificar contrasena actual antes de cualquier cambio.
        if not self.auth_service.verificar_login(self.usuario.usuario, contrasena_actual):
            QMessageBox.warning(self, "Error", "La contraseña actual no es correcta.")
            return

        cambios = False
        errores: list[str] = []

        # Cambiar nombre completo.
        nuevo_nombre = self.txt_nombre_completo.text().strip()
        if nuevo_nombre and nuevo_nombre != self.usuario.nombre_completo:
            try:
                self.auth_service.actualizar(
                    self.usuario.id,  # type: ignore[arg-type]
                    nombre_completo=nuevo_nombre,
                )
                cambios = True
            except ValueError as e:
                errores.append(str(e))

        # Cambiar nombre de usuario.
        nuevo_usuario = self.txt_nuevo_usuario.text().strip()
        if nuevo_usuario and nuevo_usuario != self.usuario.usuario:
            try:
                self.auth_service.actualizar(
                    self.usuario.id,  # type: ignore[arg-type]
                    usuario=nuevo_usuario,
                )
                self.usuario.usuario = nuevo_usuario
                cambios = True
            except ValueError as e:
                errores.append(str(e))

        # Cambiar contrasena.
        nueva_contrasena = self.txt_nueva_contrasena.text()
        if nueva_contrasena:
            try:
                ok = self.auth_service.cambiar_contrasena(
                    self.usuario.id,  # type: ignore[arg-type]
                    contrasena_actual,
                    nueva_contrasena,
                )
                if ok:
                    cambios = True
                else:
                    errores.append("No se pudo cambiar la contraseña.")
            except ValueError as e:
                errores.append(str(e))

        # Mostrar resultado.
        if errores:
            QMessageBox.warning(self, "Errores", "\n".join(errores))
            return

        if cambios:
            # Actualizar el nombre completo en el objeto usuario.
            if nuevo_nombre:
                self.usuario.nombre_completo = nuevo_nombre
            QMessageBox.information(self, "Exito", "Datos actualizados correctamente.")
            self.accept()
        else:
            QMessageBox.information(self, "Sin cambios", "No se realizaron cambios.")
            self.reject()
