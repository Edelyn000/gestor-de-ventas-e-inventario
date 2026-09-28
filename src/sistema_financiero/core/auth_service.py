import bcrypt
from sqlmodel import Session, select

from sistema_financiero.utils import ahora

from ..models import Usuario, obtener_sesion

LONGITUD_MINIMA_CONTRASENA: int = 4


# AuthService: Login bcrypt y CRUD de usuarios.
class AuthService:
    def verificar_login(
        self,
        usuario: str,
        contrasena: str,
        db_session: Session | None = None,
    ) -> Usuario | None:
        """Verifica credenciales. Retorna el Usuario si son correctas, None si no."""
        with obtener_sesion(db_session) as session:
            user = session.exec(select(Usuario).where(Usuario.usuario == usuario)).first()

        if user is None:
            return None

        if not user.activo:
            return None

        if not bcrypt.checkpw(
            contrasena.encode("utf-8"),
            user.contrasena.encode("utf-8"),
        ):
            return None

        return user

    def crear_usuario(
        self,
        usuario: str,
        contrasena: str,
        nombre_completo: str | None = None,
        rol: str = "VENDEDOR",
        db_session: Session | None = None,
    ) -> Usuario:
        """Crea un nuevo usuario con contrasena hasheada."""
        if not usuario.strip():
            msg = "El nombre de usuario es obligatorio."
            raise ValueError(msg)

        if not contrasena:
            msg = "La contrasena es obligatoria."
            raise ValueError(msg)

        if len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
            msg = f"La contrasena debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres."
            raise ValueError(msg)

        contrasena_hash = bcrypt.hashpw(
            contrasena.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        with obtener_sesion(db_session) as session:
            existente = session.exec(select(Usuario).where(Usuario.usuario == usuario)).first()
            if existente:
                msg = f"El usuario '{usuario}' ya existe."
                raise ValueError(msg)

            nuevo = Usuario(
                usuario=usuario.strip().lower(),
                contrasena=contrasena_hash,
                nombre_completo=nombre_completo.strip() if nombre_completo else None,
                rol=rol.strip().upper(),
                activo=True,
                fecha_creacion=ahora(),
            )
            session.add(nuevo)
            session.commit()
            session.refresh(nuevo)

        return nuevo

    def obtener_por_id(
        self,
        id_usuario: int,
        db_session: Session | None = None,
    ) -> Usuario | None:
        """Busca un usuario por su ID."""
        with obtener_sesion(db_session) as session:
            return session.get(Usuario, id_usuario)

    def obtener_por_usuario(
        self,
        usuario: str,
        db_session: Session | None = None,
    ) -> Usuario | None:
        """Busca un usuario por su nombre de usuario."""
        with obtener_sesion(db_session) as session:
            return session.exec(select(Usuario).where(Usuario.usuario == usuario)).first()

    def listar_usuarios(
        self,
        db_session: Session | None = None,
    ) -> list[Usuario]:
        """Devuelve todos los usuarios ordenados por nombre."""
        with obtener_sesion(db_session) as session:
            stmt = select(Usuario).order_by(Usuario.usuario)
            return list(session.exec(stmt).all())

    def cambiar_contrasena(
        self,
        id_usuario: int,
        contrasena_actual: str,
        nueva_contrasena: str,
        db_session: Session | None = None,
    ) -> bool:
        """Cambia la contrasena de un usuario. Retorna False si la actual no coincide."""
        if len(nueva_contrasena) < LONGITUD_MINIMA_CONTRASENA:
            msg = (
                f"La nueva contrasena debe tener al menos "
                f"{LONGITUD_MINIMA_CONTRASENA} caracteres."
            )
            raise ValueError(msg)

        with obtener_sesion(db_session) as session:
            user = session.get(Usuario, id_usuario)
            if not user:
                return False

            if not bcrypt.checkpw(
                contrasena_actual.encode("utf-8"),
                user.contrasena.encode("utf-8"),
            ):
                return False

            nuevo_hash = bcrypt.hashpw(
                nueva_contrasena.encode("utf-8"),
                bcrypt.gensalt(),
            ).decode("utf-8")
            user.contrasena = nuevo_hash

            session.add(user)
            session.commit()

        return True

    def cambiar_contrasena_admin(
        self,
        id_usuario: int,
        nueva_contrasena: str,
        db_session: Session | None = None,
    ) -> bool:
        """Cambia la contrasena sin verificar la actual (solo admin)."""
        if len(nueva_contrasena) < LONGITUD_MINIMA_CONTRASENA:
            msg = (
                f"La nueva contrasena debe tener al menos "
                f"{LONGITUD_MINIMA_CONTRASENA} caracteres."
            )
            raise ValueError(msg)

        with obtener_sesion(db_session) as session:
            user = session.get(Usuario, id_usuario)
            if not user:
                return False

            nuevo_hash = bcrypt.hashpw(
                nueva_contrasena.encode("utf-8"),
                bcrypt.gensalt(),
            ).decode("utf-8")
            user.contrasena = nuevo_hash

            session.add(user)
            session.commit()

        return True

    def activar(
        self,
        id_usuario: int,
        db_session: Session | None = None,
    ) -> bool:
        """Activa un usuario. Retorna False si no existe."""
        with obtener_sesion(db_session) as session:
            user = session.get(Usuario, id_usuario)
            if not user:
                return False
            user.activo = True
            session.add(user)
            session.commit()
        return True

    def desactivar(
        self,
        id_usuario: int,
        db_session: Session | None = None,
    ) -> bool:
        """Desactiva un usuario. Retorna False si no existe."""
        with obtener_sesion(db_session) as session:
            user = session.get(Usuario, id_usuario)
            if not user:
                return False
            user.activo = False
            session.add(user)
            session.commit()
        return True

    def actualizar(
        self,
        id_usuario: int,
        usuario: str | None = None,
        nombre_completo: str | None = None,
        rol: str | None = None,
        db_session: Session | None = None,
    ) -> Usuario | None:
        """Actualiza los datos de un usuario (nombre, usuario, rol)."""
        with obtener_sesion(db_session) as session:
            user = session.get(Usuario, id_usuario)
            if not user:
                return None

            if usuario is not None:
                existente = session.exec(
                    select(Usuario).where(
                        Usuario.usuario == usuario,
                        Usuario.id != id_usuario,
                    ),
                ).first()
                if existente:
                    msg = f"El usuario '{usuario}' ya esta en uso."
                    raise ValueError(msg)
                user.usuario = usuario.strip().lower()

            if nombre_completo is not None:
                user.nombre_completo = nombre_completo.strip()

            if rol is not None:
                user.rol = rol.strip().upper()

            session.add(user)
            session.commit()
            session.refresh(user)

        return user

