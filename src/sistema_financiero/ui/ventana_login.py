import logging

import bcrypt
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
from sqlmodel import select

from ..models import Usuario, obtener_sesion
from ..utils.logging_setup import registrar_evento


# VentanaLogin: Dialogo de inicio de sesion.
class VentanaLogin(QDialog):
    usuario_actual: Usuario | None = None

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Gestor de Ventas e Inventario — Iniciar Sesión")
        self.setFixedSize(340, 235)
        self.setStyleSheet("QDialog { background-color: #f3f4f6; }")

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construye los campos de usuario, contrasena y botones."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        cabecera = QFrame()
        cabecera.setProperty("rol", "cabecera_aplicacion")
        cabecera.setFixedHeight(48)
        layout_cabecera = QHBoxLayout(cabecera)
        layout_cabecera.setContentsMargins(16, 0, 16, 0)
        lbl_titulo = QLabel("Gestor de Ventas e Inventario")
        lbl_titulo.setProperty("rol", "cabecera_aplicacion_titulo")
        layout_cabecera.addWidget(lbl_titulo)
        layout.addWidget(cabecera)

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(18, 14, 18, 12)
        cuerpo.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)

        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("Nombre de usuario")

        self.txt_contrasena = QLineEdit()
        self.txt_contrasena.setPlaceholderText("Contraseña")
        self.txt_contrasena.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Usuario:", self.txt_usuario)
        form.addRow("Contraseña:", self.txt_contrasena)

        cuerpo.addLayout(form)

        btn_layout = QHBoxLayout()

        btn_ingresar = QPushButton("Ingresar")
        btn_ingresar.setProperty("rol", "primario")
        btn_ingresar.clicked.connect(self._validar_login)

        btn_salir = QPushButton("Salir")
        btn_salir.clicked.connect(self.reject)

        btn_layout.addWidget(btn_ingresar)
        btn_layout.addWidget(btn_salir)

        cuerpo.addLayout(btn_layout)
        layout.addLayout(cuerpo)

    def _validar_login(self) -> None:
        """Verifica credenciales contra la BD y registra la auditoria."""
        usuario = self.txt_usuario.text().strip()
        contrasena = self.txt_contrasena.text()

        if not usuario or not contrasena:
            registrar_evento(logging.WARNING, "Intento de login con campos vacios.")
            QMessageBox.warning(self, "Error", "Usuario y contraseña son requeridos.")
            return

        with obtener_sesion() as session:
            user = session.exec(select(Usuario).where(Usuario.usuario == usuario)).first()

        if user is None or not bcrypt.checkpw(
            contrasena.encode("utf-8"),
            user.contrasena.encode("utf-8"),
        ):
            registrar_evento(
                logging.WARNING,
                f"Intento de login fallido para el usuario: {usuario}",
            )
            QMessageBox.warning(self, "Error", "Usuario o contraseña incorrectos.")
            return

        registrar_evento(logging.INFO, f"Login exitoso del usuario: {usuario}")

        self.usuario_actual = user
        self.accept()

