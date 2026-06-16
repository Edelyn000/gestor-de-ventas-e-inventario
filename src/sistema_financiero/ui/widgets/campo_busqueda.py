from PyQt6.QtWidgets import QLineEdit


class CampoBusqueda(QLineEdit):
    """Campo de busqueda con placeholder y filtro en tiempo real."""

    def __init__(self, placeholder: str = "Buscar...") -> None:
        super().__init__()
        self.setPlaceholderText(placeholder)
