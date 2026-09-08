# Documentación del Sistema Financiero

## ¿Qué es este sistema?

Un sistema de gestión financiera para un abasto/mini-mercado. Permite llevar control de productos, ventas, inventario, reportes diarios y usuarios. Trabaja con SQLite local y tiene una interfaz gráfica escrita en PyQt6.

---

## Roles de usuario

| Rol | Acceso |
|---|---|
| **ADMINISTRADOR** | Todo: productos, ventas, inventario, reportes, gestión de usuarios |
| **VENDEDOR** | Productos, ventas, inventario, reportes. NO ve la página de Usuarios |

---

## Módulos del sistema

### 1. Dashboard (página de inicio)

**Qué muestra:**
- Tarjeta "Ventas Hoy": total vendido en bolívares el día actual
- Tarjeta "Stock Bajo": productos por debajo del mínimo
- Tarjeta "Sin Stock": productos con stock en cero
- Tarjeta "Tasa BCV": tasa de cambio del día (se consulta automáticamente al BCV)
- Tabla de productos con stock bajo o sin stock

**Cómo funciona:**
- Se actualiza automáticamente cada 10 minutos
- Si no hay tasa del BCV para hoy, consulta el BCV en un hilo separado (no congela la app)
- La tasa se guarda en la tabla `tasa_cambio` y se reutiliza para las ventas

---

### 2. Productos

**Qué permite hacer:**
- **Crear producto**: nombre, categoría, tipo de venta (UNIDAD/PESO/GRAMOS), precios de compra y venta (VES y USD), stock actual, stock mínimo
- **Editar producto**: modificar cualquier dato
- **Eliminar producto**: con confirmación
- **Buscar**: filtrar por nombre o categoría mientras escribes

**Tipos de venta:**
| Tipo | Descripción | Ejemplo |
|---|---|---|
| UNIDAD | Piezas enteras | 5 latas, 10 paquetes |
| PESO | Kilogramos (decimal) | 2.500 kg de arroz |
| GRAMOS | Gramos (decimal) | 500 gramos de queso |

**Campos del producto:**
- `nombre_producto`: nombre del artículo
- `categoria`: agrupación (ej: "Lácteos", "Carnes")
- `tipo_venta`: UNIDAD, PESO o GRAMOS
- `precio_compra`: cuánto costó (en VES)
- `precio_venta_bs`: precio de venta en bolívares
- `precio_venta_usd`: precio de venta en dólares
- `stock_actual`: cantidad actual en inventario
- `stock_minimo`: mínimo antes de alertar
- `unidad`: texto descriptivo (ej: "UNIDAD", "KG", "GRAMO")

---

### 3. Ventas

**Qué permite hacer:**
- **Registrar venta**: seleccionar productos, cantidades, método de pago
- **Anular venta**: devolver stock automáticamente
- **Ver detalle**: doble clic en una fila muestra los productos de esa venta
- **Filtrar por fechas**: seleccionar rango desde/hasta

**Métodos de pago (pueden combinarse en una venta):**
| Método | Descripción |
|---|---|
| Efectivo BS | Pago en bolívares efectivo |
| Efectivo USD | Pago en dólares efectivo |
| Tarjeta | Pago con tarjeta de crédito/débito |
| Pago Móvil | Transferencia bancaria |
| BioPago | Pago biométrico |

**Cómo se registra una venta:**
1. El usuario selecciona productos y cantidades
2. El sistema calcula los subtotales y el total
3. Selecciona el método de pago y los montos
4. Se aplica la tasa de cambio del día para convertir BS ↔ USD
5. Se guarda la venta con estado "COMPLETADA"
6. Se genera un número de factura automático

**Cuando se anula una venta:**
- El estado cambia a "ANULADA"
- El stock de cada producto se devuelve automáticamente
- Los movimientos de inventario se registran como "SALIDA" con motivo "DEVOLUCION"

---

### 4. Inventario

**Qué permite hacer:**
- **Registrar entrada**: compras, devoluciones, traslados
- **Registrar salida**: pérdidas, vencimientos, traslados
- **Registrar ajuste**: corrección de inventario físico
- **Ver historial**: tabla con todos los movimientos

**Tipos de movimiento:**
| Tipo | Motivos | Efecto en stock |
|---|---|---|
| ENTRADA | COMPRA, DEVOLUCION, TRASLADO, OTRO | Suma al stock |
| SALIDA | VENTA, PERDIDA, VENCIMIENTO, TRASLADO, OTRO | Resta del stock |
| AJUSTE | INVENTARIO, ROBO, EXTRA, OTRO | Establece stock físico |

**Cómo funciona el ajuste:**
- El usuario indica el stock FÍSICO (lo que cuenta en el almacén)
- El sistema calcula la diferencia con el stock registrado
- Registra el movimiento con stock_anterior y stock_nuevo

**Cada movimiento registra:**
- Producto afectado
- Tipo (ENTRADA/SALIDA/AJUSTE)
- Motivo
- Cantidad
- Stock anterior y nuevo (para auditoría)
- Fecha y observaciones

---

### 5. Reportes

**Qué permite hacer:**
- **Cerrar día**: genera un reporte consolidado del día actual
- **Regenerar**: volver a generar un reporte de una fecha específica
- **Exportar Excel**: descargar el reporte como archivo .xlsx
- **Ver historial**: tabla con reportes anteriores

**Qué contiene un reporte diario:**
- Total de ventas en BS y USD
- Cantidad de ventas realizadas
- Cantidad de productos vendidos
- Productos con stock bajo
- Productos sin stock
- Desglose por método de pago (efectivo BS, efectivo USD, tarjeta, pago móvil, bio_pago)
- Fecha y hora de generación

---

### 6. Usuarios (solo ADMINISTRADOR)

**Qué permite hacer:**
- **Ver mi perfil**: nombre, usuario, rol
- **Editar perfil**: cambiar nombre completo
- **Cambiar contraseña**: con verificación de contraseña actual
- **Crear usuario**: nombre completo, usuario, contraseña, rol
- **Resetear contraseña**: el admin puede cambiar la contraseña de otro usuario
- **Activar/Desactivar**: bloquear acceso sin eliminar el usuario

**Por qué desactivar y no eliminar:**
Si eliminas un usuario, se pierden las ventas asociadas a ese ID. Al desactivarlo, no puede entrar pero su historial se mantiene.

**Cómo funciona el login:**
1. El usuario escribe su nombre y contraseña
2. El sistema busca el usuario en la BD
3. Verifica la contraseña con bcrypt (compara hash)
4. Si es correcto → abre la ventana principal
5. Si es incorrecto → muestra "Usuario o contraseña incorrectos"
6. Un usuario desactivado no puede iniciar sesión aunque la contraseña sea correcta

---

## Base de datos

**Motor:** SQLite local (`database/database.db`)

**Tablas:**

| Tabla | Qué almacena |
|---|---|
| `producto` | Artículos del inventario |
| `venta` | Ventas completas con totales y métodos de pago |
| `venta_detalle` | Líneas individuales de cada venta (producto + cantidad + precio) |
| `movimiento_inventario` | Auditoría de cambios de stock |
| `tasa_cambio` | Tasas diarias del BCV |
| `usuario` | Usuarios del sistema (contraseña hasheada con bcrypt) |
| `reporte_diario` | Cierres diarios consolidados |

**Monedas:**
- El sistema trabaja en dos monedas: VES (bolívares) y USD (dólares)
- Cada venta registra el total en ambas monedas
- La tasa de cambio se usa al momento de la venta para la conversión

---

## Seguridad

- **Contraseñas**: se guardan hasheadas con bcrypt (nunca en texto plano)
- **Bcrypt es lento a propósito**: dificulta ataques de fuerza bruta
- **Cada hash incluye su "sal"**: dos hashes del mismo texto son diferentes
- **No revelar si el usuario existe**: el mensaje de error siempre dice "Usuario o contraseña incorrectos"
- **Verificación de contraseña actual**: para cambiar la propia contraseña, se pide la actual

---

## Cómo agregar una nueva funcionalidad

### 1. Crear el modelo (si es necesario)

En `src/sistema_financiero/models/modelos.py`:

```python
class MiModelo(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    campo: str = Field(max_length=100)
```

### 2. Crear la migración (si es necesario)

```bash
alembic revision --autogenerate -m "descripcion del cambio"
alembic upgrade head
```

### 3. Crear el controlador/servicio

En `src/sistema_financiero/core/`:

```python
class MiServicio:
    def listar(self, db_session: Session | None = None) -> list[MiModelo]:
        with obtener_sesion(db_session) as session:
            return list(session.exec(select(MiModelo)).all())
```

### 4. Crear la página UI

En `src/sistema_financiero/ui/`:

```python
class MiPagina(QWidget):
    def __init__(self, controlador):
        super().__init__()
        # Layout, tabla, botones...
```

### 5. Agregar al menú

En `src/sistema_financiero/ui/interfaz.py`:
- Importar la página
- Crearla en `__init__`
- Agregar "Mi Módulo" a `items_menu`
- Crear `_crear_pagina_mi_modulo()` para agregarla al `QStackedWidget`

### 6. Escribir tests

En `tests/`:
- Tests de UI con `pytest-qt`
- Tests de lógica de negocio con `pytest` y BD en memoria

### 7. Verificar

```bash
poetry run ruff check src/
poetry run mypy src/
poetry run pytest
```

---

## Comandos útiles

| Comando | Qué hace |
|---|---|
| `poetry install` | Instalar dependencias |
| `poetry run python -m sistema_financiero` | Ejecutar la app |
| `poetry run pytest` | Ejecutar todos los tests |
| `poetry run pytest tests/ -v` | Tests con verbosidad |
| `poetry run pytest tests/ -k test_algo` | Test específico |
| `poetry run ruff check src/` | Verificar estilo de código |
| `poetry run mypy src/` | Verificar tipos |
| `alembic upgrade head` | Aplicar migraciones |
| `alembic revision --autogenerate -m "msg"` | Crear migración |

---

## Estructura del proyecto

```
sistema_finacieron/
├── src/sistema_financiero/     ← código fuente
│   ├── __main__.py             ← punto de entrada
│   ├── models/                 ← modelos de BD (SQLModel)
│   ├── core/                   ← lógica de negocio
│   ├── services/               ← servicios externos (BCV, Excel)
│   ├── ui/                     ← interfaz gráfica (PyQt6)
│   ├── utils/                  ← utilidades (fechas, formato)
│   └── db/                     ← migraciones y seeds
├── tests/                      ← pruebas
├── database/                   ← base de datos SQLite
├── alembic/                    ← migraciones
└── DOCUMENTACION.md            ← este archivo
```

---

## Resumen del proyecto (para no olvidarlo)

### ¿Qué es?
Sistema de gestión financiera para un abasto/mini-mercado. Control de productos, ventas, inventario, tasas de cambio, reportes y dashboard con gráficos. MVP **completado al 100%**.

### Arquitectura en capas

| Capa | Ubicación | Qué hace |
|------|-----------|----------|
| **Entrypoint** | `__main__.py` | Inicializa la app, DB, login, ventana principal |
| **UI (pantallas)** | `src/ui/` | 7 vistas + 4 diálogos + 4 widgets reutilizables (PyQt6) |
| **Módulos (fachadas)** | `src/modules/` | Conecta UI con lógica de negocio |
| **Core (lógica)** | `src/core/` | Reglas de negocio: auth, productos, ventas, inventario, reportes, tasas (~1773 líneas) |
| **Servicios** | `src/services/` | Servicios externos: consulta BCV, exportación Excel |
| **Modelos (BD)** | `src/models/` | 7 tablas SQLModel con check constraints |
| **DB (migraciones)** | `src/db/` | Alembic + seeds (admin, productos, tasas) |
| **Utils** | `src/utils/` | Helpers: formateo moneda, validación, constantes |

### Qué hace cada módulo

| Módulo | Función principal |
|--------|-------------------|
| **Dashboard** | Panel resumen: ventas del día, stock bajo, tasa BCV, gráficos |
| **Productos** | CRUD completo con tipos (UNIDAD/PESO/GRAMOS), precios VES/USD |
| **Ventas** | Registro multi-pago, facturación, anulación con devolución stock |
| **Inventario** | Entradas, salidas, ajustes con auditoría de stock |
| **Reportes** | Cierre diario, exportar Excel, historial |
| **Tasas** | BCV automático + manual, historial |
| **Usuarios** | Login bcrypt, CRUD, activar/desactivar |

### Qué ya tiene el proyecto

- **172 tests** pasando (unitarios + UI)
- **CI/CD** con GitHub Actions (lint + tests + coverage)
- **Base de datos** SQLite local (`database/database.db`)
- **Login** seguro con bcrypt
- **Tipado completo** (mypy strict, 0 errores)
- **Linting** (ruff, 0 fallos)
- **Migraciones** con Alembic

### Tecnologías principales

| Tecnología | Para qué |
|------------|----------|
| Python >=3.14 | Lenguaje base |
| PyQt6 | Interfaz gráfica de escritorio |
| SQLModel | ORM con tipado |
| SQLite | Base de datos local |
| pyqtgraph | Gráficos en dashboard |
| openpyxl | Exportación Excel |
| scraper-bcv | Tasas BCV automáticas |
| bcrypt | Contraseñas seguras |
| alembic | Migraciones de BD |

### Comandos clave

| Comando | Qué hace |
|---------|----------|
| `poetry run python -m sistema_financiero` | Ejecutar la app |
| `poetry run pytest` | Correr todos los tests |
| `poetry run ruff check src/` | Verificar código |
| `poetry run mypy src/` | Verificar tipos |

### Estado final

| Fase | Estado |
|------|--------|
| Entrypoint + Login + DB | ✅ Completado |
| CRUD Productos + UI | ✅ Completado |
| Módulo Ventas + Detalle | ✅ Completado |
| Inventario + Movimientos | ✅ Completado |
| Tasas de Cambio + Reportes | ✅ Completado |
| Dashboard + Gráficos | ✅ Completado |
| Exportación Excel | ✅ Completado |
| Tests + CI + Documentación | ✅ Completado |

**Proyecto listo para uso en producción local.**

---

## Metodología del Proyecto

### Modelo seleccionado: Ciclo de Vida de Llorens Fábregas (II) — Cascada/Secuencial

```
Fase 1 → Fase 2 → Fase 3 → Fase 4
(Requisitos) (Diseño) (Construcción) (Pruebas)
```

Cada fase se completa antes de pasar a la siguiente. No se retrocede.

### Por qué este modelo

- **Requisitos estables:** El abasto siempre va a vender, controlar stock y cobrar en BS/USD
- **Mediana complejidad:** No es un sistema que cambie cada semana
- **Diseño primero:** Al diseñar bien la BD al inicio, evitaste problemas después
- **Feedback tardío mitigado:** Los tests (172) compensan que el cliente no vio el sistema hasta el final

### Fases aplicadas

| Fase | Qué se hizo | Resultado |
|------|-------------|-----------|
| **1. Requisitos** | Definir necesidades del abasto: registro de ventas, alertas stock, tasa BCV, inventario, usuarios | Documento de necesidades |
| **2. Análisis y Diseño** | Diseñar BD (7 tablas), DFD (Nivel 0, 1, 2, 3), Diagrama E-R | Arquitectura del sistema |
| **3. Construcción** | Programar: modelos, core, UI, servicios, db | Código funcional |
| **4. Pruebas y Mantenimiento** | 172 tests, CI/CD, documentación, plan de mantenimiento | Sistema verificado |

### Documentos generados por fase

| Fase | Documentos |
|------|------------|
| Requisitos | Requisitos funcionales (RF-01 a RF-07), requisitos no funcionales (RNF-01 a RNF-09) |
| Diseño | DFD Nivel 0/1/2/3, Diagrama E-R, Diccionario de Datos, Fichas de Proceso/Flujo/Almacén/Entidad |
| Construcción | Código fuente (src/), base de datos SQLite, migraciones Alembic |
| Pruebas | 172 tests (unitarios + UI), CI/CD GitHub Actions, DOCUMENTACION.md |

### Plan de Mantenimiento

| Tipo | Descripción |
|------|-------------|
| **Correctivo** | Bitácoras de logs automáticos en `logs/` para reparaciones inmediatas |
| **Adaptativo** | Alembic para migraciones de esquema SQLite sin perder datos |
| **Perfectivo** | Planificación de impresión en ticketeras 80mm y cuentas por pagar |
| **Preventivo** | Copias de seguridad diarias de `database/database.db` a unidad externa o nube |
