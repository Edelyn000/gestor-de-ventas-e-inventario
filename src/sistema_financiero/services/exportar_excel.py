from ..core.reporte_service import ReporteService


def exportar_reporte_excel(reporte_id: int, ruta_archivo: str) -> str | None:
    """Exporta un reporte diario a Excel.
    Retorna la ruta del archivo generado o None si falla."""
    servicio = ReporteService()
    return servicio.exportar_excel(reporte_id, ruta_archivo)
