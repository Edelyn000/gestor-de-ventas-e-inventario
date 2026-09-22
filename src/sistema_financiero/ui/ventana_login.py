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
# SEGURIDAD:
#   - NO existe "olvide mi contrasena" en el login: cualquiera
#     podria resetear credenciales sin identificarse (mala
#     practica). El cambio de contrasena solo es posible con
#     sesion iniciada (formulario_cambio_contrasena.py) o por
#     el administrador (usuarios_pagina.py).
#   - Cada login exitoso/fallido se registra en logs/eventos.log
#     (auditoria). Jamas se registra la contrasena.
#
# --- NO TOCAR: nombre de la clase (VentanaLogin), logica de
#     validacion con bcrypt, consulta a BD.
# --- MODIFICABLE: textos, placeholders, tamanos, espaciados.
#     Los estilos globales viven en ui/estilos.py (tema claro).
# ============================================================
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

# --- NO TOCAR: importaciones de modelos y utilidades.
from ..models import Usuario, obtener_sesion
from ..utils.logging_setup import registrar_evento


# ============ VENTANA DE LOGIN PRINCIPAL ============
# --- NO TOCAR: clase, logica de validacion con bcrypt y BD.
# --- MODIFICABLE: textos, placeholders, tamaño, espaciados.
class VentanaLogin(QDialog):
    # --- NO TOCAR: almacenamiento del usuario logueado.
    usuario_actual: Usuario | None = None

    # --- NO TOCAR: firma del constructor.
    def __init__(self) -> None:
        super().__init__()

        # --- MODIFICABLE: titulo, tamaño y espaciado (compacto).
        self.setWindowTitle("ABASTO PA' QUE JESUS — Iniciar Sesión")
        self.setFixedSize(340, 235)
        # Fondo claro de la paleta solo en el dialogo (el header azul y el
        # resto del estilo vienen de ui/estilos.py). Se usa el selector
        # QDialog para NO pisar el fondo de la barra superior.
        self.setStyleSheet("QDialog { background-color: #f3f4f6; }")

        self._setup_ui()

    # --- MODIFICABLE: construccion de la interfaz (campos, botones).
    def _setup_ui(self) -> None:
        """Construye los campos de usuario, contrasena y botones."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra superior azul (misma que la ventana principal).
        cabecera = QFrame()
        cabecera.setProperty("rol", "cabecera_aplicacion")
        cabecera.setFixedHeight(48)
        layout_cabecera = QHBoxLayout(cabecera)
        layout_cabecera.setContentsMargins(16, 0, 16, 0)
        lbl_titulo = QLabel("ABASTO PA' QUE JESUS")
        lbl_titulo.setProperty("rol", "cabecera_aplicacion_titulo")
        layout_cabecera.addWidget(lbl_titulo)
        layout.addWidget(cabecera)

        # Cuerpo del formulario (debajo del header).
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

        # --- MODIFICABLE: textos de botones.
        btn_layout = QHBoxLayout()

        btn_ingresar = QPushButton("Ingresar")
        btn_ingresar.setProperty("rol", "primario")
        # --- NO TOCAR: conexion a _validar_login.
        btn_ingresar.clicked.connect(self._validar_login)

        btn_salir = QPushButton("Salir")
        btn_salir.clicked.connect(self.reject)

        btn_layout.addWidget(btn_ingresar)
        btn_layout.addWidget(btn_salir)

        cuerpo.addLayout(btn_layout)
        layout.addLayout(cuerpo)

    # --- NO TOCAR: logica de validacion de credenciales con bcrypt y BD.
    def _validar_login(self) -> None:
        """Verifica credenciales contra la BD y registra la auditoria."""
        usuario = self.txt_usuario.text().strip()
        # NOTA: la contrasena NO se hace strip() — paridad con
        # auth_service.crear_usuario(), que la hashea tal cual.
        contrasena = self.txt_contrasena.text()

        if not usuario or not contrasena:
            registrar_evento(logging.WARNING, "Intento de login con campos vacios.")
            QMessageBox.warning(self, "Error", "Usuario y contraseña son requeridos.")
            return

        # --- NO TOCAR: consulta a BD y verificacion bcrypt.
        with obtener_sesion() as session:
            user = session.exec(select(Usuario).where(Usuario.usuario == usuario)).first()

        if user is None or not bcrypt.checkpw(
            contrasena.encode("utf-8"),
            user.contrasena.encode("utf-8"),
        ):
            # Auditoria: se registra el usuario intentado, NUNCA la contrasena.
            registrar_evento(
                logging.WARNING,
                f"Intento de login fallido para el usuario: {usuario}",
            )
            QMessageBox.warning(self, "Error", "Usuario o contraseña incorrectos.")
            return

        registrar_evento(logging.INFO, f"Login exitoso del usuario: {usuario}")

        # --- NO TOCAR: almacenamiento del usuario y cierre exitoso.
        self.usuario_actual = user
        self.accept()
