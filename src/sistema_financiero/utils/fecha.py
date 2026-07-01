from datetime import UTC, date, datetime


def ahora() -> datetime:
    """Retorna datetime actual como naive UTC (compatible con DB SQLite)."""
    return datetime.now(UTC).replace(tzinfo=None)


def hoy() -> date:
    """Retorna fecha actual como naive date (UTC)."""
    return ahora().date()
