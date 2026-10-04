import logging
from collections.abc import Generator
from contextlib import contextmanager

import pytest
import pytest_mock
from PyQt6.QtWidgets import QDialog
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from sistema_financiero.__main__ import asegurar_administrador
from sistema_financiero.core.auth_service import AuthService
from sistema_financiero.models import Usuario
from sistema_financiero.utils import ROL_ADMINISTRADOR

pytestmark = pytest.mark.unitarias


# Prepara una BD en memoria y parchea obtener_sesion en los dos modulos que lo usan.
@pytest.fixture()
def engine_memoria(mocker: pytest_mock.MockerFixture) -> Engine:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    # Generador de sesiones sobre el engine de prueba.
    @contextmanager
    def _fake_obtener_sesion(session: Session | None = None) -> Generator[Session]:
        if session is not None:
            yield session
        else:
            with Session(engine) as s:
                yield s

    mocker.patch(
        "sistema_financiero.__main__.obtener_sesion",
        side_effect=_fake_obtener_sesion,
    )
    mocker.patch(
        "sistema_financiero.core.auth_service.obtener_sesion",
        side_effect=_fake_obtener_sesion,
    )
    return engine


# Crea un administrador de prueba a traves del AuthService real.
def _crear_admin_en_memoria(usuario: str = "admin") -> None:
    AuthService().crear_usuario(
        usuario=usuario,
        contrasena="clave_segura",
        rol=ROL_ADMINISTRADOR,
    )


# Base de los dobles: conserva el DialogCode real de QDialog.
class _DialogoBase:
    # __main__ compara contra DialogoPrimerUso.DialogCode.Accepted.
    DialogCode = QDialog.DialogCode


# Doble del dialogo que el operador acepta: crea el administrador al abrirse.
class _DialogoAcepta(_DialogoBase):
    # Simula la creacion del administrador y la aceptacion del dialogo.
    def exec(self) -> QDialog.DialogCode:
        _crear_admin_en_memoria()
        return QDialog.DialogCode.Accepted


# Doble del dialogo que el operador cancela: no crea nada.
class _DialogoCancela(_DialogoBase):
    # Simula el cierre del dialogo sin creacion.
    def exec(self) -> QDialog.DialogCode:
        return QDialog.DialogCode.Rejected


# No se abre el dialogo cuando ya existe algun usuario.
def test_no_abre_dialogo_si_ya_hay_usuarios(
    engine_memoria: Engine,
    mocker: pytest_mock.MockerFixture,
) -> None:
    _crear_admin_en_memoria()
    mock_clase = mocker.patch("sistema_financiero.__main__.DialogoPrimerUso")

    assert asegurar_administrador() is True
    mock_clase.assert_not_called()


# El administrador se crea cuando el dialogo se acepta.
def test_crea_admin_si_se_acepta_el_dialogo(
    engine_memoria: Engine,
    mocker: pytest_mock.MockerFixture,
) -> None:
    mocker.patch("sistema_financiero.__main__.DialogoPrimerUso", _DialogoAcepta)

    assert asegurar_administrador() is True

    with Session(engine_memoria) as session:
        admin = session.exec(select(Usuario).where(Usuario.usuario == "admin")).first()
        assert admin is not None
        assert admin.rol == ROL_ADMINISTRADOR
        assert admin.activo is True


# Cancelar el dialogo devuelve False y no crea ningun usuario.
def test_falla_si_se_cancela_el_dialogo(
    engine_memoria: Engine,
    mocker: pytest_mock.MockerFixture,
) -> None:
    mocker.patch("sistema_financiero.__main__.DialogoPrimerUso", _DialogoCancela)

    assert asegurar_administrador() is False

    with Session(engine_memoria) as session:
        assert session.exec(select(Usuario)).first() is None


# Cancelar el dialogo deja rastro en la auditoria.
def test_registra_evento_de_cancelacion(
    engine_memoria: Engine,
    mocker: pytest_mock.MockerFixture,
) -> None:
    mocker.patch("sistema_financiero.__main__.DialogoPrimerUso", _DialogoCancela)
    mock_evento = mocker.patch("sistema_financiero.__main__.registrar_evento")

    assert asegurar_administrador() is False

    mock_evento.assert_called_once_with(
        logging.INFO,
        "Primer inicio cancelado: no se creo el administrador.",
    )


# Aceptar el dialogo no deja rastro de cancelacion.
def test_no_registra_cancelacion_si_el_dialogo_acepta(
    engine_memoria: Engine,
    mocker: pytest_mock.MockerFixture,
) -> None:
    mocker.patch("sistema_financiero.__main__.DialogoPrimerUso", _DialogoAcepta)
    mock_evento = mocker.patch("sistema_financiero.__main__.registrar_evento")

    assert asegurar_administrador() is True

    mock_evento.assert_not_called()
