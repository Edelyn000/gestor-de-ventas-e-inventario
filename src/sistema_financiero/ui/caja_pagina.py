# ============================================================
# ARCHIVO: ui/caja_pagina.py  (PÁGINA DE GESTIÓN DE CAJA)
# ============================================================
# Página que muestra el estado de la caja registradora y
# permite su apertura, cierre y reporte Z.
#
# --- Panel Cajero (Operativo):
#   - Ver estado de la caja (ABIERTA/CERRADA)
#   - Monto de apertura
#   - Ventas del turno
#   - Botones: Abrir Caja, Cerrar Caja
#
# --- Panel Administrador (Gerencial):
#   - Adicional: Historial de cierres
#   - Ver/reimprimir Reportes Z anteriores
# ============================================================

from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session
from sqlmodel import col, select

from sistema_financiero.core.caja_service import CajaService
from sistema_financiero.core.venta_controller import VentaController
from sistema_financiero.models.modelos import Usuario, Venta
from sistema_financiero.utils.moneda import formatear_bs, formatear_usd


class CajaPagina(QWidget):
    """Página de gestión de caja registradora."""

    def __init__(
        self, usuario_actual: Usuario, caja_service: CajaService, venta_controller: VentaController
    ) -> None:
        super().__init__()
        self.usuario_actual = usuario_actual
        self.caja_service = caja_service
        self.venta_controller = venta_controller
        self.db: Session | None = None

        self.setWindowTitle("Caja - Sistema Financiero")
        self.resize(1024, 768)

        self._setup_ui()
        self._actualizar_estado()

    # ------------------------------------------------------------------
    # _setup_ui: construye los widgets de la página de caja
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # --- Sección: Estado de la caja ---
        grupo_estado = QGroupBox("Estado de la Caja")
        estado_layout = QFormLayout(grupo_estado)

        # Etiqueta de estado
        self.lbl_estado = QLabel("---")
        self.lbl_estado.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        estado_layout.addRow("Estado:", self.lbl_estado)

        # Monto de apertura
        self.lbl_monto_apertura = QLabel("---")
        estado_layout.addRow("Monto Apertura (Bs.):", self.lbl_monto_apertura)

        # Hora de apertura
        self.lbl_hora_apertura = QLabel("---")
        estado_layout.addRow("Hora Apertura:", self.lbl_hora_apertura)

        # --- Sección: Ventas del turno ---
        grupo_ventas = QGroupBox("Ventas del Turno")
        ventas_layout = QVBoxLayout(grupo_ventas)

        self.lbl_total_ventas = QLabel("Total Ventas: Bs. 0.00")
        self.lbl_total_ventas.setStyleSheet("font-size: 14px; font-weight: bold;")
        ventas_layout.addWidget(self.lbl_total_ventas)

        self.lbl_cantidad_ventas = QLabel("Cantidad de Ventas: 0")
        ventas_layout.addWidget(self.lbl_cantidad_ventas)

        # Tabla de detalle de ventas (resumida)
        self.tabla_ventas_resumen = QTableWidget()
        self.tabla_ventas_resumen.setColumnCount(4)
        self.tabla_ventas_resumen.setHorizontalHeaderLabels(
            ["Hora", "Factura", "Total Bs.", "Total USD"]
        )
        horizontal_header = self.tabla_ventas_resumen.horizontalHeader()
        if horizontal_header:
            horizontal_header.setStretchLastSection(True)
        self.tabla_ventas_resumen.setSelectionBehavior(QAbstractItemView.SelectRows)  # type: ignore
        ventas_layout.addWidget(self.tabla_ventas_resumen, 1)

        # --- Sección: Operaciones ---
        grupo_operaciones = QGroupBox("Operaciones")
        ops_layout = QFormLayout(grupo_operaciones)

        # Botón: Abrir Caja (solo si no hay caja abierta)
        self.btn_abrir_caja = QPushButton("Abrir Caja")
        self.btn_abrir_caja.setStyleSheet("""
            QPushButton {
                background-color: #84cc16;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #777777;
            }
        """)
        self.btn_abrir_caja.clicked.connect(self._on_abrir_caja)
        ops_layout.addRow(":", self.btn_abrir_caja)

        # Botón: Cerrar Caja (solo si hay caja abierta)
        self.btn_cerrar_caja = QPushButton("Cerrar Caja")
        self.btn_cerrar_caja.setStyleSheet("""
            QPushButton {
                background-color: #f06543;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
        """)
        self.btn_cerrar_caja.clicked.connect(self._on_cerrar_caja)
        self.btn_cerrar_caja.setVisible(False)
        ops_layout.addRow(":", self.btn_cerrar_caja)

        # Campo: Observaciones (solo visible al cerrar)
        self.grp_observaciones = QGroupBox("Observaciones Cierre")
        obs_layout = QFormLayout(self.grp_observaciones)
        self.txt_observaciones = QLabel("--")
        obs_layout.addRow("Observaciones:", self.txt_observaciones)
        # Oculto inicialmente
        self.grp_observaciones.setVisible(False)

        # --- Layout principal ---
        layout.addWidget(grupo_estado)
        layout.addWidget(grupo_ventas)
        layout.addWidget(grupo_operaciones)
        layout.addWidget(self.grp_observaciones, 1)  # Espacio flexible

        # Cargar datos iniciales
        self._cargar_ventas_del_turno()

    # ------------------------------------------------------------------
    # _actualizar_estado: Actualiza la UI con el estado actual de la caja
    # ------------------------------------------------------------------
    def _actualizar_estado(self) -> None:
        """Actualiza la interfaz con el estado actual de la caja."""
        try:
            caja = self.caja_service.obtener_caja_abierta()

            if caja:
                # Hay caja abierta
                self.lbl_estado.setText("ABIERTA ✓")
                self.lbl_estado.setStyleSheet(
                    "color: #84cc16; font-size: 14px; font-weight: bold; padding: 5px;"
                )
                self.lbl_monto_apertura.setText(formatear_bs(caja.monto_apertura_bs))
                self.lbl_hora_apertura.setText(
                    f"Abrida: {caja.fecha_apertura.strftime('%H:%M:%S')}"
                )

                # Mostrar botones de operación
                self.btn_abrir_caja.setVisible(False)
                self.btn_abrir_caja.setEnabled(False)
                self.btn_cerrar_caja.setVisible(True)
                self.btn_cerrar_caja.setEnabled(True)
                self.grp_observaciones.setVisible(True)
                self.txt_observaciones.setText(caja.observaciones or "--")

                # Cargar ventas del turno
                self._cargar_ventas_del_turno(caja.id)
            else:
                # No hay caja abierta
                self.lbl_estado.setText("NINGUNA")
                self.lbl_estado.setStyleSheet(
                    "color: #f06543; font-size: 14px; font-weight: bold; padding: 5px;"
                )
                self.lbl_monto_apertura.setText("---")
                self.lbl_hora_apertura.setText("---")

                # Mostrar botón de abrir
                self.btn_abrir_caja.setVisible(True)
                self.btn_abrir_caja.setEnabled(True)
                self.btn_cerrar_caja.setVisible(False)
                self.btn_cerrar_caja.setEnabled(False)
                self.grp_observaciones.setVisible(False)
        except ValueError:
            # Error (shouldn't normally happen, but handle gracefully)
            self.lbl_estado.setText("Error")
            self.lbl_estado.setStyleSheet("color: #e74c3c;")
            self.btn_abrir_caja.setEnabled(True)
            self.btn_cerrar_caja.setVisible(False)

    # ------------------------------------------------------------------
    # _cargar_ventas_del_turno: Carga la tabla de ventas del turno actual
    # ------------------------------------------------------------------
    def _cargar_ventas_del_turno(self, caja_id: int | None = None) -> None:
        """Carga la tabla resumida de ventas del turno."""
        if caja_id is not None:
            stmt = select(Venta).where(
                col(Venta.caja_id) == caja_id,
                col(Venta.estado) == "COMPLETADA",
            )
        else:
            # Si no hay caja_id, intentar obtener la caja actual
            stmt = select(Venta).limit(20)  # Fallback limitado

        ventas = (
            self.db.execute(stmt).scalars().all()
            if hasattr(self, "db") and self.db is not None
            else []
        )

        # Por ahora, si no hay sesión de BD directa, mostraremos info limitada
        if not ventas or len(ventas) == 0:
            self.lbl_total_ventas.setText("Total Ventas: Bs. 0.00")
            self.lbl_cantidad_ventas.setText("Cantidad de Ventas: 0")
            self.tabla_ventas_resumen.setRowCount(0)
            return

        # Calcular totales
        total_bs = sum((v.total_bs or 0) for v in ventas)
        cantidad = len(ventas)

        self.lbl_total_ventas.setText(f"Total Ventas: {formatear_bs(Decimal(str(total_bs)))}")
        self.lbl_cantidad_ventas.setText(f"Cantidad de Ventas: {cantidad}")

        # Llenar tabla resumida (últimas ventas)
        self.tabla_ventas_resumen.setRowCount(min(len(ventas), 10))  # Máx 10 filas

        for i, v in enumerate(ventas[:10]):
            # Formatear hora y factura
            hora = v.fecha_venta.strftime("%H:%M") if v.fecha_venta else "---"
            factura = v.numero_factura or "---"
            total_bs_formateado = formatear_bs(v.total_bs) if v.total_bs else "0.00"
            total_usd_formateado = formatear_usd(v.total_usd) if v.total_usd else "0.00"

            self.tabla_ventas_resumen.setItem(i, 0, QTableWidgetItem(hora))
            self.tabla_ventas_resumen.setItem(i, 1, QTableWidgetItem(factura))
            self.tabla_ventas_resumen.setItem(i, 2, QTableWidgetItem(total_bs_formateado))
            self.tabla_ventas_resumen.setItem(i, 3, QTableWidgetItem(total_usd_formateado))

    # ------------------------------------------------------------------
    # _on_abrir_caja: Maneja el clic en el botón "Abrir Caja"
    # ------------------------------------------------------------------
    def _on_abrir_caja(self) -> None:
        """Abre la caja registradora."""
        # Verificar que no haya una caja abierta con este usuario ya
        try:
            self.caja_service.validar_caja_abierta()
            QMessageBox.warning(self, "Caja Abierta", "Ya existe una caja abierta.")
            return
        except ValueError:
            # No hay caja abierta, podemos abrir una
            pass

        # Solicitar monto de apertura
        monto, ok = QInputDialog.getDouble(
            self,
            "Abrir Caja",
            "Ingrese el monto inicial de apertura (en bolívares):",
            0,
            0,
            99999999,
            2,
        )

        if ok and monto > 0:
            usuario_id = self.usuario_actual.id
            if usuario_id is None:
                QMessageBox.critical(
                    self,
                    "Error",
                    "El usuario actual no tiene un ID válido.",
                )
                return

            try:
                caja = self.caja_service.abrir_caja(Decimal(str(monto)), usuario_id)

                monto_apertura = caja.monto_apertura_bs
                monto_formateado = (
                    formatear_bs(monto_apertura) if monto_apertura is not None else "Bs. 0,00"
                )

                QMessageBox.information(
                    self,
                    "Caja Abierta",
                    f"Caja abierta correctamente.\nMonto: {monto_formateado}",
                )
                self._actualizar_estado()
            except ValueError as e:
                QMessageBox.critical(self, "Error", str(e))
        elif ok and monto == 0:
            QMessageBox.warning(
                self, "Monto Inválido", "El monto de apertura debe ser mayor a cero."
            )

    # ------------------------------------------------------------------
    # _on_cerrar_caja: Maneja el clic en el botón "Cerrar Caja"
    # ------------------------------------------------------------------
    def _on_cerrar_caja(self) -> None:
        """Cierra la caja registradora y genera Reporte Z."""
        # Verificar que haya caja abierta
        caja = self.caja_service.obtener_caja_abierta()
        if not caja:
            QMessageBox.warning(self, "Caja", "No hay caja abierta para cerrar.")
            return

        # Solicitar conteo físico (billetes Bs. y Bs. USD)
        billetes_bs, ok_bs = QInputDialog.getDouble(
            self,
            "Cierre de Caja",
            "Ingrese el total en billetes de bolívares (solo billetes):",
            0,
            0,
            99999999,
            2,
        )

        if ok_bs:
            billetes_usd, ok_usd = QInputDialog.getDouble(
                self,
                "Cierre de Caja",
                "Ingrese el total en billetes de dólares (solo billetes):",
                0,
                0,
                99999999,
                2,
            )

            if ok_bs and ok_usd:
                # Solicitar observaciones
                dialog = QDialog(self)
                dialog.setWindowTitle("Observaciones Cierre")
                dialog.resize(400, 150)
                layout = QVBoxLayout(dialog)
                label = QLabel("Observaciones opcionales para el cierre:")
                layout.addWidget(label)
                observacion_edit = QLineEdit()
                observacion_edit.setPlaceholderText("Ej: Cierre normal, sin observaciones")
                layout.addWidget(observacion_edit)

                button_box = QDialogButtonBox(
                    QDialogButtonBox.Ok | QDialogButtonBox.Cancel,  # type: ignore[attr-defined]
                    Qt.Horizontal,  # type: ignore[attr-defined]
                    dialog,
                )
                button_box.accepted.connect(dialog.accept)
                button_box.rejected.connect(dialog.reject)
                layout.addWidget(button_box)

                if dialog.exec() == QDialog.DialogCode.Accepted:
                    observaciones = observacion_edit.text().strip()
                else:
                    return  # User cancelled
                # Confirmar cierre
                caja_id = caja.id
                if caja_id is None:
                    QMessageBox.critical(self, "Error", "La caja no tiene un ID válido.")
                    return

                try:
                    nueva_caja = self.caja_service.cerrar_caja(
                        caja_id,
                        Decimal(str(billetes_bs)),
                        Decimal(str(billetes_usd)),
                        observaciones if observaciones else None,
                    )

                    sobrante_faltante = nueva_caja.sobrante_faltante_bs
                    if sobrante_faltante is None:
                        sobrante_faltante = Decimal("0")

                    QMessageBox.information(
                        self,
                        "Cierre Exitoso",
                        "Caja cerrada correctamente.\n"
                        f"Sobrante/Faltante: {formatear_bs(sobrante_faltante)}\n"
                        "Reporte Z generado automáticamente.",
                    )
                    self._actualizar_estado()
                except ValueError as e:
                    QMessageBox.critical(self, "Error", str(e))
            elif ok_usd:
                # User cancelled the USD input
                pass
        elif ok_bs:
            QMessageBox.warning(
                self, "Dato Incompleto", "También debe ingresar el total en dólares."
            )
        else:
            # User cancelled the Bs. input
            pass
