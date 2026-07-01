# Plan de Proyecto — Sistema Finacieron

> **Estado actual:** ✅ MVP COMPLETO (v1.0). 172 tests, CI/CD activo, código 100% tipado.

## 1. Resumen del Proyecto

Sistema de gestión financiera y de inventario para un abasto. PyQt6 + SQLModel + SQLite, doble moneda (VES/USD).

**Logrado:** Módulos de productos, ventas, inventario, tasas de cambio, usuarios, reportes diarios y dashboard con gráficos en tiempo real.

## 2. Requisitos Funcionales

| ID | Módulo | Descripción | Estado |
|----|--------|-------------|--------|
| RF-01 | **Productos** | CRUD con precios VES/USD, stock, categorías, alertas | ✅ |
| RF-02 | **Ventas** | Registro multi-forma de pago, facturación (`formulario_venta.py`) | ✅ |
| RF-03 | **Inventario** | Stock, movimientos (entrada/salida/ajuste), alertas stock bajo | ✅ |
| RF-04 | **Tasas de Cambio** | BCV automático + manual, historial | ✅ |
| RF-05 | **Usuarios** | Login bcrypt, CRUD, cambiar contraseña | ✅ |
| RF-06 | **Reportes** | Cierre diario, totales por método de pago, exportar Excel | ✅ |
| RF-07 | **Dashboard** | Tarjetas resumen, gráficos pyqtgraph (líneas + barras), stock bajo | ✅ |

## 3. Requisitos No Funcionales

| ID | Descripción | Estado |
|----|-------------|--------|
| RNF-01 | Interfaz responsive con PyQt6 | ✅ |
| RNF-02 | SQLite con integridad referencial + check constraints | ✅ |
| RNF-03 | Contraseñas hasheadas con bcrypt en capa core | ✅ |
| RNF-04 | Exportación a Excel con openpyxl (vía `ReporteService`) | ✅ |
| RNF-05 | Consulta automática de tasas BCV vía scraper-bcv | ✅ |
| RNF-06 | Sesión por usuario, sin multi-tenant | ✅ |
| RNF-07 | CI/CD con GitHub Actions (lint + test + coverage) | ✅ |
| RNF-08 | Migraciones con Alembic (1 migración inicial + seeds) | ✅ |
| RNF-09 | Cobertura de tests: 172 tests (unitarios + UI con pytest-qt) | ✅ |

## 4. Arquitectura del Sistema

```
┌──────────────────────────────────────────────────────────┐
│                    __main__.py                            │
│   Entrypoint (QApplication → VentanaLogin → VentanaPrincipal) │
├──────────────────────────────────────────────────────────┤
│                      src/ui/                              │
│  VentanaPrincipal (QTabWidget)                            │
│  ├─ DashboardPagina     (tarjetas + 2 gráficos pyqtgraph) │
│  ├─ ProductosPagina     (CRUD + tabla)                    │
│  ├─ VentasPagina        (historial ventas)                │
│  ├─ InventarioPagina    (movimientos stock)               │
│  └─ ReportesPagina      (cierre diario + Excel)           │
│                                                           │
│  Diálogos:                                                │
│  └─ VentanaLogin │ FormularioProducto │ FormularioVenta   │
│     FormularioCambioContrasena                             │
│                                                           │
│  Widgets reutilizables:                                   │
│  └─ TablaProductos │ SelectorFecha │ IndicadorStock       │
│     CampoBusqueda                                          │
├──────────────────────────────────────────────────────────┤
│                   src/modules/                             │
│  Fachadas por dominio (productos/, ventas/, inventario/,  │
│  reportes/, usuarios/)                                    │
├──────────────────────────────────────────────────────────┤
│                    src/core/                               │
│  auth_service │ inventario_service │ producto_controller  │
│  reporte_service │ tasa_cambio_service │ venta_controller │
├──────────────────────────────────────────────────────────┤
│                   src/services/                            │
│  bcv.py  (scraper-bcv wrapper)                            │
│  exportar_excel.py  (fachada → ReporteService)            │
├──────────────────────────────────────────────────────────┤
│                    src/models/                             │
│  Producto │ Venta │ VentaDetalle │ MovimientoInventario   │
│  TasaCambio │ Usuario │ ReporteDiario                     │
├──────────────────────────────────────────────────────────┤
│                    src/db/                                 │
│  Alembic (alembic/, alembic.ini)                          │
│  seeds (seed_admin, seed_productos, seed_tasa_cambio)     │
├──────────────────────────────────────────────────────────┤
│                    src/utils/                              │
│  formateo moneda, validación, constantes                  │
├──────────────────────────────────────────────────────────┤
│              SQLite (database/database.db)                 │
└──────────────────────────────────────────────────────────┘
```

### Capas

| Capa | Rol |
|------|-----|
| `__main__.py` | Inicializa QApplication, DB, seed admin, login → ventana principal |
| `src/ui/` | Widgets PyQt6 (7 vistas + 4 diálogos + 4 widgets reutilizables) |
| `src/modules/` | Fachadas por dominio que conectan UI con core |
| `src/core/` | Lógica de negocio: controladores/servicios con validación (~1773 líneas) |
| `src/services/` | Servicios externos: BCV, exportación Excel |
| `src/models/` | ORM SQLModel + engine (7 tablas, check constraints) |
| `src/db/` | Migraciones Alembic + seeds datos iniciales |
| `src/utils/` | Helpers: formateo moneda, validación, constantes |

## 5. Decisión Técnica (ADR)

### ADR-001: SQLite con check_same_thread=False

- **Contexto:** PyQt6 corre en el hilo principal y accede a la DB desde la UI.
- **Decisión:** SQLite local con `check_same_thread=False` y sesiones cortas por operación.
- **Alternativas:** PostgreSQL (overkill para escritorio local), JSON plano (sin integridad).
- **Consecuencias:** + simplicidad, - sin concurrencia real.

### ADR-002: SQLModel con restricciones CHECK en la DB

- **Contexto:** Los montos no pueden ser negativos, estado de venta ENUM-like.
- **Decisión:** `CheckConstraint` a nivel DB + validación en core.
- **Alternativas:** Solo validación en core (menos seguro), triggers (más complejo).

### ADR-003: Fachadas (modules/) entre UI y core

- **Contexto:** Separar la lógica de navegación/eventos Qt de la lógica de negocio pura.
- **Decisión:** Capa intermedia `modules/` que usa `core/` y expone métodos listos para conectar a señales Qt.
- **Consecuencias:** + separación limpia, + testabilidad del core sin Qt.

## 6. Tecnologías

| Tecnología | Versión | Propósito |
|------------|---------|-----------|
| Python | >=3.14 | Lenguaje base |
| PyQt6 | >=6.11 | GUI de escritorio |
| SQLModel | >=0.0.38 | ORM con tipado |
| SQLite | — | BD embebida (`database/database.db`) |
| pyqtgraph | >=0.14 | Gráficos (líneas + barras en dashboard) |
| openpyxl | >=3.1 | Exportación Excel |
| scraper-bcv | >=0.1 | Tasas BCV automáticas |
| bcrypt | >=5.0 | Hashing de contraseñas |
| alembic | >=1.18 | Migraciones |
| ruff | >=0.11 | Linter |
| mypy | >=1.15 | Type checker |
| pytest | >=8.3 | Tests |
| pytest-qt | >=4.4 | Tests de UI |

## 7. Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación | Estado |
|--------|---------|-----------|--------|
| SQLite sin concurrencia multi-hilo | Medio | Sesiones cortas por operación | ✅ Mitigado |
| Contraseñas en schema como string | Alto | bcrypt en capa core antes de persistir | ✅ Mitigado |
| Sin tests | Medio | 172 tests (unitarios + UI) | ✅ Mitigado |
| Sin CI/CD | Bajo | GitHub Actions configurado | ✅ Mitigado |
| Proyecto sin migraciones | Bajo | Alembic inicializado con migración base | ✅ Mitigado |

## 8. Estado Final del Proyecto

| Fase | Actividades | Estado |
|------|------------|--------|
| **Fase 1** | Entrypoint + Login + Conexión DB | ✅ COMPLETO |
| **Fase 2** | CRUD Productos + UI | ✅ COMPLETO |
| **Fase 3** | Módulo Ventas + Detalle | ✅ COMPLETO |
| **Fase 4** | Inventario + Movimientos | ✅ COMPLETO |
| **Fase 5** | Tasas de Cambio + Reporte Diario | ✅ COMPLETO |
| **Fase 6** | Dashboard + Gráficos (pyqtgraph) | ✅ COMPLETO |
| **Fase 7** | Exportación Excel + Pulido | ✅ COMPLETO |
| **Fase 8** | Tests + CI + Documentación | ✅ COMPLETO |

**Proyecto completado — MVP listo para uso en producción local.**
