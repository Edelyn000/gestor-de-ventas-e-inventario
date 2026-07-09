# ============ CAMPO DE BUSQUEDA REUTILIZABLE ============
# --- NO TOCAR: clase base y constructor.
# --- MODIFICABLE: placeholder por defecto, estilos si se agregan.
from PyQt6.QtWidgets import QLineEdit


class CampoBusqueda(QLineEdit):
    """Campo de busqueda con placeholder y filtro en tiempo real."""

    # --- MODIFICABLE: texto del placeholder por defecto.
    def __init__(self, placeholder: str = "Buscar...") -> None:
        super().__init__()
        self.setPlaceholderText(placeholder)
