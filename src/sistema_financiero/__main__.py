import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from .db import ejecutar_todos
from .models import create_db_and_tables
from .ui.estilos import QSS_APP
from .ui.interfaz import VentanaPrincipal
from .ui.ventana_login import VentanaLogin
from .utils.logging_setup import configurar_logging, manejar_excepcion_no_manejada


def main() -> None:
    # Nunca permitir que un error quede invisible: se registra en
    # logs/errores.log y se muestra un dialogo (sys.excepthook).
    configurar_logging()
    sys.excepthook = manejar_excepcion_no_manejada

    app = QApplication(sys.argv)
    app.setApplicationName("ABASTO PA' QUE JESUS")

    fuente = QFont()
    fuente.setPointSize(12)
    # Tipografia del sistema: letra moderna y legible en Windows.
    fuente.setFamily("Segoe UI")
    app.setFont(fuente)

    # Tema claro centralizado (fondo gris claro, letras oscuras):
    # TODO el QSS vive en ui/estilos.py (unico lugar para estilos).
    app.setStyleSheet(QSS_APP)

    create_db_and_tables()
    ejecutar_todos()

    login = VentanaLogin()
    if login.exec() == VentanaLogin.DialogCode.Accepted:
        usuario = login.usuario_actual
        assert usuario is not None
        window = VentanaPrincipal(usuario)
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
