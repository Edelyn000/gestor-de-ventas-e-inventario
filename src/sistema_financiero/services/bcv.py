# bcv.py: Consulta de la tasa BCV via scraper-bcv.
from decimal import Decimal

from scraper_bcv import BCVClient

_client: BCVClient | None = None


# Devuelve (o crea) la instancia unica del cliente BCV.
def _get_client() -> BCVClient:
    """Devuelve (o crea) la instancia unica del cliente BCV."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = BCVClient(log_file="logs/mi_app.log")
    return _client


# Obtiene la tasa de cambio actual del BCV para USD.
def obtener_tasa() -> Decimal:
    """Obtiene la tasa de cambio actual del BCV para USD."""
    client = _get_client()
    tasas = client.get_tasas("USD")
    try:
        return Decimal(str(tasas["USD"]["valor"]))
    except (KeyError, TypeError) as exc:
        raise ConnectionError(
            f"Respuesta BCV invalida o sin conexion: {tasas!r}",
        ) from exc


# Convierte bolívares (Bs) a dólares (USD) usando la tasa del BCV.
def convertir_a_usd(bs: int | float | Decimal) -> Decimal:
    """Convierte bolívares (Bs) a dólares (USD) usando la tasa del BCV."""
    bs = Decimal(str(bs))
    tasa = obtener_tasa()
    return bs / tasa


# Convierte dólares (USD) a bolívares (Bs) usando la tasa del BCV.
def convertir_a_bs(dolares: int | float | Decimal) -> Decimal:
    """Convierte dólares (USD) a bolívares (Bs) usando la tasa del BCV."""
    dolares = Decimal(str(dolares))
    tasa = obtener_tasa()
    return dolares * tasa

