from PyQt6.QtWidgets import QLineEdit


# CampoBusqueda: Campo de busqueda de texto en vivo.
class CampoBusqueda(QLineEdit):
    """Campo de busqueda con placeholder y filtro en tiempo real."""

    def __init__(self, placeholder: str = "Buscar...") -> None:
        super().__init__()
        self.setPlaceholderText(placeholder)

