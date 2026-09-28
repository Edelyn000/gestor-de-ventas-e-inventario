# __main__.py: Entrypoint: login, ventana principal y bucle de sesiones.
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
    configurar_logging()
    sys.excepthook = manejar_excepcion_no_manejada

    app = QApplication(sys.argv)
    app.setApplicationName("Gestor de Ventas e Inventario")

    fuente = QFont()
    fuente.setPointSize(12)
    fuente.setFamily("Segoe UI")
    app.setFont(fuente)

    app.setStyleSheet(QSS_APP)

    create_db_and_tables()
    ejecutar_todos()

    while True:
        login = VentanaLogin()
        if login.exec() != VentanaLogin.DialogCode.Accepted:
            sys.exit(0)
        usuario = login.usuario_actual
        assert usuario is not None

        ventana = VentanaPrincipal(usuario)
        salida_por_logout = False

        def _marcar_logout() -> None:
            nonlocal salida_por_logout
            salida_por_logout = True

        ventana.sesion_cerrada.connect(_marcar_logout)
        ventana.show()
        app.exec()
        if not salida_por_logout:
            sys.exit(0)


if __name__ == "__main__":
    main()

