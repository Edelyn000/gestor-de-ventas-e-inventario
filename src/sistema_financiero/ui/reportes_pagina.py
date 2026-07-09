# ============================================================
# ARCHIVO: ui/reportes_pagina.py  (PAGINA DE REPORTES / CIERRE DIARIO)
# ============================================================
# Widget independiente para la gestion de reportes diarios.
#
# QUE MUESTRA:
#   1. Filtro de fechas (desde / hasta) para el historial de reportes.
#   2. Botones: Cerrar Dia (genera reporte), Exportar Excel, Regenerar.
#   3. Tabla con reportes generados (ventas Bs, USD, stock bajo, etc.).
#
# --- NO TOCAR: nombre de la clase (ReportesPagina), firma del __init__,
#     logica de _cerrar_dia, _regenerar_reporte, _exportar_reporte_excel.
# --- MODIFICABLE: estilos de botones, colores, fuentes, columnas de tabla,
#     textos, etiquetas, mensajes, ruta/nombre por defecto en exportacion.
# ============================================================
from datetime import date

from PyQt6.QtCore import QDate
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.reporte_service import ReporteService
from ..utils import formatear_bs, formatear_usd_texto, hoy
from .widgets import TablaProductos


# ============ PAGINA DE REPORTES ============
class ReportesPagina(QWidget):
    # --- NO TOCAR: firma del constructor (recibe controlador).
    def __init__(self, controlador_reportes: ReporteService) -> None:
        super().__init__()

        self.controlador_reportes = controlador_reportes

        # --- MODIFICABLE: layout, margenes, espaciado.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # [Titulo]
        # --- MODIFICABLE: texto, fuente, tamaño.
        lbl_titulo = QLabel("Reportes")
        fuente = QFont()
        fuente.setPointSize(24)
        fuente.setBold(True)
        lbl_titulo.setFont(fuente)
        layout.addWidget(lbl_titulo)

        # [Barra de herramientas: filtro de fechas + botones]
        # --- MODIFICABLE: estilos, textos, colores de botones.
        barra = QHBoxLayout()
        barra.setSpacing(10)

        barra.addWidget(QLabel("Desde:"))
        self.fecha_desde_reporte = QDateEdit()
        self.fecha_desde_reporte.setCalendarPopup(True)
        self.fecha_desde_reporte.setDate(QDate.currentDate().addDays(-30))
        self.fecha_desde_reporte.dateChanged.connect(self._refrescar_tabla_reportes)
        barra.addWidget(self.fecha_desde_reporte)

        barra.addWidget(QLabel("Hasta:"))
        self.fecha_hasta_reporte = QDateEdit()
        self.fecha_hasta_reporte.setCalendarPopup(True)
        self.fecha_hasta_reporte.setDate(QDate.currentDate())
        self.fecha_hasta_reporte.dateChanged.connect(self._refrescar_tabla_reportes)
        barra.addWidget(self.fecha_hasta_reporte)

        barra.addSpacing(20)

        btn_cerrar_dia = QPushButton("Cerrar Dia")
        btn_cerrar_dia.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #45a049; }",
        )
        # --- NO TOCAR: conexion a _cerrar_dia.
        btn_cerrar_dia.clicked.connect(self._cerrar_dia)
        barra.addWidget(btn_cerrar_dia)

        btn_exportar = QPushButton("Exportar Excel")
        btn_exportar.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0b7dda; }",
        )
        btn_exportar.clicked.connect(self._exportar_reporte_excel)
        barra.addWidget(btn_exportar)

        btn_regenerar = QPushButton("Regenerar")
        btn_regenerar.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white;"
            " padding: 8px 16px; border-radius: 5px; font-weight: bold; }"
            "QPushButton:hover { background-color: #e68a00; }",
        )
        btn_regenerar.clicked.connect(self._regenerar_reporte)
        barra.addWidget(btn_regenerar)

        barra.addStretch()
        layout.addLayout(barra)

        # --- MODIFICABLE: columnas y anchos de la tabla de reportes.
        columnas = [
            ("ID", 40),
            ("Fecha", 110),
            ("Ventas Bs.", 100),
            ("Ventas USD", 100),
            ("Cant. Ventas", 80),
            ("Stock Bajo", 80),
            ("Sin Stock", 80),
            ("Generado", 130),
        ]
        self.tabla_reportes = TablaProductos(columnas)
        layout.addWidget(self.tabla_reportes)

        # --- NO TOCAR: carga inicial de datos.
        self._refrescar_tabla_reportes()

    # --- NO TOCAR: logica de consulta de reportes a la BD.
    # --- MODIFICABLE: formato de los datos en la tabla.
    def _refrescar_tabla_reportes(self) -> None:
        desde_qdate = self.fecha_desde_reporte.date()
        hasta_qdate = self.fecha_hasta_reporte.date()

        desde = date(desde_qdate.year(), desde_qdate.month(), desde_qdate.day())
        hasta = date(hasta_qdate.year(), hasta_qdate.month(), hasta_qdate.day())

        # ADVERTENCIA: listar_por_rango() cierra la sesión. ReporteDiario no tiene
        # relaciones, pero si agregas una en el futuro, cárgala con selectinload().
        reportes = self.controlador_reportes.listar_por_rango(desde, hasta)

        self.tabla_reportes.setRowCount(len(reportes))
        for fila, rep in enumerate(reportes):
            self.tabla_reportes.setItem(fila, 0, QTableWidgetItem(str(rep.id or "")))
            self.tabla_reportes.setItem(fila, 1, QTableWidgetItem(rep.fecha.isoformat()))
            self.tabla_reportes.setItem(
                fila, 2, QTableWidgetItem(formatear_bs(rep.total_ventas_bs)),
            )
            self.tabla_reportes.setItem(
                fila, 3, QTableWidgetItem(formatear_usd_texto(rep.total_ventas_usd)),
            )
            self.tabla_reportes.setItem(fila, 4, QTableWidgetItem(str(rep.cantidad_ventas)))
            self.tabla_reportes.setItem(fila, 5, QTableWidgetItem(str(rep.productos_stock_bajo)))
            self.tabla_reportes.setItem(fila, 6, QTableWidgetItem(str(rep.productos_sin_stock)))
            fecha_gen = (
                rep.fecha_generacion.strftime("%d/%m/%Y %H:%M") if rep.fecha_generacion else ""
            )
            self.tabla_reportes.setItem(fila, 7, QTableWidgetItem(fecha_gen))

        self.tabla_reportes.resizeColumnsToContents()

    # --- NO TOCAR: logica de cierre de dia (genera reporte en BD).
    def _cerrar_dia(self) -> None:
        try:
            reporte = self.controlador_reportes.generar_reporte()
            # --- MODIFICABLE: mensaje de exito.
            QMessageBox.information(
                self,
                "Cierre Exitoso",
                f"Reporte del {reporte.fecha} generado correctamente.\n"
                f"Ventas: {reporte.cantidad_ventas} | "
                f"Total Bs.: {formatear_bs(reporte.total_ventas_bs)}",
            )
            self._refrescar_tabla_reportes()
        except Exception:
            QMessageBox.critical(self, "Error", "Error al generar reporte.")
            raise

    # --- NO TOCAR: logica de regeneracion de reporte.
    def _regenerar_reporte(self) -> None:
        fila = self.tabla_reportes.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Seleccion", "Seleccione un reporte de la tabla.")
            return

        item_fecha = self.tabla_reportes.item(fila, 1)
        if item_fecha is None:
            return
        fecha_texto = item_fecha.text()

        try:
            partes = fecha_texto.split("-")
            fecha_reporte = date(int(partes[0]), int(partes[1]), int(partes[2]))
        except (IndexError, ValueError):
            QMessageBox.warning(self, "Error", "Fecha de reporte invalida.")
            return

        # --- MODIFICABLE: texto de confirmacion.
        respuesta = QMessageBox.question(
            self,
            "Regenerar Reporte",
            f"Va a regenerar el reporte del {fecha_reporte}.\n"
            "Esto reemplazara el reporte existente. Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            reporte = self.controlador_reportes.generar_reporte(fecha_reporte)
            QMessageBox.information(
                self,
                "Regenerado",
                f"Reporte del {reporte.fecha} regenerado correctamente.",
            )
            self._refrescar_tabla_reportes()
        except Exception:
            QMessageBox.critical(self, "Error", "Error al regenerar reporte.")
            raise

    # --- NO TOCAR: logica de exportacion a Excel.
    # --- MODIFICABLE: nombre de archivo por defecto, filtro de archivos.
    def _exportar_reporte_excel(self) -> None:
        fila = self.tabla_reportes.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Seleccion", "Seleccione un reporte de la tabla.")
            return

        item_id = self.tabla_reportes.item(fila, 0)
        if item_id is None:
            return
        reporte_id = int(item_id.text())

        # --- MODIFICABLE: nombre sugerido y filtro del dialogo de guardado.
        ruta, _filtro = QFileDialog.getSaveFileName(
            self,
            "Guardar Reporte Excel",
            f"reporte_diario_{hoy().isoformat()}.xlsx",
            "Archivos Excel (*.xlsx)",
        )

        if not ruta:
            return

        try:
            # --- NO TOCAR: llamada al servicio para exportar.
            self.controlador_reportes.exportar_excel(reporte_id, ruta)
            QMessageBox.information(
                self,
                "Exportado",
                f"Reporte exportado correctamente a:\n{ruta}",
            )
        except Exception:
            QMessageBox.critical(self, "Error", "Error al exportar.")
            raise
