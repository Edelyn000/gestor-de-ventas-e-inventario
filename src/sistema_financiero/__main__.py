# __main__.py: Entrypoint: login, ventana principal y bucle de sesiones.
import logging
import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication
from sqlmodel import select

from .db import ejecutar_todos
from .models import Usuario, create_db_and_tables, obtener_sesion
from .ui.dialogo_primer_uso import DialogoPrimerUso
from .ui.estilos import QSS_APP
from .ui.interfaz import VentanaPrincipal
from .ui.ventana_login import VentanaLogin
from .utils.logging_setup import (
    configurar_logging,
    manejar_excepcion_no_manejada,
    registrar_evento,
)


# Crea el administrador en el primer inicio; retorna False si se cancela.
def asegurar_administrador() -> bool:
    """Pide crear el administrador si la tabla de usuarios esta vacia.

    Retorna False si el operador cancela el dialogo, para que el programa
    termine sin dejar la base a medio sembrar.
    """
    with obtener_sesion() as session:
        if session.exec(select(Usuario)).first() is not None:
            return True

    dialogo = DialogoPrimerUso()
    if dialogo.exec() != DialogoPrimerUso.DialogCode.Accepted:
        registrar_evento(
            logging.INFO,
            "Primer inicio cancelado: no se creo el administrador.",
        )
        return False

    return True


# Punto de entrada de la app: configura logs, lanza el login y el bucle de sesiones.
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
    if not asegurar_administrador():
        sys.exit(0)
    ejecutar_todos()

    while True:
        login = VentanaLogin()
        if login.exec() != VentanaLogin.DialogCode.Accepted:
            sys.exit(0)
        usuario = login.usuario_actual
        assert usuario is not None

        ventana = VentanaPrincipal(usuario)
        salida_por_logout = False

        # Marca que la salida fue un logout para relanzar el login.
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
