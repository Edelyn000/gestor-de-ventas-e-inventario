# exportar_excel.py: Fachada de exportacion a Excel del reporte diario.
from ..core.reporte_service import ReporteService


# Exporta un reporte diario a Excel.
def exportar_reporte_excel(reporte_id: int, ruta_archivo: str) -> str | None:
    """Exporta un reporte diario a Excel."""
    servicio = ReporteService()
    return servicio.exportar_excel(reporte_id, ruta_archivo)

