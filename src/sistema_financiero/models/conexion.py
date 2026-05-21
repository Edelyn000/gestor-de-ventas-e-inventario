from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# ============================================================
# CONFIGURACION DE LA BASE DE DATOS
# La DB se crea automaticamente en database/database.db
# (ruta relativa a la raiz del proyecto).
# check_same_thread=False es necesario porque PyQt6 accede
# a la DB desde el hilo principal de la GUI.
# ============================================================

# Ruta absoluta al archivo SQLite
DB_PATH = Path(__file__).parent.parent.parent.parent / "database" / "database.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Motor de SQLAlchemy (echo=False para no mostrar logs SQL)
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    """Crea todas las tablas definidas en modelos.py si no existen."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """Devuelve una nueva sesion de BD lista para operaciones."""
    return Session(engine)
