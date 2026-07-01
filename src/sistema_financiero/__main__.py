import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from .db import seed_admin
from .models import create_db_and_tables
from .ui.interfaz import VentanaPrincipal
from .ui.ventana_login import VentanaLogin


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Sistema Financiero")

    fuente = QFont()
    fuente.setPointSize(12)
    app.setFont(fuente)

    app.setStyleSheet("""
        QLabel, QTableWidget, QPushButton,
        QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit,
        QTextEdit, QPlainTextEdit, QGroupBox, QCheckBox,
        QRadioButton, QTabWidget, QHeaderView, QAbstractSpinBox {
            color: #1a1a1a;
        }
    """)

    create_db_and_tables()
    seed_admin()

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
