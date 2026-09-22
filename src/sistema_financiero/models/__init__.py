# ============================================================
# PAQUETE: models/
# Exporta todos los modelos ORM y utilidades de conexion.
# Importar desde aqui: from .models import Producto
# ============================================================

from .conexion import create_db_and_tables, engine, obtener_sesion
from .modelos import (
    Caja,
    MovimientoInventario,
    PagoVenta,
    Producto,
    ReporteDiario,
    TasaCambio,
    Usuario,
    Venta,
    VentaDetalle,
)

__all__ = [
    "Caja",
    "create_db_and_tables",
    "engine",
    "obtener_sesion",
    "MovimientoInventario",
    "PagoVenta",
    "Producto",
    "ReporteDiario",
    "TasaCambio",
    "Usuario",
    "Venta",
    "VentaDetalle",
]
