from PyQt6.QtWidgets import QAbstractItemView, QTableWidget


class TablaProductos(QTableWidget):
    """Tabla reutilizable con configuracion base para todo el sistema."""

    def __init__(
        self,
        columnas: list[tuple[str, int]],
        padre: QTableWidget | None = None,
    ) -> None:
        super().__init__(padre)
        self._columnas = columnas
        self.setColumnCount(len(columnas))
        self.setHorizontalHeaderLabels([c[0] for c in columnas])
        for i, (_, ancho) in enumerate(columnas):
            self.setColumnWidth(i, ancho)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]

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
