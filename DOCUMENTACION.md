# Documentación del sistema

Sistema de gestión financiera para un abasto. PyQt6, SQLModel y SQLite. Guarda cada venta en bolívares y dólares con la tasa del día.

## Roles

| Rol | Acceso |
|---|---|
| ADMINISTRADOR | Dashboard, Ventas, Inventarios, Reportes, Usuarios |
| VENDEDOR | Solo Ventas |

El menú lateral se arma a partir del rol: el vendedor arranca en Ventas y nunca ve el Dashboard, así que no toca la red del BCV.

## Módulos

### Dashboard

Cuatro tarjetas: Ventas Hoy, Stock Bajo, Sin Stock y Tasa BCV. Debajo, la tabla de productos con stock bajo o agotado.

La tasa se consulta en un hilo aparte, así que la interfaz no se congela sin internet. Si no hay tasa del día, el Dashboard consulta al BCV; si la hay y tiene menos de 10 minutos, no repite la llamada. El hilo corre cada 10 minutos mientras la app está abierta, y la fila del día se actualiza por UPSERT. Sin red, la tarjeta dice "Sin tasa (error)" y el error queda en `logs/errores.log`.

### Productos

El formulario pide el precio en dólares y muestra el equivalente en bolívares al lado, calculado con la tasa activa. El tipo de venta se deduce de la unidad, no se elige.

| Unidad | Tipo de venta | Cantidad en el ticket |
|---|---|---|
| UNIDAD | UNIDAD | Piezas enteras |
| KILO | PESO | Kilos con decimales y gramos separados |

El stock admite decimales solo con KILO. Las categorías se normalizan al guardar, así que "Limpieza" y "LIMPIEZA" apuntan a la misma fila, y el formulario puede crear una desde el combo.

Un producto con ventas o movimientos de inventario no se puede eliminar: borrarlo rompería el costo histórico de las ventas y los reportes. El botón avisa el motivo.

### POS (formulario de venta)

- **Catálogo** en lista con columnas Producto, USD, Bs, Stock y (+). El precio en bolívares se recalcula con la tasa activa. Doble clic, Enter o el botón (+) agregan al ticket.
- **Filtro de categoría** desplegable, con "Todos" por defecto.
- **Ticket** por tipo de venta: las líneas UNIDAD piden "Cant." entera; si hay alguna línea PESO, el ticket gana columnas Kg y g, un botón "+ Peso" y los rápidos 1kg, 1/2, 1/4 y 100g. Quitar la última línea PESO devuelve el ticket al modo UNIDAD.
- **Cobro digital en un clic**: Tarjeta, Pago Móvil, BioPago y Transferencia cubren el total sin teclear montos.
- **Efectivo con vuelto en vivo**: la fila "Recibido" aparece con el faltante precargado y muestra el vuelto mientras se teclea.
- **Pago mixto**: el panel docked reparte el total entre varios métodos. COBRAR se habilita solo cuando la venta queda cubierta.
- **Tasa manual**: sin internet, el botón ✏️ fija la tasa del día. Queda registrada con origen MANUAL, la tasa oficial del BCV no se toca y si el BCV actualiza durante una venta activa el cambio se ofrece al vaciar el ticket.
- **Factura** al cobrar: vista previa, Imprimir y Guardar PDF. Si falla, la venta ya quedó registrada y el aviso lo dice.

### Ventas

Historial con doble clic para ver el detalle y filtro por rango de fechas. La columna Acciones con el botón de anulación solo la ve el administrador.

Cada venta acepta hasta 6 métodos de pago combinables:

| Método | Clave en BD |
|---|---|
| Efectivo Bs | `efectivo_bs` |
| Efectivo USD | `efectivo_usd` |
| Tarjeta | `tarjeta` |
| Pago Móvil | `pago_movil` |
| BioPago | `bio_pago` |
| Transferencia | `transferencia` |

El POS cobra en bolívares. Un pago en dólares guarda el monto recibido, el equivalente aplicado y el vuelto en bolívares, para que el arqueo descuente el vuelto que salió del cajón.

Anular exige motivo y las credenciales de un administrador. Queda auditada con `motivo_anulacion` y `anulado_por`, y el stock de cada producto se devuelve.

### Inventario

Entrada, salida y ajuste, con historial completo. El vendedor solo ve Entrada: Salida y Ajuste son del administrador.

| Tipo | Motivos | Efecto |
|---|---|---|
| ENTRADA | COMPRA, DEVOLUCION, TRASLADO, OTRO | Suma |
| SALIDA | VENTA, PERDIDA, VENCIMIENTO, TRASLADO, OTRO | Resta |
| AJUSTE | INVENTARIO, ROBO, EXTRA, OTRO | Fija el stock contado |

El ajuste toma el stock físico, calcula la diferencia y guarda el stock anterior y el nuevo. Cada movimiento es una fila de auditoría.

### Reportes

Cerrar Dia consolida el día local de Venezuela. El mismo botón regenera un reporte de una fecha ya cerrada sin duplicar el detalle.

El reporte guarda: total en Bs y USD, cantidad de ventas, unidades vendidas, peso vendido en kilos, costo de ventas, utilidad bruta, margen, alertas de stock, desglose por método de pago, cantidad de productos con costo de compra no confiable y el detalle agrupado por producto.

El costo se toma del snapshot guardado en cada línea de venta, no del precio actual del producto: cambiar el costo hoy no reescribe la historia.

El Excel sale en 4 hojas: Reporte Diario, Ventas del Dia, Alertas de Stock y Productos Vendidos (Detalle).

### Usuarios (solo administrador)

Editar perfil, cambiar contraseña, crear usuario, resetear la contraseña de otro y activar o desactivar. Desactivar en vez de eliminar conserva el historial de ventas asociado al ID.

El login busca el usuario, compara con bcrypt y si el usuario está desactivado no entra aunque la contraseña sea correcta. Cada intento queda en `logs/eventos.log` sin la contraseña.

## Base de datos

SQLite en `database/database.db`. 11 tablas del ORM:

| Tabla | Qué guarda |
|---|---|
| `producto` | Artículos del inventario |
| `categoria` | Categorías normalizadas por clave única |
| `venta` | Cabecera de venta, totales y desglose por método |
| `ventadetalle` | Líneas de la venta, con el costo snapshot |
| `venta_pago` | Desglose de pago, con tasa y vuelto |
| `movimientoinventario` | Auditoría de cambios de stock |
| `tasacambio` | Tasas BCV y manuales por fecha y origen |
| `usuario` | Usuarios con contraseña hasheada y rol |
| `caja` | Apertura y cierre de caja con arqueo |
| `reportediario` | Cierre diario con totales y rentabilidad |
| `reporteventadetalle` | Agrupación de productos por reporte |

La base real tiene además `reporte_venta_detalle`, con 0 filas: la creó la migración `f1e2d3c4b5a6` con el nombre en snake_case y el ORM nunca escribió ahí. Es una tabla muerta.

Los nombres vienen del nombre de la clase en minúsculas: `VentaDetalle` produce `ventadetalle`. Para cambiar uno hay que declararlo en el cuerpo de la clase, `__tablename__` como kwarg se ignora.

El día de negocio es el día local de Venezuela, la BD guarda todo en UTC. `rango_dia_utc()` hace la conversión, y una venta de las 23:50 cuenta para el día que el cajero ve.

## Seguridad

- bcrypt con salt por hash: dos contraseñas iguales dan hashes distintos.
- El mensaje de error del login no dice si el usuario existe.
- Cambiar la contraseña propia pide la actual. Resetear la de otro, solo lo hace un administrador.
- El login y los errores van a `logs/`, nunca las contraseñas.

### Credencial de la semilla local

`db/seeds.py::seed_admin()` crea un usuario **`admin` con contraseña `admin`**
la primera vez que se ejecuta el programa, y solo si la tabla de usuarios está
vacía. El hash usa bcrypt.

Su alcance real es corto:

- `database/database.db` es un archivo local ignorado por git. Quien clone el
  repositorio recibe el código, no la base con usuarios.
- La aplicación corre en el escritorio de quien la usa. Esa contraseña no
  protege ningún servicio remoto.
- La semilla solo actúa sobre una tabla de usuarios vacía, en la primera
  ejecución.

Un despliegue real debería crear al administrador fuera de la semilla, con una
contraseña que elija quien opera.

## Cómo agregar una funcionalidad

1. **Modelo**, en `models/modelos.py`, si hace falta tabla nueva.
2. **Migración**, desde la raíz del repo (el `alembic.ini` usa una URL relativa):

```powershell
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "descripcion del cambio"
.venv\Scripts\python.exe -m alembic upgrade head
```

3. **Servicio o controlador**, en `core/`, con `obtener_sesion(session=None)` para aceptar la sesión del llamador:

```python
class MiServicio:
    def listar(self, session: Session | None = None) -> list[MiModelo]:
        with obtener_sesion(session) as db:
            return list(db.exec(select(MiModelo)).all())
```

4. **Página**, en `ui/`, que solo llama a `core/`.
5. **Menú**, en `ui/interfaz.py`: importar la página, crearla en `__init__`, añadir el nombre a `self._items_menu` y escribir el despachador `_crear_pagina_mi_modulo()`.
6. **Tests** en `tests/`: `pytest-qt` para la UI, BD en memoria para la lógica, y el marker del nivel que corresponda (`unitarias`, `integracion`, `sistema` o `aceptacion`).
7. **Verificar**:

```powershell
.venv\Scripts\python.exe -m ruff check src/ tests/
.venv\Scripts\python.exe -m mypy src/
.venv\Scripts\python.exe -m pytest
```

## Comandos

| Comando | Qué hace |
|---|---|
| `poetry install` | Instalar dependencias |
| `.\run.ps1` | Ejecutar la app |
| `.venv\Scripts\python.exe -m pytest` | Correr los tests |
| `.venv\Scripts\python.exe -m pytest tests/ -m integracion -v` | Un nivel de pruebas |
| `.venv\Scripts\python.exe -m ruff check src/` | Lint |
| `.venv\Scripts\python.exe -m mypy src/` | Tipos |
| `.venv\Scripts\python.exe -m alembic upgrade head` | Aplicar migraciones |

## Metodología y mantenimiento

Ciclo de vida en cascada: requisitos, análisis y diseño, construcción, pruebas. Cada fase se cerró antes de pasar a la siguiente.

| Fase | Resultado |
|---|---|
| Requisitos | RF-01 a RF-07 y RNF-01 a RNF-09 |
| Análisis y diseño | DFD, E-R y diccionario de datos, documentados en la presentación del proyecto |
| Construcción | `src/`, SQLite y migraciones Alembic |
| Pruebas | 522 tests, CI/CD, esta documentación |

Mantenimiento previsto:

| Tipo | Qué |
|---|---|
| Correctivo | Bitácora en `logs/` para ubicar el fallo rápido |
| Adaptativo | Alembic para cambiar el esquema SQLite sin perder datos |
| Perfectivo | Impresión en ticketeras 80 mm y cuentas por pagar |
| Preventivo | Copia diaria de `database/database.db` a unidad externa |