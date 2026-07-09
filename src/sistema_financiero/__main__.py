import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from .db import ejecutar_todos
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
        QMainWindow, QWidget, QDialog {
            background-color: #1e1e2e;
            color: #cdd6f4;
        }
        QLabel {
            color: #cdd6f4;
        }
        QGroupBox {
            background-color: #2a2a3e;
            border: 1px solid #3a3a4e;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
            color: #cdd6f4;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
            background-color: #2a2a3e;
            color: #cdd6f4;
            border: 1px solid #3a3a4e;
            border-radius: 4px;
            padding: 4px;
        }
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border: 1px solid #89b4fa;
        }
        QComboBox::drop-down {
            background-color: #2a2a3e;
            border: none;
        }
        QComboBox QAbstractItemView {
            background-color: #2a2a3e;
            color: #cdd6f4;
            selection-background-color: #45475a;
        }
        QPushButton {
            background-color: #45475a;
            color: #cdd6f4;
            border: none;
            border-radius: 4px;
            padding: 6px 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #585b70;
        }
        QPushButton:pressed {
            background-color: #313244;
        }
        QTableWidget, QTableWidget QHeaderView {
            background-color: #2a2a3e;
            color: #cdd6f4;
            gridline-color: #3a3a4e;
            border: 1px solid #3a3a4e;
            border-radius: 4px;
        }
        QTableWidget::item {
            padding: 4px;
        }
        QTableWidget::item:selected {
            background-color: #45475a;
        }
        QHeaderView::section {
            background-color: #3a3a4e;
            color: #cdd6f4;
            padding: 6px;
            border: none;
            border-right: 1px solid #2a2a3e;
            font-weight: bold;
        }
        QListWidget {
            background-color: #16162a;
            color: #cdd6f4;
            border: none;
            outline: none;
        }
        QListWidget::item {
            padding: 12px;
            border-bottom: 1px solid #2a2a3e;
        }
        QListWidget::item:selected {
            background-color: #45475a;
            color: #89b4fa;
        }
        QListWidget::item:hover {
            background-color: #2a2a3e;
        }
        QStatusBar {
            background-color: #16162a;
            color: #a6adc8;
        }
        QFrame {
            background-color: #2a2a3e;
            border-radius: 10px;
        }
        QScrollBar:vertical {
            background-color: #2a2a3e;
            width: 10px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background-color: #45475a;
            border-radius: 5px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #585b70;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QMessageBox {
            background-color: #1e1e2e;
        }
        QMessageBox QLabel {
            color: #cdd6f4;
        }
        QMessageBox QPushButton {
            min-width: 80px;
        }
    """)

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
