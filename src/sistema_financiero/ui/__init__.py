# ============================================================
# PAQUETE: ui/
# Vistas y componentes visuales PyQt6.
# Aqui van las ventanas, dialogos y widgets de la interfaz.
# NO debe contener logica de negocio — solo llama a core/.
#
# Archivos:
#   interfaz.py           → VentanaPrincipal (ventana principal con paginas)
#   ventana_login.py      → VentanaLogin (inicio de sesion)
#   formulario_producto.py → FormularioProducto (crear/editar productos)
#   formulario_venta.py   → FormularioVenta (registrar ventas)
#   dashboard_pagina.py   → DashboardPagina (resumen, graficos)
#   productos_pagina.py   → ProductosPagina (CRUD productos)
#   ventas_pagina.py      → VentasPagina (historial ventas)
#   inventario_pagina.py  → InventarioPagina (movimientos stock)
#   reportes_pagina.py    → ReportesPagina (cierre diario, exportar)
#
# Paginas independientes que se insertan en VentanaPrincipal -> QStackedWidget.
# ============================================================
