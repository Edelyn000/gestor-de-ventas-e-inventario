# fecha.py: Helpers de fecha en zona horaria de Venezuela.
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    ZONA_VET: timezone | ZoneInfo = ZoneInfo("America/Caracas")
except ZoneInfoNotFoundError, ValueError:
    ZONA_VET = timezone(timedelta(hours=-4), name="VET")


# Retorna datetime actual como naive UTC (compatible con DB SQLite).
def ahora() -> datetime:
    """Retorna datetime actual como naive UTC (compatible con DB SQLite)."""
    return datetime.now(UTC).replace(tzinfo=None)


# Convierte un datetime naive (interpretado como UTC) a hora local.
def a_local(fecha_utc: datetime) -> datetime:
    """Convierte un datetime naive (interpretado como UTC) a hora local
    de Venezuela (UTC-4), devolviendo un naive local (para mostrar)."""
    return fecha_utc.replace(tzinfo=UTC).astimezone(ZONA_VET).replace(tzinfo=None)


# Convierte un datetime naive local de Venezuela a naive UTC.
def a_utc(fecha_local: datetime) -> datetime:
    """Convierte un datetime naive local de Venezuela a naive UTC
    (para comparar contra las marcas de tiempo guardadas en BD)."""
    return fecha_local.replace(tzinfo=ZONA_VET).astimezone(UTC).replace(tzinfo=None)


# Límites UTC (naive) que cubren el dí­a local venezolano `dia`.
def rango_dia_utc(dia: date) -> tuple[datetime, datetime]:
    """Límites UTC (naive) que cubren el dí­a local venezolano `dia`."""
    desde_local = datetime(dia.year, dia.month, dia.day, 0, 0, 0)
    hasta_local = datetime(dia.year, dia.month, dia.day, 23, 59, 59)
    return a_utc(desde_local), a_utc(hasta_local)


# Retorna la fecha actual en Venezuela (UTC-4) como naive date.
def hoy() -> date:
    """Retorna la fecha actual en Venezuela (UTC-4) como naive date."""
    return a_local(ahora()).date()

