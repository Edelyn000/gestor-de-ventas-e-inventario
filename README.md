# Gestor de Ventas e Inventario

Sistema de escritorio para gestionar las ventas, el inventario, la caja y los
reportes de un abasto, con precios simultáneos en bolívares (Bs) y dólares (USD).

**Autora:** Edelyn Hernandez · edelinhernandezolano@hotmail.com

![Python](https://img.shields.io/badge/python-%3E%3D3.14-3776AB)
![PyQt6](https://img.shields.io/badge/PyQt6-6.11-2c6fbb)
![SQLModel](https://img.shields.io/badge/SQLModel-0.0.38-2c6fbb)
![SQLite](https://img.shields.io/badge/SQLite-3-brightgreen)
![Tests](https://img.shields.io/badge/tests-522%20passing-success)
![Ruff](https://img.shields.io/badge/ruff-0%20errores-success)
![Mypy](https://img.shields.io/badge/mypy-0%20errores-success)

## Problema

Un abasto administra el precio de compra, el precio de venta, el stock y la caja
en papel. Eso genera tres problemas concretos:

- **El costo real de la venta no se conoce.** Solo queda el precio de venta, así
  que no se puede saber si un producto deja ganancia o se está vendiendo a
  pérdida.
- **El stock se descuadra.** Cada venta y cada ajuste modifican las existencias,
  pero sin un registro de auditoría nadie explica por qué el stock cambió.
- **El cierre del día no se puede justificar.** Sin arqueo de caja ni reporte
  diario, no hay forma de demostrar cuánto entró y cuánto quedó.

## Solución

Una aplicación de escritorio en Python que cubre el ciclo completo:

- **POS** con catálogo, ticket por peso o por unidad, cobro en un clic con
  métodos digitales, efectivo con vuelto en vivo y pago mixto entre métodos.
- **Inventario** con movimientos auditados (entrada, salida, ajuste) que guardan
  el stock anterior y el posterior de cada cambio.
- **Caja** con apertura, arqueo por billetes y cierre que descuenta el vuelto
  entregado.
- **Reportes diarios** con costo de ventas, utilidad bruta y margen de ganancia.
- **Tasa de cambio BCV** consultada en red, con tasa manual de respaldo cuando
  no hay conexión.

### Decisión de diseño: el costo es un snapshot

El costo de una venta se copia a la línea de detalle en el momento de cobrar
(`VentaDetalle.precio_costo_unitario`) y **nunca se relee del producto**. Si el
dueño corrige el precio de compra mañana, la venta de ayer sigue mostrando lo
que realmente costó. Además, un producto cuyo costo no sea creíble (no hay
costo, el costo supera el precio de venta, o es menos del 1 % del precio) se
marca como **no confiable** y el reporte avisa en vez de publicar un margen
inventado.

## Requisitos

- Python >= 3.14
- Poetry 2.x
- PyQt6 (interfaz gráfica)
- SQLModel + SQLite (persistencia, sin servidor externo)

## Instalación

```powershell
poetry install
```

## Ejecutar

```powershell
.\run.ps1
```

Equivale a `.venv\Scripts\python.exe -m sistema_financiero`.

## Tests, lint y tipos

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check src/ tests/ alembic/
.venv\Scripts\python.exe -m mypy src/
```

**Estado verificado:** 522 pruebas en verde, 0 errores de Ruff sobre `src/`,
`tests/` y `alembic/`, y 0 errores de mypy sobre 51 archivos de `src/`.

Las pruebas están marcadas por nivel y se pueden correr por separado:

```powershell
.venv\Scripts\python.exe -m pytest tests/ -m unitarias
.venv\Scripts\python.exe -m pytest tests/ -m integracion
.venv\Scripts\python.exe -m pytest tests/ -m sistema
.venv\Scripts\python.exe -m pytest tests/ -m aceptacion
```

| Nivel | Cuántas | Qué cubre |
|---|---|---|
| `unitarias` | 280 | Un módulo aislado, con el resto simulado |
| `integracion` | 211 | Servicio real sobre base de datos SQLite en memoria |
| `sistema` | 31 | Aplicación completa: login → POS → cobro → cierre, con controladores reales |
| `aceptacion` | 32 | Escenarios de negocio del POS vistos desde la interfaz |

Los cuatro niveles suman 554 porque `aceptacion` reutiliza pruebas que ya
cuentan como `sistema`. Son 522 pruebas clasificadas de más de una forma.

Las pruebas de interfaz usan `pytest-qt` y **nunca tocan la red**: el hilo que
consulta la tasa BCV se neutraliza con el fixture `_sin_fetch_bcv` en
`tests/test_ui.py` y `tests/test_sistema.py`.

## Arquitectura

```
src/sistema_financiero/
  __main__.py          Arranque: crea la BD, siembra el admin, login, bucle de sesión
  models/              Capa de datos (11 tablas SQLModel sobre SQLite)
  core/                Lógica de negocio (8 servicios)
  services/            Integración externa (BCV) y fachadas
  ui/                  Interfaz PyQt6 (páginas, formularios y diálogos)
  utils/               Moneda, fecha (UTC/Venezuela), validación, constantes
  db/                  Scripts de datos y semillas
alembic/               Migraciones de esquema
database/database.db   Base local en SQLite (no se versiona)
tests/                 522 pruebas (14 archivos)
```

Las dependencias apuntan hacia dentro: `ui/` llama a `core/`, `core/` a
`models/`, y nadie sube de nivel. `core/rentabilidad.py` es deliberadamente puro
(sin base de datos ni Qt) para que las reglas de margen se prueben solas.

## Matriz requisito → implementación → archivo → prueba

| Requisito | Implementación | Archivo | Pruebas |
|---|---|---|---|
| Autenticación y roles | bcrypt + verificación de credenciales | `core/auth_service.py` | `test_auth_service.py` (18) |
| Catálogo y categorías | CRUD con categorías normalizadas y reutilizadas | `core/producto_controller.py` | `test_producto_controller.py` (19) |
| POS y cobro | Ticket, pago mixto, vuelto en vivo | `ui/formulario_venta.py` | `test_ui.py::TestFormularioVenta` |
| Factura imprimible | Vista previa, impresión y PDF | `ui/dialogo_factura.py` | `test_ui.py::TestDialogoFactura` |
| Anulación auditada | Motivo + doble autorización de administrador | `ui/dialogo_anulacion.py` | `test_ui.py::TestDialogoAnulacion` |
| Inventario | Entrada, salida y ajuste con rastro de stock | `core/inventario_service.py` | `test_inventario_service.py` (17) |
| Caja y arqueo | Apertura, arqueo por billetes, cierre | `core/caja_service.py` | `test_caja_service.py` (12) |
| Tasa BCV | Consulta en red con respaldo manual | `core/tasa_cambio_service.py`, `services/bcv.py` | `test_tasa_cambio_service.py` (20), `test_bcv.py` (12) |
| Reporte diario | Unidades, peso, costo, utilidad y margen | `core/reporte_service.py` | `test_reporte_service.py` (14) |
| Rentabilidad | COGS, utilidad bruta y margen (módulo puro) | `core/rentabilidad.py` | `test_rentabilidad.py` (27) |
| Flujo completo | Login → venta → cierre con servicios reales | toda la aplicación | `test_sistema.py` (5) |

## Documentación

| Archivo | Contenido |
|---|---|
| [DOCUMENTACION.md](DOCUMENTACION.md) | Módulos, base de datos y cómo agregar una funcionalidad |
| [ESTRUCTURA.md](ESTRUCTURA.md) | Árbol de carpetas y responsabilidad de cada una |
| [PLANIFICACION_PROYECTO.md](PLANIFICACION_PROYECTO.md) | Requisitos, decisiones técnicas y estado |

## Entrega

| Dato | Valor |
|---|---|
| Proyecto | Gestor de Ventas e Inventario |
| Integrante | Edelyn Hernandez |
| Modalidad | Trabajo individual |
| Rama estable | `main` |
| Versión estable | `v1.0.0` |
| Repositorio | [github.com/Edelyn000/gestor-de-ventas-e-inventario](https://github.com/Edelyn000/gestor-de-ventas-e-inventario) |

El tag `v1.0.0` marca el commit de entrega. Para traer esa versión:

```powershell
git clone https://github.com/Edelyn000/gestor-de-ventas-e-inventario.git
cd gestor-de-ventas-e-inventario
git checkout main
```
