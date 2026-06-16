"""Pruebas para __main__.py — entrypoint de la aplicacion.

Prueba _seed_admin() que crea el usuario admin por defecto.
main() no se prueba directamente porque crea QApplication."""
import bcrypt
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from sistema_financiero.models import Usuario


@pytest.fixture()
def _mock_get_session(mocker):
    """Reemplaza get_session() para usar BD en memoria."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    def _fake_get_session():
        return Session(engine)

    mocker.patch(
        "sistema_financiero.__main__.get_session",
        side_effect=_fake_get_session,
    )
    return engine


def test_seed_admin_crea_admin(_mock_get_session):
    """_seed_admin() crea el usuario admin/admin cuando la BD esta vacia."""
    from sistema_financiero.__main__ import _seed_admin  # noqa: PLC0415

    with Session(_mock_get_session) as session:
        assert session.exec(select(Usuario)).first() is None

    _seed_admin()

    with Session(_mock_get_session) as session:
        admin = session.exec(select(Usuario).where(Usuario.usuario == "admin")).first()
        assert admin is not None
        assert admin.usuario == "admin"
        assert admin.nombre_completo == "Administrador"
        assert admin.activo is True
        assert bcrypt.checkpw(b"admin", admin.contrasena.encode("utf-8"))


def test_seed_admin_no_duplica(_mock_get_session):
    """_seed_admin() NO crea duplicados si el admin ya existe."""
    from sistema_financiero.__main__ import _seed_admin  # noqa: PLC0415

    with Session(_mock_get_session) as session:
        admin = Usuario(
            usuario="admin",
            contrasena=bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode("utf-8"),
            nombre_completo="Admin",
            activo=True,
        )
        session.add(admin)
        session.commit()

    _seed_admin()

    with Session(_mock_get_session) as session:
        admins = session.exec(select(Usuario).where(Usuario.usuario == "admin")).all()
        assert len(admins) == 1
