# ============================================================
# PAQUETE: models/
# Exporta todos los modelos ORM y utilidades de conexion.
# Importar desde aqui: from .models import Producto, get_session
# ============================================================

from .conexion import create_db_and_tables, engine, get_session, obtener_sesion
from .modelos import (
    MovimientoInventario,
    Producto,
    ReporteDiario,
    TasaCambio,
    Usuario,
    Venta,
    VentaDetalle,
)

__all__ = [
    "create_db_and_tables",
    "engine",
    "get_session",
    "obtener_sesion",
    "MovimientoInventario",
    "Producto",
    "ReporteDiario",
    "TasaCambio",
    "Usuario",
    "Venta",
    "VentaDetalle",
]
