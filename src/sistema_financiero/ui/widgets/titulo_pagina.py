# ============ TITULO DE PANTALLA REUTILIZABLE ============
# Tarjeta de titulo para las paginas (Dashboard, Ventas, Productos,
# Inventario, Reportes, Usuarios): fondo blanco, barra vertical
# izquierda de 5px (#2563eb), esquinas redondeadas solo a la derecha
# y texto azul oscuro (#1e3a8a).
#
# El estilo visual vive en ui/estilos.py (rol "titulo_pagina"):
#   QFrame[rol="titulo_pagina"] { ... }
#   QFrame[rol="titulo_pagina"] QLabel { ... }
# Aqui solo se monta la estructura (QFrame + QLabel con fuente 24pt).
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel


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
