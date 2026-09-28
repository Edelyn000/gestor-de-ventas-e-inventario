
from collections.abc import Generator

import pytest
from sqlmodel import Session, SQLModel, create_engine

from sistema_financiero.core.auth_service import AuthService
from sistema_financiero.core.inventario_service import InventarioService
from sistema_financiero.core.producto_controller import ProductoController
from sistema_financiero.core.reporte_service import ReporteService
from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.core.venta_controller import VentaController


@pytest.fixture()
def session() -> Generator[Session]:
    """Crea una BD SQLite en memoria y todas las tablas para pruebas."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    SQLModel.metadata.create_all(engine)

    with Session(engine) as sesion:
        yield sesion


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

