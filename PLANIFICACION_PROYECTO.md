# Plan de Proyecto — Sistema Finacieron

## 1. Resumen del Proyecto

Sistema de gestión financiera y de inventario para un abasto. Sobre PyQt6 + SQLModel + SQLite, con doble moneda (VES/USD).

**Objetivo:** Entregar un MVP funcional con módulos de productos, ventas, inventario, tasas de cambio, usuarios y reportes diarios.

## 2. Requisitos Funcionales

| ID | Módulo | Descripción |
|----|--------|-------------|
| RF-01 | **Productos** | CRUD de productos con precios en VES/USD, stock, categorías |
| RF-02 | **Ventas** | Registro de ventas con múltiples formas de pago, facturación |
| RF-03 | **Inventario** | Control de stock, movimientos (entrada/salida/ajuste), alertas de stock bajo |
| RF-04 | **Tasas de Cambio** | Registro y consulta de tasas BCV (VES/USD) |
| RF-05 | **Usuarios** | Login seguro, gestión de usuarios con bcrypt |
| RF-06 | **Reportes** | Reporte diario de cierre con totales por método de pago |
| RF-07 | **Dashboard** | Vista principal con indicadores y alertas en tiempo real |

## 3. Requisitos No Funcionales

| ID | Descripción |
|----|-------------|
| RNF-01 | Interfaz responsive con PyQt6 |
| RNF-02 | Base de datos local SQLite con integridad referencial |
| RNF-03 | Contraseñas hasheadas con bcrypt |
| RNF-04 | Exportación a Excel con openpyxl |
| RNF-05 | Consulta automática de tasas BCV vía scraper-bcv |
| RNF-06 | Sesión por usuario, sin multi-tenant |

## 4. Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────┐
│                    __main__.py                       │
│         Entrypoint (QApplication + Login)            │
├─────────────────────────────────────────────────────┤
│                   src/ui/                            │
│    VentanaPrincipal │ ProductosView │ VentasView     │
│    InventarioView │ ReportesView │ LoginDialog       │
├─────────────────────────────────────────────────────┤
│                   src/core/                          │
│     ProductoController │ VentaController             │
│     InventarioService │ ReporteService               │
│     AuthService │ TasaCambioService                  │
├─────────────────────────────────────────────────────┤
│                 src/models/                          │
│    Producto │ Venta │ VentaDetalle │ MovInventario  │
│    TasaCambio │ Usuario │ ReporteDiario             │
├─────────────────────────────────────────────────────┤
│              SQLite (abasto.db)                      │
└─────────────────────────────────────────────────────┘
```

### Capas

| Capa | Rol |
|------|-----|
| `__main__.py` | Inicializa QApplication, DB, muestra login y ventana principal |
| `src/ui/` | Widgets PyQt6 (vistas, diálogos, tablas, gráficos) |
| `src/core/` | Lógica de negocio: controladores/servicios con validación |
| `src/models/` | ORM SQLModel + engine (completos) |
| `src/utils/` | Helpers: exportación Excel, integración BCV, formateo |

## 5. Decisión Técnica (ADR)

### ADR-001: SQLite con check_same_thread=False

- **Contexto:** PyQt6 corre en el hilo principal y accede a la DB desde la UI.
- **Decisión:** SQLite local con `check_same_thread=False` y una única sesión por operación.
- **Alternativas:** PostgreSQL (overkill para app local de escritorio), JSON plano (sin integridad).
- **Consecuencias:** + simplicidad, - sin concurrencia real.

### ADR-002: SQLModel con restricciones CHECK en la DB

- **Contexto:** Los montos no pueden ser negativos, el estado de venta debe ser ENUM-like.
- **Decisión:** Se usan `CheckConstraint` a nivel DB para garantizar integridad.
- **Alternativas:** Validación solo en capa core (menos seguro), triggers (más complejo).

## 6. Tecnologías

| Tecnología | Versión | Propósito |
|------------|---------|-----------|
| Python | >=3.14 | Lenguaje base |
| PyQt6 | >=6.11 | GUI de escritorio |
| SQLModel | >=0.0.38 | ORM con tipado |
| SQLite | — | Base de datos embebida |
| pyqtgraph | >=0.14 | Gráficos y dashboards |
| openpyxl | >=3.1 | Exportación Excel |
| scraper-bcv | >=0.1 | Tasas BCV automáticas |
| bcrypt | >=5.0 | Hashing de contraseñas |
| alembic | >=1.18 | Migraciones futuras |

## 7. Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|-----------|
| SQLite sin concurrencia multi-hilo | Medio | Envolver accesos DB en transacciones cortas |
| Contraseñas en texto plano en schema | Alto | Aplicar bcrypt en capa core antes de persistir |
| Falta de .gitignore | Bajo | Ignorar __pycache__, *.db, *.pyc |
| Sin tests escritos | Medio | Escribir tests por cada módulo completado |
| Sin CI/CD | Bajo | Configurar GitHub Actions con pytest + coverage |

## 8. Cronograma Tentativo

| Fase | Actividades | Duración estimada |
|------|------------|-------------------|
| **Fase 1** | Entrypoint + Login + Conexión DB | 1 semana |
| **Fase 2** | CRUD Productos + UI | 1 semana |
| **Fase 3** | Módulo Ventas + Detalle | 1.5 semanas |
| **Fase 4** | Inventario + Movimientos | 1 semana |
| **Fase 5** | Tasas de Cambio + Reporte Diario | 1 semana |
| **Fase 6** | Dashboard + Gráficos (pyqtgraph) | 1 semana |
| **Fase 7** | Exportación Excel + Puli | 0.5 semanas |
| **Fase 8** | Tests + CI + Documentación | 1 semana |

**Total estimado: ~8 semanas**
