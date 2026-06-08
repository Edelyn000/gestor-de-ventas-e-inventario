# ============================================================
# ARCHIVO: tests/test_producto_controller.py
# Pruebas para el controlador de productos (ProductoController).
#
# ¿QUE ES ProductoController?
#   Es la clase que maneja TODAS las operaciones con productos:
#   crear, buscar, actualizar, eliminar, listar categorias, etc.
#
# ¿QUE ES Producto?
#   Es el modelo ORM que representa la tabla "producto" en la BD.
#   Tiene campos como: nombre_producto, precio_venta_bs, stock_actual, etc.
#
# NOTA: ProductoController.crear() ahora recibe un objeto Producto,
# no parametros separados. Veamos como se usa.
# ============================================================

# Decimal: necesario para crear precios con precision exacta.
#   Decimal("2.50") es 2.50 exacto.
#   2.50 como float seria 2.5 (y 0.1 + 0.2 = 0.30000000000000004).
# En finanzas, SIEMPRE usamos Decimal para dinero.
from decimal import Decimal

# pytest: necesitamos pytest.raises para probar errores.
import pytest

# ProductoController: el servicio que vamos a probar.
from sistema_financiero.core.producto_controller import ProductoController
# Producto: el modelo ORM para crear productos de prueba.
from sistema_financiero.models import Producto


# ============================================================
# TEST: test_crear_producto_exitoso
# ¿QUE PRUEBA? Que se pueda crear un producto con datos validos.
#
# Flujo:
#   1. Crear un objeto Producto con los datos que queremos.
#   2. Llamar a producto_controller.crear(producto, db_session=session).
#   3. Verificar que el producto devuelto tenga ID (se guardo).
# ============================================================
def test_crear_producto_exitoso(session, producto_controller: ProductoController) -> None:
    """
    Prueba que crear() guarde un producto correctamente.
    """
    # ----------------------------------------------------------
    # CREAR UN PRODUCTO DE PRUEBA
    # ----------------------------------------------------------
    # Creamos un objeto Producto "a mano" en lugar de llamar a la API.
    # Esto se llama "crear datos de prueba" (test data).
    #
    # ¿Por que Decimal en lugar de float para los precios?
    #   Porque las operaciones con float pueden tener errores de redondeo.
    #   Ejemplo en Python: 0.1 + 0.2 -> 0.30000000000000004
    #   Con Decimal: Decimal("0.1") + Decimal("0.2") -> Decimal("0.3")
    #
    # ¿Por que "stock_minimo=5"?
    #   El stock minimo es la cantidad que activa la alerta
    #   "stock bajo". Si stock_actual <= stock_minimo, el producto
    #   aparece en la lista de alertas. 5 es un valor tipico.
    producto = Producto(
        nombre_producto="ARROZ",
        categoria="ALIMENTOS",
        precio_compra=Decimal("1.50"),
        precio_venta_bs=Decimal("2.50"),
        precio_venta_usd=Decimal("0.50"),
        stock_actual=100,
        stock_minimo=10,
        unidad="KILO",
    )

    # ----------------------------------------------------------
    # EJECUTAR: llamar al metodo que queremos probar.
    # ----------------------------------------------------------
    # crear() recibe un objeto Producto y lo persiste en la BD.
    # Retorna el mismo producto pero con su ID asignado.
    resultado = producto_controller.crear(producto, db_session=session)

    # ----------------------------------------------------------
    # VERIFICAR: los resultados deben ser los esperados.
    # ----------------------------------------------------------

    # isinstance: verifica que el resultado sea un Producto.
    assert isinstance(resultado, Producto), "Debe retornar un objeto Producto"

    # El ID debe haberse asignado (no es None).
    assert resultado.idproducto is not None, "El producto debe tener ID asignado"

    # El nombre debe estar en mayusculas (el controlador normaliza).
    assert resultado.nombre_producto == "ARROZ"

    # El precio debe coincidir (comparacion exacta con Decimal).
    assert resultado.precio_venta_bs == Decimal("2.50")

    # La fecha de ingreso debe estar asignada.
    assert resultado.fecha_ingreso is not None, "Debe tener fecha de ingreso"


# ============================================================
# TEST: test_crear_producto_sin_nombre
# ¿QUE PRUEBA? Que NO se pueda crear un producto sin nombre.
# ============================================================
def test_crear_producto_sin_nombre(session, producto_controller: ProductoController) -> None:
    """
    Prueba que crear() rechace un producto sin nombre.
    """
    # Producto con nombre vacio (deberia fallar).
    producto = Producto(
        nombre_producto="",
        precio_venta_bs=Decimal("1.00"),
        precio_venta_usd=Decimal("0.20"),
    )

    # with pytest.raises(ValueError): esperamos que se lance un error.
    with pytest.raises(ValueError):
        producto_controller.crear(producto, db_session=session)


# ============================================================
# TEST: test_crear_producto_precio_negativo
# ¿QUE PRUEBA? Que NO se permitan precios negativos.
# ============================================================
def test_crear_producto_precio_negativo(session, producto_controller: ProductoController) -> None:
    """
    Prueba que crear() rechace un producto con precio negativo.
    """
    producto = Producto(
        nombre_producto="PAN",
        precio_venta_bs=Decimal("-5.00"),  # Precio negativo (invalido).
        precio_venta_usd=Decimal("1.00"),
    )

    with pytest.raises(ValueError):
        producto_controller.crear(producto, db_session=session)


# ============================================================
# TEST: test_crear_producto_stock_minimo_invalido
# ¿QUE PRUEBA? Que el stock_minimo no pueda ser 0.
# ============================================================
def test_crear_producto_stock_minimo_invalido(session, producto_controller: ProductoController) -> None:
    """
    Prueba que crear() rechace stock_minimo < 1.
    """
    producto = Producto(
        nombre_producto="LECHE",
        precio_venta_bs=Decimal("3.00"),
        precio_venta_usd=Decimal("0.60"),
        stock_minimo=0,  # Invalido: debe ser al menos 1.
    )

    with pytest.raises(ValueError):
        producto_controller.crear(producto, db_session=session)


# ============================================================
# TEST: test_obtener_por_id
# ¿QUE PRUEBA? Que obtener_por_id() encuentre un producto existente.
# ============================================================
def test_obtener_por_id(session, producto_controller: ProductoController) -> None:
    """
    Prueba que obtener_por_id() retorne el producto correcto.
    """
    # Primero creamos un producto.
    producto = Producto(
        nombre_producto="CAFE",
        precio_venta_bs=Decimal("5.00"),
        precio_venta_usd=Decimal("1.00"),
    )
    creado = producto_controller.crear(producto, db_session=session)

    # Ahora lo buscamos por su ID.
    encontrado = producto_controller.obtener_por_id(creado.idproducto, db_session=session)  # type: ignore[arg-type]

    # Debe encontrarlo y tener el mismo nombre.
    assert encontrado is not None
    assert encontrado.nombre_producto == "CAFE"


# ============================================================
# TEST: test_obtener_por_id_inexistente
# ¿QUE PRUEBA? Que obtener_por_id() retorne None si no existe.
# ============================================================
def test_obtener_por_id_inexistente(session, producto_controller: ProductoController) -> None:
    """
    Prueba que obtener_por_id() retorne None para un ID que no existe.
    """
    resultado = producto_controller.obtener_por_id(9999, db_session=session)
    assert resultado is None


# ============================================================
# TEST: test_listar_todos
# ¿QUE PRUEBA? Que listar_todos() devuelva todos los productos ordenados.
# ============================================================
def test_listar_todos(session, producto_controller: ProductoController) -> None:
    """
    Prueba que listar_todos() devuelva los productos ordenados alfabeticamente.
    """
    # Crear 3 productos con nombres en distinto orden.
    producto_controller.crear(Producto(nombre_producto="ZANAHORIA", precio_venta_bs=Decimal("1"), precio_venta_usd=Decimal("0.20")), db_session=session)
    producto_controller.crear(Producto(nombre_producto="BROCOLI", precio_venta_bs=Decimal("2"), precio_venta_usd=Decimal("0.40")), db_session=session)
    producto_controller.crear(Producto(nombre_producto="ajo", precio_venta_bs=Decimal("3"), precio_venta_usd=Decimal("0.60")), db_session=session)

    lista = producto_controller.listar_todos(db_session=session)

    # Debe haber al menos 3 productos.
    assert len(lista) >= 3

    # Verificar que esten ordenados alfabeticamente.
    # El controlador convierte a mayusculas, entonces:
    # "AJO" < "BROCOLI" < "ZANAHORIA"
    nombres = [p.nombre_producto for p in lista]
    indice_ajo = nombres.index("AJO")
    indice_brocoli = nombres.index("BROCOLI")
    indice_zanahoria = nombres.index("ZANAHORIA")
    assert indice_ajo < indice_brocoli < indice_zanahoria


# ============================================================
# TEST: test_buscar_por_nombre
# ¿QUE PRUEBA? Que buscar() encuentre productos por nombre parcial.
# ============================================================
def test_buscar_por_nombre(session, producto_controller: ProductoController) -> None:
    """
    Prueba que buscar() encuentre productos usando busqueda parcial.
    """
    producto_controller.crear(Producto(
        nombre_producto="HARINA DE MAIZ",
        categoria="ALIMENTOS",
        precio_venta_bs=Decimal("2.50"),
        precio_venta_usd=Decimal("0.50"),
    ), db_session=session)

    # Buscar con un termino parcial en el nombre.
    resultados = producto_controller.buscar("HARINA", db_session=session)

    assert len(resultados) >= 1
    assert any(p.nombre_producto == "HARINA DE MAIZ" for p in resultados)


# ============================================================
# TEST: test_buscar_por_categoria
# ¿QUE PRUEBA? Que buscar() tambien busque en el campo categoria.
# ============================================================
def test_buscar_por_categoria(session, producto_controller: ProductoController) -> None:
    """
    Prueba que buscar() encuentre productos por categoria.
    """
    producto_controller.crear(Producto(
        nombre_producto="PASTA DENTAL",
        categoria="HIGIENE",
        precio_venta_bs=Decimal("3.00"),
        precio_venta_usd=Decimal("0.60"),
    ), db_session=session)

    # Buscar por categoria.
    resultados = producto_controller.buscar("HIGIENE", db_session=session)

    assert len(resultados) >= 1
    assert any(p.categoria == "HIGIENE" for p in resultados)


# ============================================================
# TEST: test_buscar_sin_resultados
# ¿QUE PRUEBA? Que buscar() devuelva lista vacia si no hay coincidencias.
# ============================================================
def test_buscar_sin_resultados(session, producto_controller: ProductoController) -> None:
    """
    Prueba que buscar() devuelva una lista vacia si no hay resultados.
    """
    resultados = producto_controller.buscar("ZZZZNOEXISTO", db_session=session)
    assert len(resultados) == 0


# ============================================================
# TEST: test_actualizar_producto
# ¿QUE PRUEBA? Que actualizar() modifique los campos de un producto.
# ============================================================
def test_actualizar_producto(session, producto_controller: ProductoController) -> None:
    """
    Prueba que actualizar() modifique campos por clave=valor.
    """
    producto = Producto(
        nombre_producto="ACEITE",
        precio_venta_bs=Decimal("5.00"),
        precio_venta_usd=Decimal("1.00"),
        stock_actual=20,
    )
    creado = producto_controller.crear(producto, db_session=session)

    # Actualizar el precio y el stock usando **kwargs.
    # **kwargs significa "argumentos con nombre" (keyword arguments).
    # Ejemplo: actualizar(1, precio_venta_bs=Decimal("6.00"), stock_actual=15)
    actualizado = producto_controller.actualizar(
        creado.idproducto,  # type: ignore[arg-type]
        precio_venta_bs=Decimal("6.00"),
        stock_actual=15,
        db_session=session,
    )

    assert actualizado is not None
    assert actualizado.precio_venta_bs == Decimal("6.00")
    assert actualizado.stock_actual == 15
    # El nombre NO deberia haber cambiado.
    assert actualizado.nombre_producto == "ACEITE"


# ============================================================
# TEST: test_actualizar_producto_inexistente
# ¿QUE PRUEBA? Que actualizar() retorne None si el producto no existe.
# ============================================================
def test_actualizar_producto_inexistente(session, producto_controller: ProductoController) -> None:
    """
    Prueba que actualizar() retorne None para un ID inexistente.
    """
    resultado = producto_controller.actualizar(9999, precio_venta_bs=Decimal("10.00"), db_session=session)
    assert resultado is None


# ============================================================
# TEST: test_eliminar_producto
# ¿QUE PRUEBA? Que eliminar() borre un producto y retorne True.
# ============================================================
def test_eliminar_producto(session, producto_controller: ProductoController) -> None:
    """
    Prueba que eliminar() borre un producto exitosamente.
    """
    producto = Producto(
        nombre_producto="LENTEJAS",
        precio_venta_bs=Decimal("2.00"),
        precio_venta_usd=Decimal("0.40"),
    )
    creado = producto_controller.crear(producto, db_session=session)

    # Eliminar el producto.
    resultado = producto_controller.eliminar(creado.idproducto, db_session=session)  # type: ignore[arg-type]
    assert resultado is True, "eliminar() debe retornar True si se elimino"

    # Verificar que ya no exista.
    no_encontrado = producto_controller.obtener_por_id(creado.idproducto, db_session=session)  # type: ignore[arg-type]
    assert no_encontrado is None, "El producto ya no debe existir"


# ============================================================
# TEST: test_eliminar_producto_inexistente
# ¿QUE PRUEBA? Que eliminar() retorne False si el producto no existe.
# ============================================================
def test_eliminar_producto_inexistente(session, producto_controller: ProductoController) -> None:
    """
    Prueba que eliminar() retorne False para un ID inexistente.
    """
    resultado = producto_controller.eliminar(9999, db_session=session)
    assert resultado is False


# ============================================================
# TEST: test_obtener_categorias
# ¿QUE PRUEBA? Que obtener_categorias() devuelva categorias unicas.
# ============================================================
def test_obtener_categorias(session, producto_controller: ProductoController) -> None:
    """
    Prueba que obtener_categorias() devuelva categorias sin repetir.
    """
    # Crear varios productos con categorias (algunas repetidas).
    producto_controller.crear(Producto(nombre_producto="PROD1", categoria="LACTEOS", precio_venta_bs=Decimal("1"), precio_venta_usd=Decimal("0.20")), db_session=session)
    producto_controller.crear(Producto(nombre_producto="PROD2", categoria="LACTEOS", precio_venta_bs=Decimal("2"), precio_venta_usd=Decimal("0.40")), db_session=session)
    producto_controller.crear(Producto(nombre_producto="PROD3", categoria="PANADERIA", precio_venta_bs=Decimal("3"), precio_venta_usd=Decimal("0.60")), db_session=session)

    categorias = producto_controller.obtener_categorias(db_session=session)

    # Verificar que no haya duplicados.
    assert len(categorias) == len(set(categorias)), "No debe haber categorias duplicadas"
    assert "LACTEOS" in categorias
    assert "PANADERIA" in categorias


# ============================================================
# TEST: test_productos_stock_bajo
# ¿QUE PRUEBA? Que productos_stock_bajo() detecte los correctos.
# La condicion: stock_actual > 0 Y stock_actual <= stock_minimo.
# ============================================================
def test_productos_stock_bajo(session, producto_controller: ProductoController) -> None:
    """
    Prueba que productos_stock_bajo() filtre correctamente.
    """
    # Producto con stock bajo (stock_actual <= stock_minimo).
    producto_controller.crear(Producto(
        nombre_producto="PROD_BAJO",
        precio_venta_bs=Decimal("1"),
        precio_venta_usd=Decimal("0.20"),
        stock_actual=3,
        stock_minimo=5,  # 3 <= 5 → stock bajo
    ), db_session=session)

    # Producto con stock normal.
    producto_controller.crear(Producto(
        nombre_producto="PROD_NORMAL",
        precio_venta_bs=Decimal("2"),
        precio_venta_usd=Decimal("0.40"),
        stock_actual=20,
        stock_minimo=5,  # 20 > 5 → stock normal
    ), db_session=session)

    bajos = producto_controller.productos_stock_bajo(db_session=session)
    nombres_bajos = [p.nombre_producto for p in bajos]

    assert "PROD_BAJO" in nombres_bajos
    assert "PROD_NORMAL" not in nombres_bajos


# ============================================================
# TEST: test_productos_sin_stock
# ¿QUE PRUEBA? Que productos_sin_stock() detecte stock_actual == 0.
# ============================================================
def test_productos_sin_stock(session, producto_controller: ProductoController) -> None:
    """
    Prueba que productos_sin_stock() detecte productos agotados.
    """
    # Producto sin stock.
    producto_controller.crear(Producto(
        nombre_producto="PROD_AGOTADO",
        precio_venta_bs=Decimal("1"),
        precio_venta_usd=Decimal("0.20"),
        stock_actual=0,  # Sin stock.
    ), db_session=session)

    sin_stock = producto_controller.productos_sin_stock(db_session=session)
    nombres = [p.nombre_producto for p in sin_stock]

    assert "PROD_AGOTADO" in nombres
