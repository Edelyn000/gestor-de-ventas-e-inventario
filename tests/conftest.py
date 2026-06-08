# ============================================================
# ARCHIVO: tests/conftest.py
# 👉 "conftest" viene de "config of test" (configuracion de pruebas).
# Es un archivo ESPECIAL de pytest: se ejecuta AUTOMATICAMENTE
# antes de cada prueba sin necesidad de importarlo.
#
# ✅ QUE HACE:
#   - Crea una base de datos EN MEMORIA (mas rapida y aislada).
#   - Crea todas las tablas de la BD antes de cada prueba.
#   - Proporciona "fixtures" (funciones reutilizables) para los tests.
#
# 📌 FIXTURES (accesorios de prueba):
#   Un fixture es UNA FUNCION que pytest ejecuta y cuyo resultado
#   INYECTA automaticamente como parametro a tu test.
#   Ejemplo: def test_algo(session, auth_service):
#                ^^^^^^^  ^^^^^^^^^^^^^^^^
#                El test         ↑ pytest ve que "session" es un
#                normal          fixture, lo ejecuta, y pasa el
#                                resultado como argumento.
#
# 📌 POR QUE UNA BD EN MEMORIA?
#   - Rapida: no escribe en disco.
#   - Aislada: cada prueba empieza limpia (sin datos de otra prueba).
#   - Segura: si algo sale mal, no afecta la BD real database.db.
#
# 📌 POR QUE "yield" y no "return"?
#   "yield" divide el fixture en dos partes:
#     - Lo de ARRIBA del yield = SETUP (preparar).
#     - Lo de ABAJO del yield = TEARDOWN (limpiar despues del test).
#   En nuestro caso, el teardown no hace nada especial porque la BD
#   en memoria se destruye automaticamente al salir de "with".
# ============================================================

# Importamos pytest (el framework de pruebas).
import pytest

# Importamos tipos de SQLModel para crear la BD en memoria.
#   - Session: permite hacer consultas y transacciones.
#   - SQLModel: tiene la configuracion de todas las tablas.
#   - create_engine: crea el motor de BD (en este caso, en memoria).
from sqlmodel import Session, SQLModel, create_engine

# Importamos los servicios que vamos a probar.
# NOTA: importamos las CLASES (no instancias) para que cada test
# pueda crear su propia instancia con datos frescos.
from sistema_financiero.core.auth_service import AuthService
from sistema_financiero.core.inventario_service import InventarioService
from sistema_financiero.core.producto_controller import ProductoController
from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.core.venta_controller import VentaController
from sistema_financiero.core.reporte_service import ReporteService

# Importamos los modelos ORM para crear datos de prueba.
from sistema_financiero.models import (
    MovimientoInventario,
    Producto,
    ReporteDiario,
    TasaCambio,
    Usuario,
    Venta,
    VentaDetalle,
)


# ============================================================
# FIXTURE: session
# Proposito: Proporciona una BD en memoria limpia para cada test.
#
# Uso en tests:
#   def test_algo(session):
#       session.exec(select(Usuario)).all()
#
# Explicacion paso a paso:
#   1. Creamos un motor SQLite en memoria (":memory:").
#   2. Creamos TODAS las tablas definidas en modelos.py.
#   3. Abrimos una sesion y la cedemos al test con "yield".
#   4. Cuando el test termina, salimos del "with" y se cierra la BD.
# ============================================================
@pytest.fixture()
def session():
    """Crea una BD SQLite en memoria y todas las tablas para pruebas."""
    # "check_same_thread=False": necesario porque pytest puede
    # ejecutar tests en paralelo (aunque no lo hacemos aqui).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    # SQLModel.metadata.create_all() examina TODOS los modelos
    # que heredan de SQLModel(table=True) y crea sus tablas.
    # Es lo mismo que hace create_db_and_tables() en la app real.
    SQLModel.metadata.create_all(engine)

    # "with Session(engine):" crea una sesion y al salir del
    # bloque se cierra automaticamente.
    with Session(engine) as sesion:
        # "yield sesion" envia la sesion al test.
        # Cuando el test termina, el codigo CONTINUA desde aqui.
        yield sesion


# ============================================================
# FIXTURE: producto_controller
# Proposito: Inyecta una instancia de ProductoController lista para usar.
#
# Los controladores/servicios NO reciben la sesion en su constructor.
# En su lugar, cada metodo abre su propia sesion con get_session().
# Para pruebas, seria mejor inyectarles la sesion de prueba,
# pero por ahora los usamos tal cual (eso significa que operaran
# sobre la BD REAL database.db si no tenemos cuidado).
#
# ⚠️ IMPORTANTE:
#   Para que estos tests funcionen SIN tocar la BD real,
#   idealmente deberiamos refactorizar los servicios para aceptar
#   una sesion opcional. Por ahora, estos tests prueban la LOGICA
#   de las funciones principalmente.
# ============================================================
@pytest.fixture()
def producto_controller() -> ProductoController:
    """Devuelve un ProductoController listo para usar."""
    return ProductoController()


@pytest.fixture()
def inventario_service() -> InventarioService:
    """Devuelve un InventarioService listo para usar."""
    return InventarioService()


@pytest.fixture()
def auth_service() -> AuthService:
    """Devuelve un AuthService listo para usar."""
    return AuthService()


@pytest.fixture()
def tasa_cambio_service() -> TasaCambioService:
    """Devuelve un TasaCambioService listo para usar."""
    return TasaCambioService()


@pytest.fixture()
def venta_controller() -> VentaController:
    """Devuelve un VentaController listo para usar."""
    return VentaController()


@pytest.fixture()
def reporte_service() -> ReporteService:
    """Devuelve un ReporteService listo para usar."""
    return ReporteService()
