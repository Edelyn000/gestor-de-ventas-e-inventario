
import bcrypt
import pytest
from sqlmodel import Session

from sistema_financiero.core.auth_service import AuthService
from sistema_financiero.models import Usuario

pytestmark = pytest.mark.unitarias


def test_crear_usuario_exitoso(session: Session) -> None:
    """
    Prueba que crear_usuario() cree un usuario correctamente
    y que la contrasena se guarde hasheada (no en texto plano).
    """
    servicio = AuthService()

    resultado = servicio.crear_usuario(
        usuario="testuser",
        contrasena="secreta123",
        nombre_completo="Usuario de Prueba",
        db_session=session,
    )


    assert isinstance(resultado, Usuario), "El resultado debe ser un Usuario"

    assert resultado.id is not None, "El usuario debe tener un ID asignado"

    assert resultado.usuario == "testuser", "El nombre de usuario debe ser 'testuser'"

    assert resultado.nombre_completo == "Usuario de Prueba"

    assert bcrypt.checkpw(
        b"secreta123",
        resultado.contrasena.encode("utf-8"),
    ), "La contrasena debe coincidir con el hash guardado"

    assert resultado.activo is True, "El usuario debe estar activo por defecto"

    assert resultado.fecha_creacion is not None, "Debe tener fecha de creacion"


def test_crear_usuario_duplicado(session: Session) -> None:
    """Prueba que NO se pueda crear un usuario con el mismo nombre."""
    servicio = AuthService()

    servicio.crear_usuario(usuario="duplicado", contrasena="secreta123", db_session=session)

    with pytest.raises(ValueError) as exc_info:
        servicio.crear_usuario(usuario="duplicado", contrasena="otra123", db_session=session)

    assert "duplicado" in str(exc_info.value), "El mensaje debe mencionar el usuario duplicado"


def test_crear_usuario_contrasena_corta(session: Session) -> None:
    """Prueba que se rechace una contrasena con menos de 4 caracteres."""
    servicio = AuthService()

    with pytest.raises(ValueError) as exc_info:
        servicio.crear_usuario(usuario="usuario_valido", contrasena="ab", db_session=session)

    assert "4 caracteres" in str(exc_info.value)


def test_crear_usuario_sin_nombre(session: Session) -> None:
    """Prueba que se rechace un usuario con nombre vacio."""
    servicio = AuthService()

    with pytest.raises(ValueError) as exc_info:
        servicio.crear_usuario(usuario="", contrasena="secreta123", db_session=session)

    assert "obligatorio" in str(exc_info.value)


def test_verificar_login_exitoso(session: Session) -> None:
    """Prueba que verificar_login() retorne el Usuario si las credenciales son correctas."""
    servicio = AuthService()

    servicio.crear_usuario(
        usuario="loginuser", contrasena="miclave", nombre_completo="Login Test", db_session=session
    )

    resultado = servicio.verificar_login(
        usuario="loginuser", contrasena="miclave", db_session=session
    )

    assert resultado is not None, "El login debe ser exitoso"

    assert resultado is not None
    assert resultado.usuario == "loginuser"
    assert resultado.nombre_completo == "Login Test"


def test_verificar_login_contrasena_incorrecta(session: Session) -> None:
    """Prueba que el login falle si la contrasena no coincide."""
    servicio = AuthService()

    servicio.crear_usuario(usuario="userpass", contrasena="correcta", db_session=session)

    resultado = servicio.verificar_login(
        usuario="userpass", contrasena="incorrecta", db_session=session
    )

    assert resultado is None, "El login debe fallar con contrasena incorrecta"


def test_verificar_login_usuario_inexistente(session: Session) -> None:
    """Prueba que el login falle si el usuario no existe en la BD."""
    servicio = AuthService()

    resultado = servicio.verificar_login(
        usuario="noexisto", contrasena="cualquiera", db_session=session
    )

    assert resultado is None, "El login debe fallar para usuario inexistente"


def test_verificar_login_usuario_inactivo(session: Session) -> None:
    """Prueba que un usuario desactivado NO pueda iniciar sesion."""
    servicio = AuthService()

    creado = servicio.crear_usuario(usuario="inactivo", contrasena="clave123", db_session=session)
    assert creado.id is not None

    servicio.desactivar(creado.id, db_session=session)

    resultado = servicio.verificar_login(
        usuario="inactivo", contrasena="clave123", db_session=session
    )

    assert resultado is None, "Usuario inactivo NO debe poder iniciar sesion"


def test_cambiar_contrasena_exitoso(session: Session) -> None:
    """
    Prueba cambiar_contrasena(): debe cambiar la contrasena si
    la contrasena actual es correcta.
    """
    servicio = AuthService()

    usuario = servicio.crear_usuario(usuario="change", contrasena="vieja123", db_session=session)
    assert usuario.id is not None

    resultado = servicio.cambiar_contrasena(
        id_usuario=usuario.id,
        contrasena_actual="vieja123",
        nueva_contrasena="nueva456",
        db_session=session,
    )

    assert resultado is True, "El cambio de contrasena debe retornar True"

    login = servicio.verificar_login(usuario="change", contrasena="nueva456", db_session=session)
    assert login is not None, "Debe poder iniciar sesion con la nueva contrasena"

    login_viejo = servicio.verificar_login(
        usuario="change", contrasena="vieja123", db_session=session
    )
    assert login_viejo is None, "La contrasena antigua ya no debe funcionar"


def test_cambiar_contrasena_admin(session: Session) -> None:
    """
    Prueba cambiar_contrasena_admin(): debe cambiar la contrasena
    sin pedir la contrasena actual.
    """
    servicio = AuthService()

    usuario = servicio.crear_usuario(usuario="target", contrasena="original", db_session=session)
    assert usuario.id is not None

    resultado = servicio.cambiar_contrasena_admin(
        id_usuario=usuario.id, nueva_contrasena="reseteada", db_session=session
    )

    assert resultado is True, "El cambio admin debe retornar True"

    login = servicio.verificar_login(usuario="target", contrasena="reseteada", db_session=session)
    assert login is not None, "Debe poder iniciar sesion con la contrasena reseteada"


def test_activar_desactivar_usuario(session: Session) -> None:
    """Prueba activar() y desactivar(): control de acceso al sistema."""
    servicio = AuthService()

    usuario = servicio.crear_usuario(usuario="toggle", contrasena="clave", db_session=session)
    assert usuario.id is not None

    assert usuario.activo is True

    resultado_des = servicio.desactivar(usuario.id, db_session=session)
    assert resultado_des is True, "desactivar() debe retornar True"

    usuario_recargado = servicio.obtener_por_id(usuario.id, db_session=session)
    assert usuario_recargado is not None
    assert usuario_recargado.activo is False, "El usuario debe estar inactivo"

    resultado_act = servicio.activar(usuario.id, db_session=session)
    assert resultado_act is True, "activar() debe retornar True"

    usuario_recargado2 = servicio.obtener_por_id(usuario.id, db_session=session)
    assert usuario_recargado2 is not None
    assert usuario_recargado2.activo is True, "El usuario debe estar activo nuevamente"


def test_desactivar_usuario_inexistente(session: Session) -> None:
    """Prueba que desactivar() retorne False para un ID inexistente."""
    servicio = AuthService()

    resultado = servicio.desactivar(9999, db_session=session)
    assert resultado is False, "Debe retornar False para usuario inexistente"


def test_obtener_por_id_exitoso(session: Session) -> None:
    """Prueba que obtener_por_id() retorne el Usuario correcto."""
    servicio = AuthService()

    creado = servicio.crear_usuario(usuario="buscarporid", contrasena="clave", db_session=session)
    assert creado.id is not None

    resultado = servicio.obtener_por_id(creado.id, db_session=session)

    assert resultado is not None
    assert resultado.usuario == "buscarporid"


def test_obtener_por_id_inexistente(session: Session) -> None:
    """Prueba que obtener_por_id() retorne None para un ID que no existe."""
    servicio = AuthService()

    resultado = servicio.obtener_por_id(9999, db_session=session)
    assert resultado is None, "Debe retornar None para ID inexistente"


def test_obtener_por_usuario(session: Session) -> None:
    """Prueba que obtener_por_usuario() encuentre un usuario por su nombre."""
    servicio = AuthService()

    servicio.crear_usuario(usuario="buscar", contrasena="clave", db_session=session)

    resultado = servicio.obtener_por_usuario("buscar", db_session=session)
    assert resultado is not None
    assert resultado.usuario == "buscar"

    no_encontrado = servicio.obtener_por_usuario("noexiste", db_session=session)
    assert no_encontrado is None


def test_listar_usuarios(session: Session) -> None:
    """Prueba que listar_usuarios() devuelva todos los usuarios creados."""
    servicio = AuthService()

    servicio.crear_usuario(usuario="alpha", contrasena="clave1", db_session=session)
    servicio.crear_usuario(usuario="beta", contrasena="clave2", db_session=session)
    servicio.crear_usuario(usuario="gamma", contrasena="clave3", db_session=session)

    lista = servicio.listar_usuarios(db_session=session)

    minimo_usuarios = 3
    assert len(lista) >= minimo_usuarios
    nombres = [u.usuario for u in lista]
    assert "alpha" in nombres
    assert "beta" in nombres
    assert "gamma" in nombres


def test_actualizar_usuario(session: Session) -> None:
    """Prueba que actualizar() modifique los datos de un usuario."""
    servicio = AuthService()

    usuario = servicio.crear_usuario(
        usuario="original",
        contrasena="clave",
        nombre_completo="Nombre Original",
        db_session=session,
    )
    assert usuario.id is not None

    actualizado = servicio.actualizar(
        id_usuario=usuario.id,
        usuario="modificado",
        nombre_completo="Nombre Modificado",
        db_session=session,
    )

    assert actualizado is not None
    assert actualizado.usuario == "modificado"
    assert actualizado.nombre_completo == "Nombre Modificado"


def test_actualizar_usuario_duplicado(session: Session) -> None:
    """Prueba que actualizar() lance error si el nuevo nombre ya esta en uso."""
    servicio = AuthService()

    servicio.crear_usuario(usuario="usuario1", contrasena="clave1", db_session=session)
    usuario2 = servicio.crear_usuario(usuario="usuario2", contrasena="clave2", db_session=session)
    assert usuario2.id is not None

    with pytest.raises(ValueError) as exc_info:
        servicio.actualizar(id_usuario=usuario2.id, usuario="usuario1", db_session=session)

    assert "usuario1" in str(exc_info.value) or "ya existe" in str(exc_info.value)

