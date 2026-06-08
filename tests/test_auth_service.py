# ============================================================
# ARCHIVO: tests/test_auth_service.py
# Pruebas para el servicio de autenticacion (AuthService).
#
# 👉 ¿QUE ES UN TEST?
# Un test es una funcion que:
#   1. PREPARA datos (ej: crea un usuario).
#   2. EJECUTA la funcion que queremos probar (ej: verificar_login).
#   3. VERIFICA que el resultado sea el esperado (ej: assert ...).
#
# 👉 ¿QUE ES "assert"?
# "assert" significa "afirmar/asegurar". Es una palabra clave de Python
# que lanza un error si la condicion que le pasas es FALSA.
#   assert 1 + 1 == 2   → pasa (no hace nada).
#   assert 1 + 1 == 3   → ERROR: AssertionError.
# En los tests, assert es nuestra manera de decir:
#   "Esto DEBERIA ser verdad. Si no lo es, el test falla."
#
# 👉 ¿POR QUE USAR "from datetime import datetime"?
# datetime es la clase de Python para fechas con hora.
#   datetime.now() → devuelve la fecha y hora actual.
# La necesitamos para crear objetos como Venta que requieren
# una fecha (ej: fecha_venta=datetime.now()).
# ============================================================

# Importamos datetime para crear fechas en los objetos de prueba.
from datetime import datetime

# Importamos bcrypt para hashear contrasenas en los tests.
# bcrypt.hashpw(): hashea una contrasena.
# bcrypt.checkpw(): verifica una contrasena contra un hash.
import bcrypt
# Importamos pytest para usar sus herramientas (ej: pytest.raises).
import pytest

# Importamos el servicio que vamos a probar.
from sistema_financiero.core.auth_service import AuthService
# Importamos el modelo Usuario para crear datos de prueba.
from sistema_financiero.models import Usuario
# Importamos select de SQLModel para hacer consultas.
from sqlmodel import select


# ============================================================
# TEST: test_crear_usuario_exitoso
# ¿QUE PRUEBA? Que crear_usuario() funciona correctamente.
# ¿QUE VERIFICA?
#   - Que el usuario se crea con los datos proporcionados.
#   - Que el ID es distinto de None (significa que se guardo en BD).
#   - Que el nombre de usuario se guardo en minusculas.
#   - Que la contrasena esta hasheada (NUNCA en texto plano).
#   - Que el usuario esta activo por defecto.
#   - Que fecha_creacion no es None.
# ============================================================

# "def test_..." → pytest busca funciones que empiecen con "test_".
# "session" es un FIXTURE (definido en conftest.py).
# pytest ve el parametro "session", busca un fixture con ese nombre,
# lo ejecuta, y pasa el resultado (una sesion de BD) al test.


def test_crear_usuario_exitoso(session):  # type: ignore[no-untyped-def]
    """
    Prueba que crear_usuario() cree un usuario correctamente
    y que la contrasena se guarde hasheada (no en texto plano).
    """
    # ----------------------------------------------------------
    # PASO 1: Crear una instancia del servicio.
    # ----------------------------------------------------------
    # AuthService() no necesita parametros (usa get_session() internamente).
    # ⚠️ OJO: Como no le pasamos nuestra sesion de prueba, este servicio
    #   usara get_session() que apunta a la BD REAL database.db.
    #   Esto es una limitacion actual del diseno.
    #   Por ahora probamos la logica de hashing y validaciones.
    servicio = AuthService()

    # ----------------------------------------------------------
    # PASO 2: Ejecutar la funcion que queremos probar.
    # ----------------------------------------------------------
    # crear_usuario() recibe: (usuario, contrasena, nombre_completo opcional).
    # Retorna el objeto Usuario recien creado.
    resultado = servicio.crear_usuario(
        usuario="testuser",
        contrasena="secreta123",
        nombre_completo="Usuario de Prueba",
        db_session=session)

    # ----------------------------------------------------------
    # PASO 3: Verificar los resultados con assert.
    # ----------------------------------------------------------

    # assert + isinstance(): verifica que el resultado sea un Usuario.
    # isinstance(objeto, Clase) → True si objeto es instancia de Clase.
    assert isinstance(resultado, Usuario), "El resultado debe ser un Usuario"

    # assert + is not None: verifica que tenga ID (se guardo en BD).
    assert resultado.id is not None, "El usuario debe tener un ID asignado"

    # assert + ==: verifica que el nombre sea exactamente el que enviamos.
    # NOTA: el servicio convierte a minusculas automaticamente.
    assert resultado.usuario == "testuser", "El nombre de usuario debe ser 'testuser'"

    # assert + ==: verifica el nombre completo.
    assert resultado.nombre_completo == "Usuario de Prueba"

    # ----------------------------------------------------------
    # VERIFICACION CLAVE: la contrasena NO debe estar en texto plano.
    # ----------------------------------------------------------
    # bcrypt.checkpw(contrasena_original_en_bytes, hash_guardado_en_str)
    # retorna True si la contrasena coincide con el hash.
    # Si la contrasena estuviera en texto plano, esto fallaria.
    assert bcrypt.checkpw(
        b"secreta123",
        resultado.contrasena.encode("utf-8"),
    ), "La contrasena debe coincidir con el hash guardado"

    # Verificar que el usuario este activo (por defecto).
    assert resultado.activo is True, "El usuario debe estar activo por defecto"

    # Verificar que la fecha de creacion se haya registrado.
    assert resultado.fecha_creacion is not None, "Debe tener fecha de creacion"


# ============================================================
# TEST: test_crear_usuario_duplicado
# ¿QUE PRUEBA? Que NO se pueda crear un usuario con el mismo nombre.
# ¿QUE VERIFICA? Que se lance un ValueError con el mensaje adecuado.
# ============================================================

# "pytest.raises(ValueError)" es un CONTEXTO (with ...).
# Significa: "Esperamos que el codigo DENTRO de este bloque lance
# una excepcion ValueError. Si NO la lanza, el test FALLA."
# Esto es util para probar que las VALIDACIONES funcionan.


def test_crear_usuario_duplicado(session):  # type: ignore[no-untyped-def]
    """
    Prueba que NO se pueda crear un usuario con el mismo nombre.
    Debe lanzar ValueError con el mensaje adecuado.
    """
    servicio = AuthService()

    # Crear el primer usuario (deberia funcionar).
    servicio.crear_usuario(usuario="duplicado", contrasena="secreta123", db_session=session)

    # Intentar crear otro usuario con el MISMO nombre.
    # "with pytest.raises(ValueError) as exc_info:" captura la excepcion.
    #   - Si NO hay excepcion → test FALLA.
    #   - Si hay ValueError → la guarda en exc_info para examinarla.
    with pytest.raises(ValueError) as exc_info:
        servicio.crear_usuario(usuario="duplicado", contrasena="otra123", db_session=session)

    # Verificar que el mensaje de error contenga el nombre del usuario.
    # exc_info.value es la excepcion que se lanzo.
    # "in" verifica si un string esta DENTRO de otro.
    assert "duplicado" in str(exc_info.value), "El mensaje debe mencionar el usuario duplicado"


# ============================================================
# TEST: test_crear_usuario_contrasena_corta
# ¿QUE PRUEBA? Que se valide la longitud minima de la contrasena.
# ============================================================
def test_crear_usuario_contrasena_corta(session):  # type: ignore[no-untyped-def]
    """
    Prueba que se rechace una contrasena con menos de 4 caracteres.
    La constante LONGITUD_MINIMA_CONTRASENA esta definida en auth_service.py.
    """
    servicio = AuthService()

    # "as exc_info" guarda la excepcion para examinarla.
    with pytest.raises(ValueError) as exc_info:
        servicio.crear_usuario(usuario="usuario_valido", contrasena="ab", db_session=session)

    # Verificar que el mensaje mencione la longitud minima.
    assert "4 caracteres" in str(exc_info.value)


# ============================================================
# TEST: test_crear_usuario_sin_nombre
# ¿QUE PRUEBA? Que el nombre de usuario sea obligatorio.
# ============================================================
def test_crear_usuario_sin_nombre(session):  # type: ignore[no-untyped-def]
    """
    Prueba que se rechace un usuario con nombre vacio.
    """
    servicio = AuthService()

    with pytest.raises(ValueError) as exc_info:
        # Nombre vacio deberia lanzar error.
        servicio.crear_usuario(usuario="", contrasena="secreta123", db_session=session)

    assert "obligatorio" in str(exc_info.value)


# ============================================================
# TEST: test_verificar_login_exitoso
# ¿QUE PRUEBA? Que un usuario pueda iniciar sesion con credenciales correctas.
# ¿QUE VERIFICA? Que retorne el objeto Usuario (no None).
# ============================================================
def test_verificar_login_exitoso(session):  # type: ignore[no-untyped-def]
    """
    Prueba que verificar_login() retorne el Usuario si las
    credenciales son correctas.
    """
    servicio = AuthService()

    # Primero crear un usuario.
    servicio.crear_usuario(usuario="loginuser", contrasena="miclave", nombre_completo="Login Test", db_session=session)

    # Ahora intentar el login con las mismas credenciales.
    resultado = servicio.verificar_login(usuario="loginuser", contrasena="miclave", db_session=session)

    # El resultado NO debe ser None (login exitoso).
    assert resultado is not None, "El login debe ser exitoso"

    # Verificar que sea el usuario correcto.
    assert resultado is not None
    assert resultado.usuario == "loginuser"
    assert resultado.nombre_completo == "Login Test"


# ============================================================
# TEST: test_verificar_login_contrasena_incorrecta
# ¿QUE PRUEBA? Que login falle si la contrasena es incorrecta.
# ¿QUE VERIFICA? Que retorne None (no el usuario).
# ============================================================
def test_verificar_login_contrasena_incorrecta(session):  # type: ignore[no-untyped-def]
    """
    Prueba que el login falle si la contrasena no coincide.
    """
    servicio = AuthService()

    # Crear usuario con contrasena conocida.
    servicio.crear_usuario(usuario="userpass", contrasena="correcta", db_session=session)

    # Intentar login con contrasena INCORRECTA.
    resultado = servicio.verificar_login(usuario="userpass", contrasena="incorrecta", db_session=session)

    # Debe retornar None (login fallido).
    assert resultado is None, "El login debe fallar con contrasena incorrecta"


# ============================================================
# TEST: test_verificar_login_usuario_inexistente
# ¿QUE PRUEBA? Que login falle si el usuario no existe.
# ============================================================
def test_verificar_login_usuario_inexistente(session):  # type: ignore[no-untyped-def]
    """
    Prueba que el login falle si el usuario no existe en la BD.
    """
    servicio = AuthService()

    # Intentar login con un usuario que NUNCA fue creado.
    resultado = servicio.verificar_login(usuario="noexisto", contrasena="cualquiera", db_session=session)

    # Debe retornar None (usuario no encontrado).
    assert resultado is None, "El login debe fallar para usuario inexistente"


# ============================================================
# TEST: test_verificar_login_usuario_inactivo
# ¿QUE PRUEBA? Que un usuario DESACTIVADO no pueda iniciar sesion.
# ============================================================
def test_verificar_login_usuario_inactivo(session):  # type: ignore[no-untyped-def]
    """
    Prueba que un usuario desactivado NO pueda iniciar sesion.
    """
    servicio = AuthService()

    # Crear un usuario.
    creado = servicio.crear_usuario(usuario="inactivo", contrasena="clave123", db_session=session)

    # Desactivarlo.
    servicio.desactivar(creado.id, db_session=session)  # type: ignore[union-attr]

    # Intentar login con el usuario desactivado.
    resultado = servicio.verificar_login(usuario="inactivo", contrasena="clave123", db_session=session)

    # Debe retornar None aunque la contrasena sea correcta.
    assert resultado is None, "Usuario inactivo NO debe poder iniciar sesion"


# ============================================================
# TEST: test_cambiar_contrasena_exitoso
# ¿QUE PRUEBA? Que un usuario pueda cambiar su propia contrasena.
# ============================================================
def test_cambiar_contrasena_exitoso(session):  # type: ignore[no-untyped-def]
    """
    Prueba cambiar_contrasena(): debe cambiar la contrasena si
    la contrasena actual es correcta.
    """
    servicio = AuthService()

    # Crear usuario.
    usuario = servicio.crear_usuario(usuario="change", contrasena="vieja123", db_session=session)

    # Cambiar contrasena: necesita (id, contrasena_actual, nueva_contrasena).
    resultado = servicio.cambiar_contrasena(
        id_usuario=usuario.id,  # type: ignore[arg-type]
        contrasena_actual="vieja123",
        nueva_contrasena="nueva456",
        db_session=session)

    # Debe retornar True (cambio exitoso).
    assert resultado is True, "El cambio de contrasena debe retornar True"

    # Verificar que la NUEVA contrasena funcione para login.
    login = servicio.verificar_login(usuario="change", contrasena="nueva456", db_session=session)
    assert login is not None, "Debe poder iniciar sesion con la nueva contrasena"

    # Verificar que la VIEJA contrasena YA NO funcione.
    login_viejo = servicio.verificar_login(usuario="change", contrasena="vieja123", db_session=session)
    assert login_viejo is None, "La contrasena antigua ya no debe funcionar"


# ============================================================
# TEST: test_cambiar_contrasena_admin
# ¿QUE PRUEBA? Que un admin pueda cambiar la contrasena de otro usuario
# SIN conocer su contrasena actual.
# ============================================================
def test_cambiar_contrasena_admin(session):  # type: ignore[no-untyped-def]
    """
    Prueba cambiar_contrasena_admin(): debe cambiar la contrasena
    sin pedir la contrasena actual.
    """
    servicio = AuthService()

    usuario = servicio.crear_usuario(usuario="target", contrasena="original", db_session=session)

    # Admin cambia la contrasena sin saber la actual.
    resultado = servicio.cambiar_contrasena_admin(
        id_usuario=usuario.id,  # type: ignore[arg-type]
        nueva_contrasena="reseteada",
        db_session=session)

    assert resultado is True, "El cambio admin debe retornar True"

    # Login con la nueva contrasena debe funcionar.
    login = servicio.verificar_login(usuario="target", contrasena="reseteada", db_session=session)
    assert login is not None, "Debe poder iniciar sesion con la contrasena reseteada"


# ============================================================
# TEST: test_activar_desactivar_usuario
# ¿QUE PRUEBA? Las funciones activar() y desactivar().
# ============================================================
def test_activar_desactivar_usuario(session):  # type: ignore[no-untyped-def]
    """
    Prueba activar() y desactivar(): control de acceso al sistema.
    """
    servicio = AuthService()

    usuario = servicio.crear_usuario(usuario="toggle", contrasena="clave", db_session=session)

    # Verificar que este activo por defecto.
    assert usuario.activo is True

    # Desactivar.
    resultado_des = servicio.desactivar(usuario.id, db_session=session)  # type: ignore[arg-type]
    assert resultado_des is True, "desactivar() debe retornar True"

    # Verificar que ahora esta inactivo, recargando desde BD.
    usuario_recargado = servicio.obtener_por_id(usuario.id, db_session=session)  # type: ignore[arg-type]
    assert usuario_recargado is not None
    assert usuario_recargado.activo is False, "El usuario debe estar inactivo"

    # Activar de nuevo.
    resultado_act = servicio.activar(usuario.id, db_session=session)  # type: ignore[arg-type]
    assert resultado_act is True, "activar() debe retornar True"

    usuario_recargado2 = servicio.obtener_por_id(usuario.id, db_session=session)  # type: ignore[arg-type]
    assert usuario_recargado2 is not None
    assert usuario_recargado2.activo is True, "El usuario debe estar activo nuevamente"


# ============================================================
# TEST: test_desactivar_usuario_inexistente
# ¿QUE PRUEBA? Que desactivar() retorne False si el usuario no existe.
# ============================================================
def test_desactivar_usuario_inexistente(session):  # type: ignore[no-untyped-def]
    """
    Prueba que desactivar() retorne False para un ID inexistente.
    """
    servicio = AuthService()

    # Usar un ID que seguro no existe (ej: 9999).
    resultado = servicio.desactivar(9999, db_session=session)
    assert resultado is False, "Debe retornar False para usuario inexistente"


# ============================================================
# TEST: test_obtener_por_id_exitoso
# ¿QUE PRUEBA? Que obtener_por_id() encuentre un usuario existente.
# ============================================================
def test_obtener_por_id_exitoso(session):  # type: ignore[no-untyped-def]
    """
    Prueba que obtener_por_id() retorne el Usuario correcto.
    """
    servicio = AuthService()

    creado = servicio.crear_usuario(usuario="buscarporid", contrasena="clave", db_session=session)

    resultado = servicio.obtener_por_id(creado.id, db_session=session)  # type: ignore[arg-type]

    assert resultado is not None
    assert resultado.usuario == "buscarporid"


# ============================================================
# TEST: test_obtener_por_id_inexistente
# ¿QUE PRUEBA? Que obtener_por_id() retorne None si no existe.
# ============================================================
def test_obtener_por_id_inexistente(session):  # type: ignore[no-untyped-def]
    """
    Prueba que obtener_por_id() retorne None para un ID que no existe.
    """
    servicio = AuthService()

    resultado = servicio.obtener_por_id(9999, db_session=session)
    assert resultado is None, "Debe retornar None para ID inexistente"


# ============================================================
# TEST: test_obtener_por_usuario
# ¿QUE PRUEBA? La busqueda por nombre de usuario.
# ============================================================
def test_obtener_por_usuario(session):  # type: ignore[no-untyped-def]
    """
    Prueba que obtener_por_usuario() encuentre un usuario por su nombre.
    """
    servicio = AuthService()

    servicio.crear_usuario(usuario="buscar", contrasena="clave", db_session=session)

    resultado = servicio.obtener_por_usuario("buscar", db_session=session)
    assert resultado is not None
    assert resultado.usuario == "buscar"

    # Buscar usuario que no existe debe dar None.
    no_encontrado = servicio.obtener_por_usuario("noexiste", db_session=session)
    assert no_encontrado is None


# ============================================================
# TEST: test_listar_usuarios
# ¿QUE PRUEBA? Que listar_usuarios() devuelva todos los usuarios.
# ============================================================
def test_listar_usuarios(session):  # type: ignore[no-untyped-def]
    """
    Prueba que listar_usuarios() devuelva todos los usuarios creados.
    """
    servicio = AuthService()

    # Empezar sin usuarios (o solo admin si el fixture anterior lo creo).
    # Crear 3 usuarios.
    servicio.crear_usuario(usuario="alpha", contrasena="clave1", db_session=session)
    servicio.crear_usuario(usuario="beta", contrasena="clave2", db_session=session)
    servicio.crear_usuario(usuario="gamma", contrasena="clave3", db_session=session)

    lista = servicio.listar_usuarios(db_session=session)

    # Verificar que haya al menos 3 usuarios.
    # Usamos >= porque podria haber el admin de tests anteriores.
    # NOTA: Como los servicios usan la BD real y no nuestra session
    # de prueba, esto podria fallar. Es una limitacion actual.
    assert len(lista) >= 3
    # Verificar que esten ordenados alfabeticamente (alpha < beta < gamma).
    nombres = [u.usuario for u in lista]
    assert "alpha" in nombres
    assert "beta" in nombres
    assert "gamma" in nombres


# ============================================================
# TEST: test_actualizar_usuario
# ¿QUE PRUEBA? La funcion actualizar() que modifica nombre/usuario.
# ============================================================
def test_actualizar_usuario(session):  # type: ignore[no-untyped-def]
    """
    Prueba que actualizar() modifique los datos de un usuario.
    """
    servicio = AuthService()

    usuario = servicio.crear_usuario(
        usuario="original",
        contrasena="clave",
        nombre_completo="Nombre Original",
        db_session=session)

    # Actualizar el nombre de usuario.
    actualizado = servicio.actualizar(
        id_usuario=usuario.id,  # type: ignore[arg-type]
        usuario="modificado",
        nombre_completo="Nombre Modificado",
        db_session=session)

    assert actualizado is not None
    assert actualizado.usuario == "modificado"
    assert actualizado.nombre_completo == "Nombre Modificado"


# ============================================================
# TEST: test_actualizar_usuario_duplicado
# ¿QUE PRUEBA? Que actualizar() rechace nombres de usuario ya existentes.
# ============================================================
def test_actualizar_usuario_duplicado(session):  # type: ignore[no-untyped-def]
    """
    Prueba que actualizar() lance error si el nuevo nombre ya esta en uso.
    """
    servicio = AuthService()

    servicio.crear_usuario(usuario="usuario1", contrasena="clave1", db_session=session)
    usuario2 = servicio.crear_usuario(usuario="usuario2", contrasena="clave2", db_session=session)

    # Intentar cambiar usuario2 a "usuario1" (ya existe).
    with pytest.raises(ValueError) as exc_info:
        servicio.actualizar(
            id_usuario=usuario2.id,  # type: ignore[arg-type]
        usuario="usuario1",
        db_session=session)

    assert "usuario1" in str(exc_info.value) or "ya existe" in str(exc_info.value)
