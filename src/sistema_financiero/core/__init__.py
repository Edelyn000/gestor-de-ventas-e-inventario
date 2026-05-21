# ============================================================
# PAQUETE: core/
# LOGICA DE NEGOCIO — CAPA INTERMEDIA
# Aqui va toda la logica pura de la aplicacion: calculos,
# validaciones, reglas de negocio. NO debe depender de la UI
# ni de la BD directamente.
#
# Contenido del paquete:
#   auth_service.py         → autenticacion (login, bcrypt)
#   producto_controller.py  → CRUD de productos, categorias
#   venta_controller.py     → registro de ventas, totales, facturacion
#   inventario_service.py   → ajustes de stock, alertas, movimientos
#   reporte_service.py      → generar reportes diarios, consolidar ventas
#   tasa_cambio_service.py  → gestion de tasas de cambio
# ============================================================

# Exportamos AuthService para que se pueda importar desde cualquier
# parte del proyecto:
#
#   from sistema_financiero.core import AuthService
#   auth = AuthService()
#
# En lugar de:
#   from sistema_financiero.core.auth_service import AuthService
#
# El __init__.py ahorra escribir el nombre del modulo cada vez.
from .auth_service import AuthService
from .inventario_service import InventarioService
from .producto_controller import ProductoController
from .reporte_service import ReporteService
from .tasa_cambio_service import TasaCambioService
from .venta_controller import VentaController

__all__ = [
    "AuthService",
    "InventarioService",
    "ProductoController",
    "ReporteService",
    "TasaCambioService",
    "VentaController",
]
