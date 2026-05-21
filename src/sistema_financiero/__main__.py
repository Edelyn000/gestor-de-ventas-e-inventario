import sys

import bcrypt
from PyQt6.QtWidgets import QApplication
from sqlmodel import select

from .models import Usuario, create_db_and_tables, get_session
from .ui.interflaz import LoginDialog, MainWindow

# ============================================================
# ARCHIVO: __main__.py  (Entrypoint / Orquestador)
# ✅ QUE HACE:
#   - Crea la aplicacion QApplication de PyQt6
#   - Crea las tablas de la BD si no existen
#   - Crea el usuario admin por defecto (seed)
#   - Abre el LoginDialog y, si es exitoso, abre MainWindow
#
# ❌ QUE NO HACE:
#   - NO contiene widgets ni interfaces visuales
#   - NO define ventanas ni dialogos (eso esta en ui/interflaz.py)
#
# 📌 DIFERENCIA con ui/interflaz.py:
#   - __main__.py  = el "director" que organiza el inicio
#   - interflaz.py = los "actores" (ventanas, botones, campos)
#
# Flujo:
#   1. Crea/verifica las tablas de la BD
#   2. Crea el usuario admin por defecto si no existe
#   3. Muestra el dialogo de login
#   4. Si el login es exitoso, abre la ventana principal
# ============================================================


def _seed_admin() -> None:
    """Crea el usuario 'admin' con clave 'admin' la primera vez que se ejecuta."""
    with get_session() as session:
        if session.exec(select(Usuario)).first() is None:
            admin = Usuario(
                usuario="admin",
                contrasena=bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode("utf-8"),
                nombre_completo="Administrador",
                activo=True,
            )
            session.add(admin)
            session.commit()


def main() -> None:
    """Inicializa la aplicacion PyQt6, la BD y lanza el login."""
    app = QApplication(sys.argv)
    app.setApplicationName("Sistema Financiero")

    create_db_and_tables()
    _seed_admin()

    login = LoginDialog()
    if login.exec() == LoginDialog.DialogCode.Accepted:
        window = MainWindow(login.usuario_actual)
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
