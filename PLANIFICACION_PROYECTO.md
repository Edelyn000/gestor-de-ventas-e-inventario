# Plan de proyecto

MVP terminado. 522 tests, CI/CD activo, mypy y ruff limpios.

## 1. Resumen

Gestión financiera e inventario para un abasto. PyQt6, SQLModel y SQLite, dos monedas por venta (VES y USD).

## 2. Requisitos funcionales

| ID | Módulo | Qué hace | Estado |
|---|---|---|---|
| RF-01 | Productos | CRUD, precios USD con equivalente Bs., stock, categorías, alertas | Hecho |
| RF-02 | Ventas | POS con pago mixto, factura, anulación auditada | Hecho |
| RF-03 | Inventario | Entrada, salida, ajuste e historial de stock | Hecho |
| RF-04 | Tasas de cambio | BCV automático, tasa manual, historial por origen | Hecho |
| RF-05 | Usuarios | Login bcrypt, CRUD, activar y desactivar | Hecho |
| RF-06 | Reportes | Cierre diario con rentabilidad, exportación a Excel | Hecho |
| RF-07 | Dashboard | Tarjetas del día, alertas de stock, tasa BCV | Hecho |

## 3. Requisitos no funcionales

| ID | Qué | Estado |
|---|---|---|
| RNF-01 | Interfaz PyQt6 usable a 1024x680 | Hecho |
| RNF-02 | Integridad referencial en SQLite | Hecho |
| RNF-03 | Contraseñas hasheadas con bcrypt en `core/` | Hecho |
| RNF-04 | Exportación a Excel con openpyxl vía `ReporteService` | Hecho |
| RNF-05 | Consulta de la tasa BCV sin bloquear la interfaz | Hecho |
| RNF-06 | Sesión por usuario, sin multi-tenant | Hecho |
| RNF-07 | CI con GitHub Actions (ruff, mypy, pytest, coverage) | Hecho |
| RNF-08 | Esquema versionado con Alembic | Hecho |
| RNF-09 | 522 tests en 4 niveles con markers de pytest: 280 unitarias, 211 de integración, 31 de sistema y 32 de aceptación (estas últimas solapan con las anteriores) | Hecho |

## 4. Capas

| Capa | Ubicación | Responsabilidad |
|---|---|---|
| Entrypoint | `__main__.py` | QApplication, BD, seed de admin, login, bucle de sesiones |
| UI | `ui/` | 6 páginas, 6 diálogos, 6 widgets reutilizables |
| Core | `core/` | Servicios y controladores con las reglas de negocio |
| Servicios | `services/` | BCV y fachada de exportación |
| Modelos | `models/` | 11 tablas SQLModel, engine y sesión |
| DB | `db/` | Alembic, seeds y scripts de datos |
| Utils | `utils/` | Moneda, fecha, validación, constantes, logging |

La UI llama a `core/` y nunca al revés. No existe capa `modules/`: la documentación anterior la mencionaba, pero nunca se creó.

El conteo de la capa UI sigue una convención: las **6 páginas** son las de
navegación por rol (`dashboard`, `productos`, `ventas`, `inventario`,
`reportes`, `usuarios`), los **6 diálogos** son las ventanas modales
(`dialogo_factura`, `dialogo_anulacion`, `dialogo_tasa_manual`,
`formulario_venta`, `formulario_producto`, `formulario_cambio_contrasena`) y
los **6 widgets** son los componentes de `ui/widgets/`. Además de eso, `ui/`
tiene `ventana_login.py` y `estilos.py`, que no cuentan en ninguna de las tres
categorías porque no son páginas, diálogos ni widgets.

## 5. Decisiones técnicas

### ADR-001: SQLite con `check_same_thread=False`

PyQt6 corre en el hilo principal y abre sesiones cortas por operación. PostgreSQL sobraría para una app de escritorio local y un JSON plano perdería la integridad referencial.

### ADR-002: Validación en `core/`, sin `CheckConstraint`

El proyecto no usa restricciones CHECK en el esquema. Los valores válidos de método de pago, moneda, estado y tipo de movimiento los valida el servicio y las pruebas cubren esas ramas. La base de datos se queda como contenedor de datos.

Consecuencia: una escritura que no pase por `core/` puede dejar un valor raro en la tabla.

### ADR-003: Snapshot del costo en `VentaDetalle`

Cada línea guarda el costo de compra del momento. El reporte diario suma ese snapshot, no el precio actual del producto, para que corregir el costo hoy no reescriba la utilidad de una venta vieja.

### ADR-004: Día de negocio en hora local de Venezuela

La BD guarda todo en UTC y el "hoy" del cajero es el día local de Venezuela. `rango_dia_utc()` traduce. Sin esto, una venta de las 23:50 aparecía en el reporte del día siguiente.

### ADR-005: Tasa BCV y tasa manual separadas por origen

`tasacambio` tiene columna `origen` con restricción única de `(fecha, origen)`. La tasa manual del POS nunca pisa la oficial: dashboard, reportes y arqueo filtran por `origen='BCV'`.

## 6. Tecnologías

| Tecnología | Versión | Para qué |
|---|---|---|
| Python | >=3.14 | Lenguaje |
| PyQt6 | >=6.11 | GUI |
| SQLModel | >=0.0.38 | ORM con tipado |
| SQLite | | BD local |
| openpyxl | >=3.1 | Excel |
| scraper-bcv | >=0.1 | Tasa BCV |
| bcrypt | >=5.0 | Contraseñas |
| alembic | >=1.18 | Migraciones |
| ruff | >=0.11 | Lint |
| mypy | >=1.15 | Tipos |
| pytest | >=9.0 | Tests |
| pytest-qt | >=4.5 | Tests de UI |

`pyqtgraph` y `fpdf2` están declaradas en `pyproject.toml` pero ninguna tiene uso en `src/`. El Dashboard usa tarjetas y tablas, no gráficos.

## 7. Riesgos

| Riesgo | Impacto | Mitigación | Estado |
|---|---|---|---|
| SQLite no aguanta concurrencia real | Medio | Sesiones cortas por operación | Mitigado |
| La contraseña vive como string en el schema | Alto | bcrypt antes de persistir, en `core/` | Mitigado |
| Sin tests | Medio | 522 tests con marker por nivel | Mitigado |
| Sin CI | Bajo | GitHub Actions con lint, tipos y cobertura | Mitigado |
| Esquema sin migraciones | Bajo | Alembic en head `a2b3c4d5e6f7` | Mitigado |
| Tasa BCV inaccesible sin red | Medio | Tasa manual en el POS y reintento cada 10 minutos | Mitigado |

## 8. Fases

| Fase | Qué | Estado |
|---|---|---|
| 1 | Entrypoint, login y conexión | Completada |
| 2 | CRUD de productos con UI | Completada |
| 3 | POS y detalle de venta | Completada |
| 4 | Inventario y movimientos | Completada |
| 5 | Tasas de cambio y reporte diario | Completada |
| 6 | Dashboard y alertas | Completada |
| 7 | Exportación a Excel | Completada |
| 8 | Caja, factura, anulación, rentabilidad, CI y documentación | Completada |
| 9 | Entregables documentales: contexto, DFD, procesos, actores, diccionario, E-R, datos, entradas/salidas, minutas y presentación | Completada |

## 9. Entregables

Los 45 archivos de `presentacion/` están ordenados en 10 carpetas por nivel de abstracción:

| Carpeta | Archivos | Contenido |
|---|---|---|
| `00-contexto/` | 1 | Contexto del sistema |
| `01-dfd/` | 8 | DFD nivel 1 y 7 procesos de nivel 2 |
| `02-procesos/` | 8 | Flujos de proceso P0 a P7 |
| `03-actores/` | 5 | Actores e interactores AL_D1 a AL_D5 |
| `04-diccionario/` | 4 | Detalle de datos DD_ER_1 a DD_ER_4 |
| `05-entidad-relacion/` | 2 | Diagrama E-R y su fuente `.dot` |
| `06-datos/` | 6 | Flujos de datos FD_FD1 a FD_FD6 |
| `07-entradas-salidas/` | 9 | Interacción actor-sistema y capturas de la UI |
| `08-minutas/` | 1 | Acta firmada de la reunión |
| `09-presentacion/` | 1 | Presentación final |

Ninguno es código: `src/` no depende de `presentacion/`.