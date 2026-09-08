# ============================================================
# ARCHIVO: ui/usuarios_pagina.py  (PAGINA DE GESTION DE USUARIOS)
# ============================================================
# Widget para gestionar usuarios del sistema.
# Solo visible para usuarios con rol ADMINISTRADOR.
#
# QUE MUESTRA:
#   1. Seccion "Mi perfil": datos del usuario actual + boton editar.
#   2. Seccion "Otros usuarios": tabla con los demas usuarios.
#   3. Boton "Crear usuario" (solo admin).
#
# --- NO TOCAR: nombre de la clase (UsuariosPagina), firma del __init__.
# --- MODIFICABLE: estilos, colores, fuentes, textos, columnas.
# ============================================================
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.auth_service import AuthService
from ..models import Usuario
from .formulario_cambio_contrasena import FormularioCambioContrasena
from .widgets import TablaProductos


# ============ PAGINA DE USUARIOS ============
class UsuariosPagina(QWidget):
    """Pagina de gestion de usuarios (solo admin)."""

    # --- NO TOCAR: firma del constructor.
    def __init__(self, usuario_actual: Usuario) -> None:
        super().__init__()

        self.usuario_actual = usuario_actual
        self.auth_service = AuthService()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # --- MODIFICABLE: texto, fuente, tamano del titulo.
        lbl_titulo = QLabel("Usuarios")
        fuente = QFont()
        fuente.setPointSize(24)
        fuente.setBold(True)
        lbl_titulo.setFont(fuente)
        layout.addWidget(lbl_titulo)

        # --- Seccion Mi perfil.
        layout.addWidget(self._crear_seccion_perfil())
        layout.addSpacing(10)

        # --- Seccion Otros usuarios (solo admin).
        self._seccion_otros = self._crear_seccion_otros_usuarios()
        layout.addWidget(self._seccion_otros)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Seccion: Mi perfil
    # ------------------------------------------------------------------
    def _crear_seccion_perfil(self) -> QWidget:
        """Muestra los datos del usuario actual con boton para editar."""
        contenedor = QWidget()
        lay = QVBoxLayout(contenedor)
        lay.setContentsMargins(0, 0, 0, 0)

        lbl_seccion = QLabel("Mi perfil")
        lbl_seccion.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
        lay.addWidget(lbl_seccion)

        info = QVBoxLayout()
        info.setSpacing(5)

        self.lbl_nombre = QLabel(f"Nombre: {self.usuario_actual.nombre_completo or '-'}")
        self.lbl_usuario = QLabel(f"Usuario: {self.usuario_actual.usuario}")
        self.lbl_rol = QLabel(f"Rol: {self.usuario_actual.rol}")

        info.addWidget(self.lbl_nombre)
        info.addWidget(self.lbl_usuario)
        info.addWidget(self.lbl_rol)
        lay.addLayout(info)

        lay.addSpacing(10)

        btn_layout = QHBoxLayout()

        btn_editar = QPushButton("Editar Perfil")
        btn_editar.clicked.connect(self._editar_perfil)
        btn_layout.addWidget(btn_editar)

        btn_contrasena = QPushButton("Cambiar Contraseña")
        btn_contrasena.clicked.connect(self._cambiar_contrasena)
        btn_layout.addWidget(btn_contrasena)

        btn_layout.addStretch()
        lay.addLayout(btn_layout)

        return contenedor

    # ------------------------------------------------------------------
    # Seccion: Otros usuarios (solo admin)
    # ------------------------------------------------------------------
    def _crear_seccion_otros_usuarios(self) -> QWidget:
        """Tabla con los otros usuarios y acciones de admin."""
        contenedor = QWidget()
        lay = QVBoxLayout(contenedor)
        lay.setContentsMargins(0, 0, 0, 0)

        lbl_seccion = QLabel("Otros usuarios")
        lbl_seccion.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
        lay.addWidget(lbl_seccion)

        # --- MODIFICABLE: columnas y anchos de la tabla.
        columnas = [
            ("ID", 50),
            ("Nombre", 180),
            ("Usuario", 120),
            ("Rol", 100),
            ("Estado", 80),
        ]
        self.tabla_usuarios = TablaProductos(columnas)
        lay.addWidget(self.tabla_usuarios)

        # --- Botones de accion.
        btn_layout = QHBoxLayout()

        btn_crear = QPushButton("+ Crear Usuario")
        btn_crear.setStyleSheet(
            "background-color: #4CAF50; color: white;"
            " font-weight: bold; padding: 8px 16px; border-radius: 4px;",
        )
        btn_crear.clicked.connect(self._crear_usuario)
        btn_layout.addWidget(btn_crear)

        btn_reset = QPushButton("Resetear Contraseña")
        btn_reset.clicked.connect(self._resetear_contrasena)
        btn_layout.addWidget(btn_reset)

        btn_toggle = QPushButton("Activar / Desactivar")
        btn_toggle.clicked.connect(self._toggle_activo)
        btn_layout.addWidget(btn_toggle)

        btn_layout.addStretch()
        lay.addLayout(btn_layout)

        # --- NO TOCAR: carga inicial.
        self._cargar_tabla()

        return contenedor

    # ------------------------------------------------------------------
    # Metodos de accion
    # ------------------------------------------------------------------
    def _editar_perfil(self) -> None:
        """Abre el dialogo de edicion de perfil."""
        dialogo = FormularioCambioContrasena(
            parent=self,
            usuario=self.usuario_actual,
        )
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self._refrescar_perfil()

    def _cambiar_contrasena(self) -> None:
        """Abre el dialogo de cambio de contrasena."""
        dialogo = FormularioCambioContrasena(
            parent=self,
            usuario=self.usuario_actual,
        )
        dialogo.exec()

    def _crear_usuario(self) -> None:
        """Abre el dialogo para crear un nuevo usuario."""
        dialogo = DialogoCrearUsuario(parent=self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self._cargar_tabla()

    def _resetear_contrasena(self) -> None:
        """Resetea la contrasena del usuario seleccionado."""
        fila = self.tabla_usuarios.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Seleccion", "Seleccione un usuario de la tabla.")
            return

        item_id = self.tabla_usuarios.item(fila, 0)
        if item_id is None:
            return
        id_usuario = int(item_id.text())

        item_usuario = self.tabla_usuarios.item(fila, 2)
        nombre_usuario = item_usuario.text() if item_usuario else ""

        dialogo = DialogoResetContrasena(
            parent=self,
            id_usuario=id_usuario,
            nombre_usuario=nombre_usuario,
        )
        dialogo.exec()

    def _toggle_activo(self) -> None:
        """Activa o desactiva el usuario seleccionado."""
        fila = self.tabla_usuarios.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Seleccion", "Seleccione un usuario de la tabla.")
            return

        item_id = self.tabla_usuarios.item(fila, 0)
        if item_id is None:
            return
        id_usuario = int(item_id.text())

        item_estado = self.tabla_usuarios.item(fila, 4)
        estado_actual = item_estado.text() if item_estado else "Activo"
        activo = estado_actual == "Activo"

        if activo:
            self.auth_service.desactivar(id_usuario)
            QMessageBox.information(self, "Exito", "Usuario desactivado.")
        else:
            self.auth_service.activar(id_usuario)
            QMessageBox.information(self, "Exito", "Usuario activado.")

        self._cargar_tabla()

    # ------------------------------------------------------------------
    # Metodos auxiliares
    # ------------------------------------------------------------------
    def _cargar_tabla(self) -> None:
        """Carga todos los usuarios excepto el actual."""
        todos = self.auth_service.listar_usuarios()
        otros = [u for u in todos if u.id != self.usuario_actual.id]

        self.tabla_usuarios.setRowCount(len(otros))
        for fila, user in enumerate(otros):
            self.tabla_usuarios.setItem(fila, 0, QTableWidgetItem(str(user.id or "")))
            self.tabla_usuarios.setItem(fila, 1, QTableWidgetItem(user.nombre_completo or "-"))
            self.tabla_usuarios.setItem(fila, 2, QTableWidgetItem(user.usuario))
            self.tabla_usuarios.setItem(fila, 3, QTableWidgetItem(user.rol))
            estado = "Activo" if user.activo else "Inactivo"
            self.tabla_usuarios.setItem(fila, 4, QTableWidgetItem(estado))

    def _refrescar_perfil(self) -> None:
        """Refresca los labels del perfil con datos actualizados."""
        self.lbl_nombre.setText(f"Nombre: {self.usuario_actual.nombre_completo or '-'}")
        self.lbl_usuario.setText(f"Usuario: {self.usuario_actual.usuario}")
        self.lbl_rol.setText(f"Rol: {self.usuario_actual.rol}")

    def cargar(self) -> None:
        """Recarga datos (llamado desde VentanaPrincipal si es necesario)."""
        self._cargar_tabla()
        self._refrescar_perfil()


# ============================================================
# DIALOGO: Crear usuario nuevo
# ============================================================
class DialogoCrearUsuario(QDialog):
    """Dialogo simple para crear un usuario."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.auth_service = AuthService()

        self.setWindowTitle("Crear Usuario")
        self.setFixedSize(400, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()

        self.txt_nombre_completo = QLineEdit()
        self.txt_nombre_completo.setPlaceholderText("Nombre y apellido")
        form.addRow("Nombre completo:", self.txt_nombre_completo)

        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("Nombre de usuario")
        form.addRow("Usuario:", self.txt_usuario)

        self.txt_contrasena = QLineEdit()
        self.txt_contrasena.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_contrasena.setPlaceholderText("Minimo 4 caracteres")
        form.addRow("Contraseña:", self.txt_contrasena)

        self.cmb_rol = QComboBox()
        self.cmb_rol.addItems(["VENDEDOR", "ADMINISTRADOR"])
        form.addRow("Rol:", self.cmb_rol)

        layout.addLayout(form)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        btn_crear = QPushButton("Crear")
        btn_crear.setStyleSheet(
            "background-color: #4CAF50; color: white;"
            " font-weight: bold; padding: 8px 16px; border-radius: 4px;",
        )
        btn_crear.clicked.connect(self._crear)
        btn_layout.addWidget(btn_crear)

        layout.addLayout(btn_layout)

    def _crear(self) -> None:
        nombre = self.txt_nombre_completo.text().strip()
        usuario = self.txt_usuario.text().strip()
        contrasena = self.txt_contrasena.text()
        rol = self.cmb_rol.currentText()

        if not usuario or not contrasena:
            QMessageBox.warning(self, "Error", "Usuario y contraseña son requeridos.")
            return

        try:
            self.auth_service.crear_usuario(
                usuario=usuario,
                contrasena=contrasena,
                nombre_completo=nombre or None,
                rol=rol,
            )
            QMessageBox.information(self, "Exito", f"Usuario '{usuario}' creado correctamente.")
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))


# ============================================================
# DIALOGO: Resetear contrasena
# ============================================================
class DialogoResetContrasena(QDialog):
    """Dialogo para que el admin resetee la contrasena de otro usuario."""

    def __init__(
        self,
        parent: QWidget | None = None,
        id_usuario: int = 0,
        nombre_usuario: str = "",
    ) -> None:
        super().__init__(parent)
        self.auth_service = AuthService()
        self.id_usuario = id_usuario

        self.setWindowTitle(f"Resetear Contraseña — {nombre_usuario}")
        self.setFixedSize(360, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel(f"Usuario: {nombre_usuario}"))

        form = QFormLayout()
        self.txt_nueva = QLineEdit()
        self.txt_nueva.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_nueva.setPlaceholderText("Minimo 4 caracteres")
        form.addRow("Nueva contraseña:", self.txt_nueva)
        layout.addLayout(form)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        btn_guardar = QPushButton("Guardar")
        btn_guardar.setStyleSheet(
            "background-color: #89b4fa; color: #1e1e2e;"
            " font-weight: bold; padding: 8px 16px; border-radius: 4px;",
        )
        btn_guardar.clicked.connect(self._guardar)
        btn_layout.addWidget(btn_guardar)

        layout.addLayout(btn_layout)

    def _guardar(self) -> None:
        nueva = self.txt_nueva.text()
        if not nueva:
            QMessageBox.warning(self, "Error", "La contraseña es requerida.")
            return

        try:
            ok = self.auth_service.cambiar_contrasena_admin(
                self.id_usuario, nueva,
            )
            if ok:
                QMessageBox.information(self, "Exito", "Contraseña actualizada.")
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "No se pudo actualizar la contraseña.")
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
