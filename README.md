# Sistema Finacieron

Sistema de gestión financiera y de inventario para abasto. Escritorio con PyQt6 + SQLModel + SQLite.

## Stack

- **Python >=3.14**, PyQt6, SQLModel, SQLite
- pyqtgraph, openpyxl, scraper-bcv, bcrypt, alembic

## Instalación

```bash
poetry install
```

## Ejecución

```bash
poetry run python -m sistema_finacieron
```

## Tests

```bash
poetry run pytest
poetry run pytest tests/ -v --cov=sistema_finacieron
```
