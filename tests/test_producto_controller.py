
from decimal import Decimal

import pytest
from sqlmodel import Session

from sistema_financiero.core.producto_controller import ProductoController
from sistema_financiero.models import Categoria, Producto

pytestmark = pytest.mark.integracion


# Prueba que crear() guarde un producto correctamente.
def test_crear_producto_exitoso(session: Session, producto_controller: ProductoController) -> None:
    """Prueba que crear() guarde un producto correctamente."""
    producto = Producto(
        nombre_producto="ARROZ",
        categoria=Categoria(nombre="ALIMENTOS", clave="alimentos"),
        precio_compra=Decimal("1.50"),
        precio_venta_bs=Decimal("2.50"),
        precio_venta_usd=Decimal("0.50"),
        stock_actual=Decimal("100"),
        stock_minimo=Decimal("10"),
        unidad="KILO",
    )

    resultado = producto_controller.crear(producto, db_session=session)


    assert isinstance(resultado, Producto), "Debe retornar un objeto Producto"

    assert resultado.idproducto is not None, "El producto debe tener ID asignado"

    assert resultado.nombre_producto == "ARROZ"

    assert resultado.precio_venta_bs == Decimal("2.50")

    assert resultado.fecha_ingreso is not None, "Debe tener fecha de ingreso"

    assert resultado.categoria is not None
    assert resultado.categoria.nombre == "Alimentos"


# Prueba que crear() rechace un producto sin nombre.
def test_crear_producto_sin_nombre(
    session: Session, producto_controller: ProductoController
) -> None:
    """Prueba que crear() rechace un producto sin nombre."""
    producto = Producto(
        nombre_producto="",
        precio_venta_bs=Decimal("1.00"),
        precio_venta_usd=Decimal("0.20"),
    )

    with pytest.raises(ValueError):
        producto_controller.crear(producto, db_session=session)


# Prueba que crear() rechace un producto con precio negativo.
def test_crear_producto_precio_negativo(
    session: Session, producto_controller: ProductoController
) -> None:
    """Prueba que crear() rechace un producto con precio negativo."""
    producto = Producto(
        nombre_producto="PAN",
        precio_venta_bs=Decimal("-5.00"),
        precio_venta_usd=Decimal("1.00"),
    )

    with pytest.raises(ValueError):
        producto_controller.crear(producto, db_session=session)


# Prueba que crear() rechace stock_minimo < 1.
def test_crear_producto_stock_minimo_invalido(
    session: Session, producto_controller: ProductoController
) -> None:
    """Prueba que crear() rechace stock_minimo < 1."""
    producto = Producto(
        nombre_producto="LECHE",
        precio_venta_bs=Decimal("3.00"),
        precio_venta_usd=Decimal("0.60"),
        stock_minimo=Decimal("0"),
    )

    with pytest.raises(ValueError):
        producto_controller.crear(producto, db_session=session)


# Prueba obtener un producto por su id.
def test_obtener_por_id(session: Session, producto_controller: ProductoController) -> None:
    producto = Producto(
        nombre_producto="CAFE",
        precio_venta_bs=Decimal("5.00"),
        precio_venta_usd=Decimal("1.00"),
    )
    creado = producto_controller.crear(producto, db_session=session)
    assert creado.idproducto is not None

    encontrado = producto_controller.obtener_por_id(creado.idproducto, db_session=session)

    assert encontrado is not None
    assert encontrado.nombre_producto == "CAFE"


# Prueba que obtener_por_id() retorne None para un ID que no existe.
def test_obtener_por_id_inexistente(
    session: Session, producto_controller: ProductoController
) -> None:
    """Prueba que obtener_por_id() retorne None para un ID que no existe."""
    resultado = producto_controller.obtener_por_id(9999, db_session=session)
    assert resultado is None


# Prueba que listar_todos() devuelva los productos ordenados alfabeticamente.
def test_listar_todos(session: Session, producto_controller: ProductoController) -> None:
    """Prueba que listar_todos() devuelva los productos ordenados alfabeticamente."""
    minimo_productos = 3
    producto_controller.crear(
        Producto(
            nombre_producto="ZANAHORIA",
            precio_venta_bs=Decimal("1"),
            precio_venta_usd=Decimal("0.20"),
        ),
        db_session=session,
    )
    producto_controller.crear(
        Producto(
            nombre_producto="BROCOLI",
            precio_venta_bs=Decimal("2"),
            precio_venta_usd=Decimal("0.40"),
        ),
        db_session=session,
    )
    producto_controller.crear(
        Producto(
            nombre_producto="ajo", precio_venta_bs=Decimal("3"), precio_venta_usd=Decimal("0.60")
        ),
        db_session=session,
    )

    lista = producto_controller.listar_todos(db_session=session)

    assert len(lista) >= minimo_productos

    nombres = [p.nombre_producto for p in lista]
    indice_ajo = nombres.index("AJO")
    indice_brocoli = nombres.index("BROCOLI")
    indice_zanahoria = nombres.index("ZANAHORIA")
    assert indice_ajo < indice_brocoli < indice_zanahoria


# Prueba que buscar() encuentre productos usando busqueda parcial.
def test_buscar_por_nombre(session: Session, producto_controller: ProductoController) -> None:
    """Prueba que buscar() encuentre productos usando busqueda parcial."""
    producto_controller.crear(
        Producto(
            nombre_producto="HARINA DE MAIZ",
            precio_venta_bs=Decimal("2.50"),
            precio_venta_usd=Decimal("0.50"),
        ),
        db_session=session,
    )

    resultados = producto_controller.buscar("HARINA", db_session=session)

    assert len(resultados) >= 1
    assert any(p.nombre_producto == "HARINA DE MAIZ" for p in resultados)


# Prueba que buscar() encuentre productos por categoria.
def test_buscar_por_categoria(session: Session, producto_controller: ProductoController) -> None:
    """Prueba que buscar() encuentre productos por categoria."""
    producto_controller.crear(
        Producto(
            nombre_producto="PASTA DENTAL",
            categoria=Categoria(nombre="HIGIENE", clave="higiene"),
            precio_venta_bs=Decimal("3.00"),
            precio_venta_usd=Decimal("0.60"),
        ),
        db_session=session,
    )

    resultados = producto_controller.buscar("HIGIENE", db_session=session)

    assert len(resultados) >= 1
    assert any(p.categoria is not None and p.categoria.nombre == "Higiene" for p in resultados)


# Prueba que buscar() devuelva una lista vacia si no hay resultados.
def test_buscar_sin_resultados(session: Session, producto_controller: ProductoController) -> None:
    """Prueba que buscar() devuelva una lista vacia si no hay resultados."""
    resultados = producto_controller.buscar("ZZZZNOEXISTO", db_session=session)
    assert len(resultados) == 0


# Prueba que actualizar() modifique campos por clave=valor.
def test_actualizar_producto(session: Session, producto_controller: ProductoController) -> None:
    """Prueba que actualizar() modifique campos por clave=valor."""
    producto = Producto(
        nombre_producto="ACEITE",
        precio_venta_bs=Decimal("5.00"),
        precio_venta_usd=Decimal("1.00"),
        stock_actual=Decimal("20"),
    )
    creado = producto_controller.crear(producto, db_session=session)
    assert creado.idproducto is not None

    actualizado = producto_controller.actualizar(
        creado.idproducto,
        precio_venta_bs=Decimal("6.00"),
        stock_actual=Decimal("15"),
        db_session=session,
    )

    assert actualizado is not None
    assert actualizado.precio_venta_bs == Decimal("6.00")
    assert actualizado.stock_actual == Decimal("15")
    assert actualizado.nombre_producto == "ACEITE"


# Prueba que actualizar() retorne None para un ID inexistente.
def test_actualizar_producto_inexistente(
    session: Session, producto_controller: ProductoController
) -> None:
    """Prueba que actualizar() retorne None para un ID inexistente."""
    resultado = producto_controller.actualizar(
        9999, precio_venta_bs=Decimal("10.00"), db_session=session
    )
    assert resultado is None


# Prueba que eliminar() borre un producto exitosamente.
def test_eliminar_producto(session: Session, producto_controller: ProductoController) -> None:
    """Prueba que eliminar() borre un producto exitosamente."""
    producto = Producto(
        nombre_producto="LENTEJAS",
        precio_venta_bs=Decimal("2.00"),
        precio_venta_usd=Decimal("0.40"),
    )
    creado = producto_controller.crear(producto, db_session=session)

    assert creado.idproducto is not None

    resultado = producto_controller.eliminar(creado.idproducto, db_session=session)
    assert resultado is True, "eliminar() debe retornar True si se elimino"

    no_encontrado = producto_controller.obtener_por_id(creado.idproducto, db_session=session)
    assert no_encontrado is None, "El producto ya no debe existir"


# Prueba que eliminar() retorne False para un ID inexistente.
def test_eliminar_producto_inexistente(
    session: Session, producto_controller: ProductoController
) -> None:
    """Prueba que eliminar() retorne False para un ID inexistente."""
    resultado = producto_controller.eliminar(9999, db_session=session)
    assert resultado is False


# Prueba que obtener_categorias() devuelva categorias sin repetir.
def test_obtener_categorias(session: Session, producto_controller: ProductoController) -> None:
    """Prueba que obtener_categorias() devuelva categorias sin repetir."""
    producto_controller.crear(
        Producto(
            nombre_producto="PROD1",
            categoria=Categoria(nombre="Lacteos", clave="lacteos"),
            precio_venta_bs=Decimal("1"),
            precio_venta_usd=Decimal("0.20"),
        ),
        db_session=session,
    )
    producto_controller.crear(
        Producto(
            nombre_producto="PROD2",
            categoria=Categoria(nombre="LACTEOS", clave="lacteos"),
            precio_venta_bs=Decimal("2"),
            precio_venta_usd=Decimal("0.40"),
        ),
        db_session=session,
    )
    producto_controller.crear(
        Producto(
            nombre_producto="PROD3",
            categoria=Categoria(nombre="Panaderia", clave="panaderia"),
            precio_venta_bs=Decimal("3"),
            precio_venta_usd=Decimal("0.60"),
        ),
        db_session=session,
    )

    categorias = producto_controller.obtener_categorias(db_session=session)

    assert len(categorias) == len(set(categorias)), "No debe haber categorias duplicadas"
    assert "Lacteos" in categorias
    assert "Panaderia" in categorias


# Prueba que productos_stock_bajo() filtre correctamente.
def test_productos_stock_bajo(session: Session, producto_controller: ProductoController) -> None:
    """Prueba que productos_stock_bajo() filtre correctamente."""
    producto_controller.crear(
        Producto(
            nombre_producto="PROD_BAJO",
            precio_venta_bs=Decimal("1"),
            precio_venta_usd=Decimal("0.20"),
            stock_actual=Decimal("3"),
            stock_minimo=Decimal("5"),
        ),
        db_session=session,
    )

    producto_controller.crear(
        Producto(
            nombre_producto="PROD_NORMAL",
            precio_venta_bs=Decimal("2"),
            precio_venta_usd=Decimal("0.40"),
            stock_actual=Decimal("20"),
            stock_minimo=Decimal("5"),
        ),
        db_session=session,
    )

    bajos = producto_controller.productos_stock_bajo(db_session=session)
    nombres_bajos = [p.nombre_producto for p in bajos]

    assert "PROD_BAJO" in nombres_bajos
    assert "PROD_NORMAL" not in nombres_bajos


# Prueba que productos_sin_stock() detecte productos agotados.
def test_productos_sin_stock(session: Session, producto_controller: ProductoController) -> None:
    """Prueba que productos_sin_stock() detecte productos agotados."""
    producto_controller.crear(
        Producto(
            nombre_producto="PROD_AGOTADO",
            precio_venta_bs=Decimal("1"),
            precio_venta_usd=Decimal("0.20"),
            stock_actual=Decimal("0"),
        ),
        db_session=session,
    )

    sin_stock = producto_controller.productos_sin_stock(db_session=session)
    nombres = [p.nombre_producto for p in sin_stock]

    assert "PROD_AGOTADO" in nombres


# Prueba que crear una categoria normaliza y reutiliza por clave.
def test_crear_categoria_normaliza_y_reutiliza_por_clave(
    session: Session, producto_controller: ProductoController
) -> None:
    primera = producto_controller.crear_categoria("jabón de baño", db_session=session)
    assert primera.id is not None
    assert primera.nombre == "Jabón de Baño"

    segunda = producto_controller.crear_categoria("JABÓN DE BAÑO", db_session=session)
    assert segunda.id == primera.id

    categorias = producto_controller.obtener_categorias(db_session=session)
    assert categorias == ["Jabón de Baño"]


# Prueba que claves distintas no se mezclan.
def test_crear_categoria_claves_distintas_no_se_mezclan(
    session: Session, producto_controller: ProductoController
) -> None:
    higiene = producto_controller.crear_categoria("HIGIENE", db_session=session)
    limpieza = producto_controller.crear_categoria("Limpieza", db_session=session)

    assert higiene.id is not None
    assert limpieza.id is not None
    assert higiene.id != limpieza.id

    assert producto_controller.obtener_categorias(db_session=session) == [
        "Higiene",
        "Limpieza",
    ]

