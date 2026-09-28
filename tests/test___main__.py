from collections.abc import Generator
from contextlib import contextmanager

import bcrypt
import pytest
import pytest_mock
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from sistema_financiero.db.seeds import seed_admin
from sistema_financiero.models import Usuario

pytestmark = pytest.mark.unitarias


@pytest.fixture()
def _mock_obtener_sesion(mocker: pytest_mock.MockerFixture) -> Engine:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    @contextmanager
    def _fake_obtener_sesion(session: Session | None = None) -> Generator[Session]:
        if session is not None:
            yield session
        else:
            with Session(engine) as s:
                yield s

    mocker.patch(
        "sistema_financiero.db.seeds.obtener_sesion",
        side_effect=_fake_obtener_sesion,
    )
    return engine


def test_seed_admin_crea_admin(_mock_obtener_sesion: Engine) -> None:
    with Session(_mock_obtener_sesion) as session:
        assert session.exec(select(Usuario)).first() is None

    seed_admin()

    with Session(_mock_obtener_sesion) as session:
        admin = session.exec(select(Usuario).where(Usuario.usuario == "admin")).first()
        assert admin is not None
        assert admin.usuario == "admin"
        assert admin.nombre_completo == "Administrador"
        assert admin.activo is True
        assert bcrypt.checkpw(b"admin", admin.contrasena.encode("utf-8"))


def test_seed_admin_no_duplica(_mock_obtener_sesion: Engine) -> None:
    with Session(_mock_obtener_sesion) as session:
        admin = Usuario(
            usuario="admin",
            contrasena=bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode("utf-8"),
            nombre_completo="Admin",
            activo=True,
        )
        session.add(admin)
        session.commit()

    seed_admin()

    with Session(_mock_obtener_sesion) as session:
        admins = session.exec(select(Usuario).where(Usuario.usuario == "admin")).all()
        assert len(admins) == 1

