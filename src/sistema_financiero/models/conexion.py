# conexion.py: Motor, sesion y creacion de tablas de la base de datos.
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

DB_PATH = Path(__file__).parent.parent.parent.parent / "database" / "database.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    """Crea todas las tablas definidas en modelos.py si no existen."""
    SQLModel.metadata.create_all(engine)


@contextmanager
def obtener_sesion(session: Session | None = None) -> Iterator[Session]:
    """Context manager: si recibe una sesion existente la usa, si no, crea una nueva."""
    if session is not None:
        yield session
    else:
        with Session(engine) as s:
            yield s

