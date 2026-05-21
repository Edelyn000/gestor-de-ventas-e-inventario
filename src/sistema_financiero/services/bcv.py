from decimal import Decimal

from scraper_bcv import BCVClient

# ============================================================
# SERVICIO: Tasa de Cambio BCV
# Cliente para consultar la tasa de cambio oficial del BCV
# (Banco Central de Venezuela) usando la libreria scraper-bcv.
# Las funciones principales son:
#   - obtener_tasa()   → tasa actual USD
#   - convertir_a_usd()  → convierte Bs a USD
#   - convertir_a_bs()   → convierte USD a Bs
# ============================================================

# Cliente singleton (se reusa entre llamadas)
_client: BCVClient | None = None


def _get_client() -> BCVClient:
    """Devuelve (o crea) la instancia unica del cliente BCV."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = BCVClient(log_file="logs/mi_app.log")
    return _client


def obtener_tasa() -> Decimal:
    """Obtiene la tasa de cambio actual del BCV para USD."""
    client = _get_client()
    tasas = client.get_tasas("USD")
    return Decimal(str(tasas["USD"]["valor"]))


def convertir_a_usd(bs: int | float | Decimal) -> Decimal:
    """Convierte bolívares (Bs) a dólares (USD) usando la tasa del BCV."""
    bs = Decimal(str(bs))
    tasa = obtener_tasa()
    return bs / tasa


def convertir_a_bs(dolares: int | float | Decimal) -> Decimal:
    """Convierte dólares (USD) a bolívares (Bs) usando la tasa del BCV."""
    dolares = Decimal(str(dolares))
    tasa = obtener_tasa()
    return dolares * tasa
