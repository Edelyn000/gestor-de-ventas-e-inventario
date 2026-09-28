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
from ..utils.logging_setup import registrar_excepcion


# FormularioCambioContrasena: Cambio de contrasena autenticado.
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
        btn_guardar.setProperty("rol", "guardar")
        btn_guardar.clicked.connect(self._guardar)
        btn_layout.addWidget(btn_guardar)

        layout.addLayout(btn_layout)

    def _guardar(self) -> None:
        if self.usuario is None:
            return

        contrasena_actual = self.txt_contrasena_actual.text()
        if not contrasena_actual:
            QMessageBox.warning(self, "Error", "Debes ingresar tu contraseña actual.")
            return

        if not self.auth_service.verificar_login(self.usuario.usuario, contrasena_actual):
            QMessageBox.warning(self, "Error", "La contraseña actual no es correcta.")
            return

        cambios = False
        errores: list[str] = []

        cambios |= self._actualizar_nombre(errores)
        cambios |= self._actualizar_usuario(errores)
        cambios |= self._actualizar_contrasena(contrasena_actual, errores)

        if errores:
            QMessageBox.warning(self, "Errores", "\n".join(errores))
            return

        if cambios:
            nuevo_nombre = self.txt_nombre_completo.text().strip()
            if nuevo_nombre:
                self.usuario.nombre_completo = nuevo_nombre
            QMessageBox.information(self, "Exito", "Datos actualizados correctamente.")
            self.accept()
        else:
            QMessageBox.information(self, "Sin cambios", "No se realizaron cambios.")
            self.reject()

    def _actualizar_nombre(self, errores: list[str]) -> bool:
        usuario = self.usuario
        if usuario is None or usuario.id is None:
            return False
        nuevo_nombre = self.txt_nombre_completo.text().strip()
        if not nuevo_nombre or nuevo_nombre == usuario.nombre_completo:
            return False
        try:
            self.auth_service.actualizar(usuario.id, nombre_completo=nuevo_nombre)
            return True
        except ValueError as e:
            errores.append(str(e))
            return False
        except Exception as e:
            registrar_excepcion(e, "FormularioCambioContrasena._actualizar_nombre")
            errores.append(f"Error inesperado al actualizar el nombre: {e}")
            return False

    def _actualizar_usuario(self, errores: list[str]) -> bool:
        usuario = self.usuario
        if usuario is None or usuario.id is None:
            return False
        nuevo_usuario = self.txt_nuevo_usuario.text().strip()
        if not nuevo_usuario or nuevo_usuario == usuario.usuario:
            return False
        try:
            self.auth_service.actualizar(usuario.id, usuario=nuevo_usuario)
            usuario.usuario = nuevo_usuario
            return True
        except ValueError as e:
            errores.append(str(e))
            return False
        except Exception as e:
            registrar_excepcion(e, "FormularioCambioContrasena._actualizar_usuario")
            errores.append(f"Error inesperado al actualizar el usuario: {e}")
            return False

    def _actualizar_contrasena(self, contrasena_actual: str, errores: list[str]) -> bool:
        usuario = self.usuario
        if usuario is None or usuario.id is None:
            return False
        nueva_contrasena = self.txt_nueva_contrasena.text()
        if not nueva_contrasena:
            return False
        try:
            ok = self.auth_service.cambiar_contrasena(
                usuario.id,
                contrasena_actual,
                nueva_contrasena,
            )
            if ok:
                return True
            errores.append("No se pudo cambiar la contraseña.")
            return False
        except ValueError as e:
            errores.append(str(e))
            return False
        except Exception as e:
            registrar_excepcion(e, "FormularioCambioContrasena._actualizar_contrasena")
            errores.append(f"Error inesperado al cambiar la contrasena: {e}")
            return False

