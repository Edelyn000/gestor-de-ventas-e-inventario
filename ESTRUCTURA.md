# Estructura del Proyecto — Sistema Finaciero

```
sistema_finacieron/
├── src/
│   └── sistema_financiero/
│       ├── __init__.py          ← Inicializador del paquete
│       ├── __main__.py          ← Entrypoint de la aplicación
│       ├── core/                ← Lógica de negocio
│       ├── models/              ← Capa de datos (ORM)
│       ├── ui/                  ← Vistas PyQt6
│       │   └── widgets/         ← Componentes reutilizables de UI
│       ├── modules/             ← Módulos funcionales
│       ├── services/            ← Servicios de integración
│       └── db/                  ← Migraciones y seeds
├── database/                    ← Archivo SQLite (se crea automáticamente)
└── ...
```

## Descripción por carpeta

### `core/` — Lógica de negocio

Acá va toda la lógica pura de la aplicación: cálculos, validaciones, reglas de negocio. No debe depender de la UI ni de la base de datos directamente. Ejemplos:

- `AuthService` → autenticación de usuarios (login, verificación de contraseñas con bcrypt)
- `VentaController` → cálculo de totales, validación de productos antes de facturar
- `InventarioService` → actualizar stock, registrar movimientos, alertas de stock bajo
- `ReporteService` → generar reportes diarios, consolidar ventas

### `models/` — Capa de datos (ORM)

Contiene los modelos SQLModel que definen las tablas de la base de datos. También va la configuración del engine y la sesión. Archivos:

- `modelos.py` → Definición de tablas: `Producto`, `Venta`, `VentaDetalle`, `MovimientoInventario`, `TasaCambio`, `Usuario`, `ReporteDiario`
- `conexion.py` → Engine de SQLAlchemy, creación de la DB (`abasto.db`), `get_session()`

### `ui/` — Vistas PyQt6

Acá van las ventanas, diálogos y componentes visuales de la interfaz. Separado en:

- **`ui/__init__.py`** + **`ui/interflaz.py`** → ventanas principales, layouts, navegación
- **`ui/widgets/`** → componentes reutilizables (ej: tabla de productos personalizada, selector de fecha, campo de búsqueda)
- No debe contener lógica de negocio directamente — solo llama a `core/`

### `modules/` — Módulos funcionales

Aquí van las funcionalidades agrupadas por dominio. Cada módulo puede contener su propio subconjunto de lógica. Ejemplos:

- `modules/ventas/` → pantalla de registro de ventas, historial
- `modules/productos/` → CRUD de productos, gestión de categorías
- `modules/reportes/` → generación y visualización de reportes
- `modules/usuarios/` → gestión de usuarios y roles

### `services/` — Servicios de integración

Acá van los servicios que se conectan con APIs externas o realizan tareas auxiliares:

- `services/tasa_bcv.py` → consultar la tasa de cambio del BCV vía scraper-bcv
- `services/exportar_excel.py` → exportar reportes a Excel con openpyxl

### `db/` — Acceso y configuración de base de datos

Capa específica para operaciones de base de datos: migraciones, seeds, consultas complejas que no están en los modelos:

- Migraciones con Alembic
- Scripts para poblar datos de prueba (seeds)
- Consultas personalizadas que no encajan en SQLModel puro

## Flujo de llamadas

```
__main__.py
    ↓
ui/  ←→  core/  ←→  models/  ←→  db/
              ↑
         services/
```
