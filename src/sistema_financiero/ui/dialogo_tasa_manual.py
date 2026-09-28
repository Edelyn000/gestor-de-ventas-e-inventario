from decimal import Decimal

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..utils import parsear_decimal_escrito


# DialogoTasaManual: Dialogo para fijar una tasa manual.
class DialogoTasaManual(QDialog):
    """Pide una tasa de cambio manual (Bs. por USD) sin bug de locale."""

    ALTO_CAMPO_TASA = 34
    MARGEN = 20

    # Construye el dialogo para fijar una tasa manual sin tocar la BCV.
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._tasa_valor: Decimal | None = None

        self.setWindowTitle("Tasa Manual")
        self.setModal(True)
        self.setMinimumHeight(163)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.MARGEN, self.MARGEN, self.MARGEN, self.MARGEN)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Tasa de cambio (Bs. por USD):"))

        self.txt_tasa = QLineEdit()
        self.txt_tasa.setMinimumHeight(self.ALTO_CAMPO_TASA)
        self.txt_tasa.setPlaceholderText("Ej: 860,50 o 860.50")
        self.txt_tasa.textChanged.connect(self._actualizar_estado)
        layout.addWidget(self.txt_tasa)

        self.lbl_error = QLabel("")
        self.lbl_error.setProperty("rol", "resumen_falta")
        self.lbl_error.setWordWrap(True)
        layout.addWidget(self.lbl_error)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)

        self.btn_fijar = QPushButton("Fijar tasa")
        self.btn_fijar.setProperty("rol", "primario")
        self.btn_fijar.setDefault(True)
        self.btn_fijar.clicked.connect(self._aceptar)
        self.btn_fijar.setEnabled(False)
        btn_layout.addWidget(self.btn_fijar)

        layout.addLayout(btn_layout)
        self.txt_tasa.setFocus()

    # Habilita el boton solo si el texto se lee como Decimal > 0.
    def _actualizar_estado(self) -> None:
        """Habilita el boton solo si el texto se lee como Decimal > 0."""
        self._tasa_valor = parsear_decimal_escrito(self.txt_tasa.text())
        valido = self._tasa_valor is not None and self._tasa_valor > 0
        self.btn_fijar.setEnabled(valido)
        if self._tasa_valor is not None and self._tasa_valor <= 0:
            self.lbl_error.setText("La tasa debe ser mayor a cero.")
        else:
            self.lbl_error.setText("")

    # Cierra con exito guardando la tasa leida.
    def _aceptar(self) -> None:
        """Cierra con exito guardando la tasa leida."""
        if self._tasa_valor is not None and self._tasa_valor > 0:
            self.accept()

    # Tasa manual leida (Decimal valido > 0 si el dialogo fue aceptado).
    def tasa(self) -> Decimal:
        """Tasa manual leida (Decimal valido > 0 si el dialogo fue aceptado)."""
        return self._tasa_valor or Decimal("0.00")

