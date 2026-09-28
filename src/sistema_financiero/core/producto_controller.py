from decimal import Decimal

from sqlmodel import Session, col, or_, select
from sqlmodel.sql.expression import SelectOfScalar

from sistema_financiero.utils import ahora, clave_normalizada, normalizar_nombre_categoria

from ..models import Categoria, Producto, obtener_sesion


# ProductoController: CRUD de productos, categorias y alertas de stock.
class ProductoController:
    def crear(
        self,
        producto: Producto,
        db_session: Session | None = None,
    ) -> Producto:
        """Crea un nuevo producto con validaciones de precios y stock."""
        if not producto.nombre_producto.strip():
            msg = "El nombre del producto es obligatorio."
            raise ValueError(msg)

        if (
            producto.precio_compra < 0
            or producto.precio_venta_bs < 0
            or producto.precio_venta_usd < 0
        ):
            msg = "Los precios no pueden ser negativos."
            raise ValueError(msg)

        if producto.stock_actual < 0:
            msg = "El stock no puede ser negativo."
            raise ValueError(msg)

        if producto.stock_minimo < Decimal("0.001"):
            msg = "El stock minimo debe ser al menos 0.001."
            raise ValueError(msg)

        producto.nombre_producto = producto.nombre_producto.strip().upper()

        if producto.categoria_id is None and producto.categoria is not None:
            categoria_resuelta = self.crear_categoria(producto.categoria.nombre, db_session)
            producto.categoria_id = categoria_resuelta.id
            producto.categoria = categoria_resuelta

        producto.unidad = producto.unidad.upper()

        producto.fecha_ingreso = ahora()

        with obtener_sesion(db_session) as session:
            session.add(producto)
            session.commit()
            if producto.idproducto is None:
                msg = "No se pudo recuperar el id del producto."
                raise RuntimeError(msg)
            recargado = session.get(Producto, producto.idproducto)
            if recargado is None:
                msg = "No se pudo recargar el producto."
                raise RuntimeError(msg)
            producto = recargado

        return producto

    def obtener_por_id(
        self,
        idproducto: int,
        db_session: Session | None = None,
    ) -> Producto | None:
        """Busca un producto por su ID. Retorna None si no existe."""
        with obtener_sesion(db_session) as session:
            return session.get(Producto, idproducto)

    def listar_todos(
        self,
        db_session: Session | None = None,
    ) -> list[Producto]:
        """Devuelve todos los productos ordenados alfabeticamente."""
        with obtener_sesion(db_session) as session:
            stmt = select(Producto).order_by(Producto.nombre_producto)
            return list(session.exec(stmt).all())

    def buscar(
        self,
        termino: str,
        db_session: Session | None = None,
    ) -> list[Producto]:
        """Busca productos por nombre o categoria (busqueda parcial)."""
        with obtener_sesion(db_session) as session:
            stmt: SelectOfScalar[Producto] = (
                select(Producto)
                .join(Categoria, col(Producto.categoria_id) == col(Categoria.id), isouter=True)
                .where(
                    or_(
                        Producto.nombre_producto.ilike(f"%{termino}%"),  # type: ignore[attr-defined]
                        Categoria.nombre.ilike(f"%{termino}%"),  # type: ignore[attr-defined]
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
        """Actualiza campos de un producto via clave=valor."""
        with obtener_sesion(db_session) as session:
            producto = session.get(Producto, idproducto)
            if not producto:
                return None

            for clave, valor in kwargs.items():
                if not hasattr(producto, clave):
                    continue

                if (
                    clave in ("precio_compra", "precio_venta_bs", "precio_venta_usd")
                    and Decimal(str(valor)) < 0
                ):
                    msg = f"{clave} no puede ser negativo."
                    raise ValueError(msg)

                if clave == "stock_actual" and Decimal(str(valor)) < 0:
                    msg = "El stock no puede ser negativo."
                    raise ValueError(msg)

                setattr(producto, clave, valor)

            session.add(producto)
            session.commit()
            session.refresh(producto)

        return producto

    def eliminar(
        self,
        idproducto: int,
        db_session: Session | None = None,
    ) -> bool:
        """Elimina un producto por ID. Retorna True si se elimino, False si no existia."""
        with obtener_sesion(db_session) as session:
            producto = session.get(Producto, idproducto)
            if not producto:
                return False

            session.delete(producto)
            session.commit()

        return True

    def crear_categoria(
        self,
        nombre: str,
        db_session: Session | None = None,
    ) -> Categoria:
        """Normaliza una categoria y la crea, o REUTILIZA la existente."""
        nombre_normalizado = normalizar_nombre_categoria(nombre)
        if not nombre_normalizado:
            msg = "El nombre de la categoria no puede estar vacio."
            raise ValueError(msg)
        clave = clave_normalizada(nombre_normalizado)

        with obtener_sesion(db_session) as session:
            existente = session.exec(
                select(Categoria).where(Categoria.clave == clave),
            ).first()
            if existente is not None:
                return existente

            nueva = Categoria(nombre=nombre_normalizado, clave=clave)
            session.add(nueva)
            session.commit()
            session.refresh(nueva)
        return nueva

    def obtener_categorias(
        self,
        db_session: Session | None = None,
    ) -> list[str]:
        """Devuelve los nombres de categorias existentes (ordenados)."""
        with obtener_sesion(db_session) as session:
            stmt = select(Categoria.nombre).order_by(Categoria.nombre)
            resultados = session.exec(stmt).all()
            return [r for r in resultados if r is not None]

    def productos_stock_bajo(
        self,
        db_session: Session | None = None,
    ) -> list[Producto]:
        """Productos con stock actual <= stock minimo (pero > 0)."""
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
        with obtener_sesion(db_session) as session:
            stmt = (
                select(Producto)
                .where(Producto.stock_actual == 0)
                .order_by(Producto.nombre_producto)
            )
            return list(session.exec(stmt).all())

