# ============================================================
# IMPORTACIONES
# ============================================================
# datetime: para registrar la fecha de creacion del usuario.
from datetime import datetime

# bcrypt: libreria de hashing de contrasenas.
#   - hashpw(): convierte una contrasena en un hash seguro.
#   - gensalt(): genera una "sal" aleatoria unica para cada hash.
#   - checkpw(): compara una contrasena con un hash guardado.
#
# Por que bcrypt y no otro algoritmo?
#   - Es LENTO a proposito (dificulta ataques de fuerza bruta).
#   - Cada hash incluye su propia "sal" (2 hashes del mismo texto
#     son diferentes entre si).
#   - Es el estandar actual para guardar contrasenas.
import bcrypt

# select: funcion de SQLModel para construir consultas SELECT.
from sqlmodel import select

# Importamos el modelo Usuario y la funcion get_session.
from ..models import Usuario, get_session

# Constante: longitud minima para contrasenas.
# Es mejor usar una constante que el numero 4 directamente ("magic number").
# Si en el futuro queremos cambiarlo a 8, solo cambiamos esta linea.
LONGITUD_MINIMA_CONTRASENA: int = 4


# ============================================================
# SERVICIO: AuthService
# ============================================================
# Servicio de autenticacion y gestion de usuarios.
#
# DIFERENCIA con LoginDialog:
#   - LoginDialog (ui/) solo llama a verificar_login().
#   - AuthService (core/) tiene TODAS las operaciones con usuarios.
#   - La UI NO debe llamar a bcrypt directamente. Siempre a traves
#     de AuthService.
#
# Responsabilidades:
#   - verificar_login()     → autenticar usuario + contrasena
#   - crear_usuario()       → registrar un nuevo usuario
#   - obtener_por_id()      → buscar por ID
#   - obtener_por_usuario() → buscar por nombre de usuario
#   - listar_usuarios()     → todos los usuarios
#   - cambiar_contrasena()  → actualizar contrasena (con hash)
#   - activar/desactivar    → controlar acceso al sistema
# ============================================================
class AuthService:
    # ------------------------------------------------------------------
    # verificar_login(): metodo principal de autenticacion
    # ------------------------------------------------------------------
    # Este es el metodo que llama LoginDialog cuando el usuario
    # hace clic en "Ingresar".
    #
    # Flujo:
    #   1. Buscar el usuario en la BD por nombre de usuario.
    #   2. Si no existe → retorna None (usuario incorrecto).
    #   3. Si existe pero no esta activo → retorna None.
    #   4. Verificar la contrasena con bcrypt.checkpw().
    #   5. Si no coincide → retorna None.
    #   6. Si todo ok → retorna el objeto Usuario.
    #
    # Por que retornar None en lugar de lanzar una excepcion?
    #   - Porque "login fallido" NO es un error del programa,
    #     es un resultado esperado. Las excepciones son para
    #     situaciones excepcionales (error de BD, etc.).
    #   - La UI revisa si el resultado es None y muestra
    #     "Usuario o contrasena incorrectos".
    #
    # Por que NO revelar si el usuario existe o no?
    #   - Seguridad: si decimos "usuario no existe", un atacante
    #     sabe que usuarios son validos y solo tiene que adivinar
    #     la contrasena.
    #   - Siempre decimos "usuario o contrasena incorrectos".
    # ------------------------------------------------------------------
    def verificar_login(self, usuario: str, contrasena: str) -> Usuario | None:
        """Verifica credenciales. Retorna el Usuario si son correctas, None si no."""
        # Paso 1: Buscar el usuario en la BD.
        # Usamos with get_session() para asegurar que la conexion se cierre.
        with get_session() as session:
            # select(Usuario): consulta SELECT * FROM usuario.
            # .where(Usuario.usuario == usuario): filtro WHERE usuario = '...'.
            # .first(): devuelve el primer resultado o None.
            user = session.exec(select(Usuario).where(Usuario.usuario == usuario)).first()

        # Paso 2: Si el usuario no existe, retornar None.
        # No especificamos si el problema es el usuario o la contrasena.
        if user is None:
            return None

        # Paso 3: Si el usuario existe pero esta desactivado, denegar acceso.
        # Un usuario desactivado no deberia poder ingresar al sistema.
        if not user.activo:
            return None

        # Paso 4: Verificar la contrasena con bcrypt.
        # checkpw() recibe: (contrasena_ingresada_en_bytes, hash_guardado_en_bytes).
        # .encode("utf-8"): convierte el string a bytes (bcrypt trabaja con bytes).
        if not bcrypt.checkpw(
            contrasena.encode("utf-8"),
            user.contrasena.encode("utf-8"),
        ):
            return None

        # Paso 5: Todo correcto, retornar el usuario.
        return user

    # ------------------------------------------------------------------
    # crear_usuario(): registra un nuevo usuario en el sistema
    # ------------------------------------------------------------------
    # La contrasena se guarda HASHEADA, nunca en texto plano.
    # Si alguien roba la BD, no podra ver las contrasenas originales.
    #
    # Por que hashear la contrasena AQUI y no en el modelo?
    #   - El modelo Usuario solo define la estructura de la tabla.
    #   - La capa core es responsable de las reglas de negocio,
    #     incluyendo el hashing de contrasenas.
    #   - Si cambiamos de algoritmo (ej: de bcrypt a argon2),
    #     solo cambiamos este metodo, no el modelo ni la UI.
    # ------------------------------------------------------------------
    def crear_usuario(
        self,
        usuario: str,
        contrasena: str,
        nombre_completo: str | None = None,
    ) -> Usuario:
        """Crea un nuevo usuario con contrasena hasheada."""
        # Validar que el nombre de usuario no este vacio.
        if not usuario.strip():
            raise ValueError("El nombre de usuario es obligatorio.")

        # Validar que la contrasena no este vacia.
        if not contrasena:
            raise ValueError("La contrasena es obligatoria.")

        # Validar longitud minima de contrasena (seguridad basica).
        # LONGITUD_MINIMA_CONTRASENA esta definido al inicio del archivo.
        if len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
            raise ValueError(
                f"La contrasena debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres."
            )

        # Hashear la contrasena antes de guardarla.
        # bcrypt.hashpw(): recibe la contrasena en bytes + una sal.
        # bcrypt.gensalt(): genera una sal aleatoria.
        # .decode("utf-8"): convertimos el hash de bytes a string para guardarlo.
        contrasena_hash = bcrypt.hashpw(
            contrasena.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        # Verificar si ya existe un usuario con ese nombre.
        with get_session() as session:
            existente = session.exec(select(Usuario).where(Usuario.usuario == usuario)).first()
            if existente:
                raise ValueError(f"El usuario '{usuario}' ya existe.")

            # Crear el objeto Usuario con la contrasena hasheada.
            nuevo = Usuario(
                usuario=usuario.strip().lower(),  # minusculas para uniformidad.
                contrasena=contrasena_hash,
                nombre_completo=nombre_completo.strip() if nombre_completo else None,
                activo=True,
                fecha_creacion=datetime.now(),
            )
            session.add(nuevo)
            session.commit()
            session.refresh(nuevo)

        return nuevo

    # ------------------------------------------------------------------
    # obtener_por_id(): busca un usuario por su ID
    # ------------------------------------------------------------------
    def obtener_por_id(self, id_usuario: int) -> Usuario | None:
        """Busca un usuario por su ID."""
        with get_session() as session:
            return session.get(Usuario, id_usuario)

    # ------------------------------------------------------------------
    # obtener_por_usuario(): busca un usuario por su nombre
    # ------------------------------------------------------------------
    def obtener_por_usuario(self, usuario: str) -> Usuario | None:
        """Busca un usuario por su nombre de usuario."""
        with get_session() as session:
            return session.exec(select(Usuario).where(Usuario.usuario == usuario)).first()

    # ------------------------------------------------------------------
    # listar_usuarios(): todos los usuarios del sistema
    # ------------------------------------------------------------------
    def listar_usuarios(self) -> list[Usuario]:
        """Devuelve todos los usuarios ordenados por nombre."""
        with get_session() as session:
            stmt = select(Usuario).order_by(Usuario.usuario)
            return list(session.exec(stmt).all())

    # ------------------------------------------------------------------
    # cambiar_contrasena(): actualiza la contrasena de un usuario
    # ------------------------------------------------------------------
    # Solo se puede cambiar si:
    #   - El usuario existe.
    #   - La contrasena actual es correcta (verificacion de seguridad).
    #   - La nueva contrasena cumple los requisitos minimos.
    #
    # Por que pedir la contrasena actual?
    #   - Seguridad: evita que alguien cambie la contrasena si
    #     deja la sesion abierta y alguien mas usa su computadora.
    # ------------------------------------------------------------------
    def cambiar_contrasena(
        self,
        id_usuario: int,
        contrasena_actual: str,
        nueva_contrasena: str,
    ) -> bool:
        """Cambia la contrasena de un usuario. Retorna False si la actual no coincide."""
        # Validar requisitos minimos.
        if len(nueva_contrasena) < LONGITUD_MINIMA_CONTRASENA:
            raise ValueError(
                f"La nueva contrasena debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres."
            )

        with get_session() as session:
            user = session.get(Usuario, id_usuario)
            if not user:
                return False

            # Verificar que la contrasena actual sea correcta.
            if not bcrypt.checkpw(
                contrasena_actual.encode("utf-8"),
                user.contrasena.encode("utf-8"),
            ):
                return False

            # Hashear la nueva contrasena y guardarla.
            nuevo_hash = bcrypt.hashpw(
                nueva_contrasena.encode("utf-8"),
                bcrypt.gensalt(),
            ).decode("utf-8")
            user.contrasena = nuevo_hash

            session.add(user)
            session.commit()

        return True

    # ------------------------------------------------------------------
    # cambiar_contrasena_admin(): cambio de contrasena sin verificar la actual
    # ------------------------------------------------------------------
    # Este metodo es SOLO para administradores. No pide la contrasena
    # actual porque un admin puede resetear la contrasena de cualquier usuario.
    #
    # Diferencia con cambiar_contrasena():
    #   - cambiar_contrasena() → el USUARIO cambia su propia contrasena (pide la actual).
    #   - cambiar_contrasena_admin() → el ADMIN resetea la contrasena de OTRO.
    # ------------------------------------------------------------------
    def cambiar_contrasena_admin(
        self,
        id_usuario: int,
        nueva_contrasena: str,
    ) -> bool:
        """Cambia la contrasena sin verificar la actual (solo admin)."""
        if len(nueva_contrasena) < LONGITUD_MINIMA_CONTRASENA:
            raise ValueError(
                f"La nueva contrasena debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres."
            )

        with get_session() as session:
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

    # ------------------------------------------------------------------
    # activar() / desactivar(): control de acceso al sistema
    # ------------------------------------------------------------------
    # Un usuario DESACTIVADO no puede iniciar sesion (verificar_login()
    # retorna None aunque la contrasena sea correcta).
    #
    # Esto es util cuando un empleado ya no trabaja aqui:
    #   - Se desactiva su usuario (no puede entrar).
    #   - NO se elimina (las ventas que hizo quedan vinculadas a su ID).
    # ------------------------------------------------------------------
    def activar(self, id_usuario: int) -> bool:
        """Activa un usuario. Retorna False si no existe."""
        with get_session() as session:
            user = session.get(Usuario, id_usuario)
            if not user:
                return False
            user.activo = True
            session.add(user)
            session.commit()
        return True

    def desactivar(self, id_usuario: int) -> bool:
        """Desactiva un usuario. Retorna False si no existe."""
        with get_session() as session:
            user = session.get(Usuario, id_usuario)
            if not user:
                return False
            user.activo = False
            session.add(user)
            session.commit()
        return True

    # ------------------------------------------------------------------
    # actualizar(): modificar datos de un usuario (sin contrasena)
    # ------------------------------------------------------------------
    def actualizar(
        self,
        id_usuario: int,
        usuario: str | None = None,
        nombre_completo: str | None = None,
    ) -> Usuario | None:
        """Actualiza los datos de un usuario (nombre, usuario)."""
        with get_session() as session:
            user = session.get(Usuario, id_usuario)
            if not user:
                return None

            if usuario is not None:
                # Verificar que el nuevo nombre no este en uso por OTRO usuario.
                existente = session.exec(
                    select(Usuario).where(
                        Usuario.usuario == usuario,
                        Usuario.id != id_usuario,
                    )
                ).first()
                if existente:
                    raise ValueError(f"El usuario '{usuario}' ya esta en uso.")
                user.usuario = usuario.strip().lower()

            if nombre_completo is not None:
                user.nombre_completo = nombre_completo.strip()

            session.add(user)
            session.commit()
            session.refresh(user)

        return user
