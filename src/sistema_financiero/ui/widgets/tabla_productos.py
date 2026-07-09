# ============ TABLA DE PRODUCTOS REUTILIZABLE ============
# --- NO TOCAR: clase, metodos auxiliares (item_texto, id_fila_seleccionada).
# --- MODIFICABLE: configuracion visual de la tabla (seleccion, edicion, header).
from PyQt6.QtWidgets import QAbstractItemView, QTableWidget, QWidget


class TablaProductos(QTableWidget):
    """Tabla reutilizable con configuracion base para todo el sistema."""

    # --- NO TOCAR: firma del constructor.
    def __init__(
        self,
        columnas: list[tuple[str, int]],
        padre: QWidget | None = None,
    ) -> None:
        super().__init__(padre)
        self._columnas = columnas
        # --- MODIFICABLE: configuracion de columnas (nombres, anchos).
        self.setColumnCount(len(columnas))
        self.setHorizontalHeaderLabels([c[0] for c in columnas])
        for i, (_, ancho) in enumerate(columnas):
            self.setColumnWidth(i, ancho)
        # --- MODIFICABLE: comportamiento de seleccion y edicion.
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.horizontalHeader()
        if header:
            header.setStretchLastSection(True)

    # --- NO TOCAR: metodos auxiliares para extraer datos de la tabla.
    def item_texto(self, fila: int, col: int) -> str:
        item = self.item(fila, col)
        return item.text() if item else ""

    def id_fila_seleccionada(self, col_id: int = 0) -> int | None:
        fila = self.currentRow()
        if fila < 0:
            return None
        item = self.item(fila, col_id)
        if item is None:
            return None
        try:
            return int(item.text())
        except ValueError:
            return None
