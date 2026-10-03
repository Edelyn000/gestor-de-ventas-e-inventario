# Estructura del proyecto

```
sistema_finacieron/
├── src/sistema_financiero/
│   ├── __init__.py
│   ├── __main__.py          punto de entrada
│   ├── core/                lógica de negocio
│   ├── models/              ORM y conexión
│   ├── ui/                  vistas PyQt6
│   │   └── widgets/         componentes reutilizables
│   ├── services/            integraciones externas
│   ├── db/                  Alembic, seeds y scripts
│   └── utils/               formateo, validación, constantes
├── alembic/                 migraciones y `alembic.ini`
├── tests/                   pytest + pytest-qt
├── database/database.db     SQLite local
└── logs/                    bitácora de app, errores y eventos
```

## Responsabilidad por carpeta

### `core/`

Reglas de negocio. No importa PyQt6 ni toca la BD directamente.

| Módulo | Qué hace |
|---|---|
| `auth_service.py` | Login con bcrypt, CRUD de usuarios |
| `inventario_service.py` | Entrada, salida y ajuste de stock |
| `producto_controller.py` | CRUD de productos y categorías, alertas |
| `venta_controller.py` | Crear y anular ventas, pagos mixtos |
| `caja_service.py` | Apertura, arqueo y cierre de caja |
| `reporte_service.py` | Reporte diario y exportación a Excel |
| `tasa_cambio_service.py` | Tasas BCV y manuales, historial |
| `rentabilidad.py` | Costo de ventas, utilidad bruta y margen (funciones puras) |

### `models/`

Los modelos SQLModel que definen las 11 tablas, el engine y la sesión.

- `modelos.py`: `Producto`, `Categoria`, `Venta`, `VentaDetalle`, `PagoVenta`, `MovimientoInventario`, `TasaCambio`, `Usuario`, `Caja`, `ReporteDiario`, `ReporteVentaDetalle`
- `conexion.py`: engine de SQLAlchemy, `obtener_sesion()`, `create_db_and_tables()`

SQLModel deriva el nombre de tabla del nombre de la clase en minúsculas, así que `VentaDetalle` crea `ventadetalle` y `ReporteVentaDetalle` crea `reporteventadetalle`. La base real conserva además `reporte_venta_detalle`, una tabla de 0 filas que creó una migración anterior con el nombre en snake_case.

### `ui/`

Ventanas, diálogos y componentes. Un page llama a `core/`, nunca al revés.

| Archivo | Qué hace |
|---|---|
| `interfaz.py` | Ventana principal, menú lateral por rol, cabecera con "Cerrar Sesion" |
| `ventana_login.py` | Inicio de sesión |
| `dashboard_pagina.py` | Resumen del día, alertas de stock, tasa BCV |
| `productos_pagina.py` | CRUD de productos y pestaña de movimientos |
| `ventas_pagina.py` | Historial de ventas y panel "Caja del Turno" |
| `inventario_pagina.py` | Entrada, salida, ajuste e historial de stock |
| `reportes_pagina.py` | Cierre del día y exportación |
| `usuarios_pagina.py` | Perfil, cambio de contraseña y gestión de usuarios |
| `formulario_venta.py` | POS: catálogo, ticket, cobro mixto, factura |
| `formulario_producto.py` | Alta y edición de productos |
| `dialogo_factura.py` | Vista previa, impresión y PDF de la factura |
| `dialogo_anulacion.py` | Anulación con motivo y doble autorización |
| `dialogo_tasa_manual.py` | Fijar tasa a mano cuando no hay BCV |
| `estilos.py` | QSS centralizado y paleta |

`ui/widgets/` tiene los componentes reutilizables: `TablaProductos`, `SelectorFecha`, `IndicadorStock`, `CampoBusqueda`, `TituloPagina`, `SpinBoxStock`.

### `services/`

Wrappers de terceros.

- `bcv.py`: consulta la tasa al BCV y distingue red caída de error interno
- `exportar_excel.py`: fachada hacia `ReporteService`

### `db/`

Seeds y scripts de datos. Las migraciones viven en `alembic/` en la raíz, no aquí.

- `seeds.py`: `seed_admin`, `seed_productos`, `seed_tasa_cambio`
- `scripts/`: scripts de migración de datos que no entran en `core/`

### `utils/`

Funciones sin estado: `moneda.py` (formateo), `fecha.py` (UTC y día local VET), `validacion.py`, `constantes.py`, `texto.py`, `logging_setup.py`.

## Flujo de llamadas

```
__main__.py
    ↓
ui/  →  core/  →  models/  →  SQLite
          ↓
      services/  →  BCV, Excel
```