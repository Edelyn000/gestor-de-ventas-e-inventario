from decimal import Decimal

from sqlmodel import Session, or_, select
from sqlmodel.sql.expression import SelectOfScalar

from sistema_financiero.utils import ahora

from ..models import Producto, obtener_sesion


# ============================================================
# CONTROLADOR: ProductoController
# Esta clase actúa como el componente de lógica de negocio
# responsable de crear, leer, actualizar y eliminar productos.
# ============================================================
class ProductoController:
    def crear(
        self,
        producto: Producto,
        db_session: Session | None = None,
    ) -> Producto:
        """Crea un nuevo producto con validaciones de precios y stock."""
        # Validar que el nombre no sea solo espacios ni esté vacío.
        if not producto.nombre_producto.strip():
            msg = "El nombre del producto es obligatorio."
            raise ValueError(msg)

        # Validar que ninguno de los precios sea negativo.
        if (
            producto.precio_compra < 0
            or producto.precio_venta_bs < 0
            or producto.precio_venta_usd < 0
        ):
            msg = "Los precios no pueden ser negativos."
            raise ValueError(msg)

        # Validar que el stock actual no sea negativo.
        if producto.stock_actual < 0:
            msg = "El stock no puede ser negativo."
            raise ValueError(msg)

        # Validar que el stock mínimo sea al menos 0.001 (1g para UNIDAD se maneja como 1.000).
        if producto.stock_minimo < Decimal("0.001"):
            msg = "El stock minimo debe ser al menos 0.001."
            raise ValueError(msg)

        # Normalizar el nombre y categoría a mayúsculas para búsquedas.
        producto.nombre_producto = producto.nombre_producto.strip().upper()
        if producto.categoria:
            producto.categoria = producto.categoria.strip().upper()

        # Asegurar que la unidad se guarde en mayúsculas.
        producto.unidad = producto.unidad.upper()

        # Registrar la fecha de ingreso al crear el producto.
        producto.fecha_ingreso = ahora()

        # Guardar el producto en la base de datos usando una sesión.
        with obtener_sesion(db_session) as session:
            session.add(producto)
            session.commit()
            session.refresh(producto)

        # Devolver el producto ya persistido con su ID.
        return producto

    def obtener_por_id(
        self,
        idproducto: int,
        db_session: Session | None = None,
    ) -> Producto | None:
        """Busca un producto por su ID. Retorna None si no existe."""
        # Abrir sesión y recuperar el registro por clave primaria.
        with obtener_sesion(db_session) as session:
            return session.get(Producto, idproducto)

    def listar_todos(
        self,
        db_session: Session | None = None,
    ) -> list[Producto]:
        """Devuelve todos los productos ordenados alfabeticamente."""
        # Consultar todos los productos y ordenar por nombre.
        with obtener_sesion(db_session) as session:
            stmt = select(Producto).order_by(Producto.nombre_producto)
            return list(session.exec(stmt).all())

    def buscar(
        self,
        termino: str,
        db_session: Session | None = None,
    ) -> list[Producto]:
        """Busca productos por nombre o categoria (busqueda parcial)."""
        # Usamos ilike para permitir coincidencias parciales sin importar mayúsculas.
        with obtener_sesion(db_session) as session:
            stmt: SelectOfScalar[Producto] = (
                select(Producto)
                .where(
                    or_(
                        Producto.nombre_producto.ilike(f"%{termino}%"),  # type: ignore[attr-defined]
                        Producto.categoria.ilike(f"%{termino}%"),  # type: ignore[union-attr]
                    ),
                )
                .order_by(Producto.nombre_producto)
            )
            return list(session.exec(stmt).all())

    def actualizar(
        self,
        idproducto: int,
        db_session: Session | None = None,
        **kwargs: object,
    ) -> Producto | None:
        """Actualiza campos de un producto via clave=valor.
        Ej: actualizar(1, precio_venta_bs=Decimal("2.50"), stock_actual=10)
        Retorna None si el producto no existe."""
        # Abrir sesión y recuperar el producto existente.
        with obtener_sesion(db_session) as session:
            producto = session.get(Producto, idproducto)
            if not producto:
                return None

            # Recorrer los campos a actualizar.
            for clave, valor in kwargs.items():
                if not hasattr(producto, clave):
                    # Ignorar atributos que no existen en el modelo.
                    continue

                # Validar que los precios no sean negativos.
                if (
                    clave in ("precio_compra", "precio_venta_bs", "precio_venta_usd")
                    and Decimal(str(valor)) < 0
                ):
                    msg = f"{clave} no puede ser negativo."
                    raise ValueError(msg)

                # Validar stock actual no negativo.
                if clave == "stock_actual" and Decimal(str(valor)) < 0:
                    msg = "El stock no puede ser negativo."
                    raise ValueError(msg)

                # Asignar el nuevo valor al producto.
                setattr(producto, clave, valor)

            # Guardar cambios en la base de datos.
            session.add(producto)
            session.commit()
            session.refresh(producto)

        # Retornar el producto actualizado.
        return producto

    def eliminar(
        self,
        idproducto: int,
        db_session: Session | None = None,
    ) -> bool:
        """Elimina un producto por ID. Retorna True si se elimino, False si no existia."""
        # Abrir sesión y buscar el producto.
        with obtener_sesion(db_session) as session:
            producto = session.get(Producto, idproducto)
            if not producto:
                return False

            # Eliminar el registro y confirmar.
            session.delete(producto)
            session.commit()

        return True

    def obtener_categorias(
        self,
        db_session: Session | None = None,
    ) -> list[str]:
        """Devuelve la lista de categorias unicas (sin repetir, ordenadas)."""
        # Seleccionar categorías distintas existentes.
        with obtener_sesion(db_session) as session:
            stmt = (
                select(Producto.categoria)
                .distinct()
                .where(Producto.categoria.isnot(None))  # type: ignore[union-attr]
                .order_by(Producto.categoria)
            )
            resultados = session.exec(stmt).all()
            return [r for r in resultados if r is not None]

    def productos_stock_bajo(
        self,
        db_session: Session | None = None,
    ) -> list[Producto]:
        """Productos con stock actual <= stock minimo (pero > 0)."""
        # Consultar productos cuyo stock está en nivel bajo.
        with obtener_sesion(db_session) as session:
            stmt = (
                select(Producto)
                .where(Producto.stock_actual <= Producto.stock_minimo, Producto.stock_actual > 0)
                .order_by(Producto.stock_actual)  # type: ignore[arg-type]
            )
            return list(session.exec(stmt).all())

    def productos_sin_stock(
        self,
        db_session: Session | None = None,
    ) -> list[Producto]:
        """Productos con stock actual = 0 (agotados)."""
        # Consultar productos que se han quedado sin inventario.
        with obtener_sesion(db_session) as session:
            stmt = (
                select(Producto)
                .where(Producto.stock_actual == 0)
                .order_by(Producto.nombre_producto)
            )
            return list(session.exec(stmt).all())
