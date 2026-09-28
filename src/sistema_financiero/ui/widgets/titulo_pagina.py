from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel


# TituloPagina: Titulo de pagina con barra lateral de acento.
class TituloPagina(QFrame):
    """Etiqueta de titulo con barra de acento lateral (reutilizable)."""

    def __init__(self, texto: str) -> None:
        super().__init__()
        self.setProperty("rol", "titulo_pagina")
        self.setObjectName("titulo_pagina")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(0)

        etiqueta = QLabel(texto)
        fuente = QFont()
        fuente.setPointSize(24)
        fuente.setBold(True)
        etiqueta.setFont(fuente)
        layout.addWidget(etiqueta)

