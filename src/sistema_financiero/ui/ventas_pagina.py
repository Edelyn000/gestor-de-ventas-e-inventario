from decimal import Decimal

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.caja_service import CajaService
from ..core.producto_controller import ProductoController
from ..core.reporte_service import ReporteService
from ..core.venta_controller import VentaController
from ..models import Usuario
from ..utils import ROL_ADMINISTRADOR, formatear_bs, formatear_usd
from ..utils.fecha import a_local, hoy
from ..utils.logging_setup import registrar_excepcion
from .dialogo_anulacion import DialogoAnulacion
from .widgets import SelectorFecha, TablaProductos, TituloPagina


# VentasPagina: Historial de ventas y panel de caja del turno.
class VentasPagina(QWidget):
    nueva_venta = pyqtSignal()
    estado_caja_cambio = pyqtSignal()

    MAX_METODOS_LISTADOS = 3

    # Construye la pagina de ventas con panel de caja, filtros y tabla.
    def __init__(
        self,
        usuario_actual: Usuario,
        controlador_ventas: VentaController,
        controlador_productos: ProductoController,
        caja_service: CajaService,
        reporte_service: ReporteService | None = None,
    ) -> None:
        super().__init__()

        self.usuario_actual = usuario_actual
        self.controlador_ventas = controlador_ventas
        self.controlador_productos = controlador_productos
        self.caja_service = caja_service
        self.reporte_service = reporte_service

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        layout.addWidget(TituloPagina("Ventas"))

        layout.addWidget(self._crear_panel_caja())
        layout.addSpacing(10)

        layout.addLayout(self._crear_barra_herramientas())
        layout.addSpacing(10)

        layout.addLayout(self._crear_filtro_fechas())
        layout.addSpacing(10)

        self.tabla_ventas = self._crear_tabla_ventas()
        layout.addWidget(self.tabla_ventas, 1)

        self.cargar()

    # Una celda del panel 2x2: etiqueta a la izquierda + caja con valor.
    def _crear_fila_panel_caja(
        self, grid: QGridLayout, fila: int, col: int, texto: str
    ) -> tuple[QLabel, QLabel]:
        """Una celda del panel 2x2: etiqueta a la izquierda + caja con valor."""
        etiqueta = QLabel(texto)
        etiqueta.setProperty("rol", "etiqueta_panel_caja")
        etiqueta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        valor = QLabel("--")
        valor.setProperty("rol", "valor_caja")
        valor.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(etiqueta, fila, col)
        grid.addWidget(valor, fila, col + 1)
        return etiqueta, valor

    # Crea el panel Caja del Turno en 2x2 con botones.
    def _crear_panel_caja(self) -> QGroupBox:
        grupo = QGroupBox("Caja del Turno")
        grupo.setProperty("rol", "panel_caja")
        grid = QGridLayout(grupo)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(12, 4, 12, 8)

        _, self.lbl_estado_caja = self._crear_fila_panel_caja(grid, 0, 0, "Estado:")
        _, self.lbl_fondo_caja = self._crear_fila_panel_caja(grid, 0, 2, "Fondo de Apertura (Bs.):")
        _, self.lbl_hora_caja = self._crear_fila_panel_caja(grid, 1, 0, "Hora Apertura:")

        self.lbl_obs_caja, self.lbl_observaciones_caja = self._crear_fila_panel_caja(
            grid, 1, 2, "Observaciones:"
        )
        self.lbl_obs_caja.setVisible(False)
        self.lbl_observaciones_caja.setVisible(False)

        botones = QHBoxLayout()
        self.btn_abrir_caja = QPushButton("Abrir Caja")
        self.btn_abrir_caja.setProperty("rol", "caja_abrir")
        self.btn_abrir_caja.clicked.connect(self._on_abrir_caja)
        botones.addWidget(self.btn_abrir_caja)

        botones.addStretch()
        self.btn_cerrar_caja = QPushButton("Cerrar Caja")
        self.btn_cerrar_caja.setProperty("rol", "caja_cerrar")
        self.btn_cerrar_caja.clicked.connect(self._on_cerrar_caja)
        self.btn_cerrar_caja.setVisible(False)
        botones.addWidget(self.btn_cerrar_caja)
        grid.addLayout(botones, 2, 0, 1, 4)

        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 1)

        return grupo

    # Refresca el estado, fondo, hora y observaciones de la caja.
    def _actualizar_estado_caja(self) -> None:
        caja = self.caja_service.obtener_caja_abierta()

        if caja:
            self.lbl_estado_caja.setText("ABIERTA")
            self._set_rol(self.lbl_estado_caja, "estado_abierta")
            self.lbl_fondo_caja.setText(formatear_bs(caja.monto_apertura_bs))
            hora_local = (
                a_local(caja.fecha_apertura).strftime("%H:%M:%S")
                if caja.fecha_apertura
                else "--:--:--"
            )
            self.lbl_hora_caja.setText(f"Abierta: {hora_local}")
            self.lbl_observaciones_caja.setText(caja.observaciones or "--")
            self.lbl_observaciones_caja.setVisible(True)
            self.lbl_obs_caja.setVisible(True)

            self.btn_abrir_caja.setVisible(False)
            self.btn_cerrar_caja.setVisible(True)
            self.btn_cerrar_caja.setEnabled(True)
        else:
            self.lbl_estado_caja.setText("CERRADA")
            self._set_rol(self.lbl_estado_caja, "estado_cerrada")
            self.lbl_fondo_caja.setText("---")
            self.lbl_hora_caja.setText("---")
            self.lbl_observaciones_caja.setVisible(False)
            self.lbl_obs_caja.setVisible(False)

            self.btn_abrir_caja.setVisible(True)
            self.btn_abrir_caja.setEnabled(True)
            self.btn_cerrar_caja.setVisible(False)
            self.btn_cerrar_caja.setEnabled(False)

    # Cambia el rol QSS de un widget y lo repinta (mismo patron del POS).
    @staticmethod
    def _set_rol(widget: QWidget, rol: str) -> None:
        """Cambia el rol QSS de un widget y lo repinta (mismo patron del POS)."""
        widget.setProperty("rol", rol)
        estilo = widget.style()
        if estilo is not None:
            estilo.unpolish(widget)
            estilo.polish(widget)

    # Pide el fondo y abre la caja del turno.
    def _on_abrir_caja(self) -> None:
        try:
            self.caja_service.validar_caja_abierta()
            QMessageBox.warning(self, "Caja Abierta", "Ya existe una caja abierta.")
            return
        except ValueError:
            pass
        except Exception as e:
            registrar_excepcion(e, "_on_abrir_caja (validar)")
            QMessageBox.critical(self, "Error", f"Error al consultar la caja.\n{e}")
            return

        monto, ok = QInputDialog.getDouble(
            self,
            "Abrir Caja",
            "Ingrese el monto inicial de apertura (en bolivares):",
            0,
            0,
            99999999,
            2,
        )
        if not ok:
            return
        if monto < 0:
            QMessageBox.warning(
                self, "Monto Invalido", "El monto de apertura no puede ser negativo."
            )
            return

        usuario_id = self.usuario_actual.id
        if usuario_id is None:
            QMessageBox.critical(self, "Error", "El usuario actual no tiene un ID valido.")
            return

        try:
            caja = self.caja_service.abrir_caja(Decimal(str(monto)), usuario_id)
            QMessageBox.information(
                self,
                "Caja Abierta",
                f"Caja abierta correctamente.\nFondo: {formatear_bs(caja.monto_apertura_bs)}",
            )
            self._actualizar_estado_caja()
            self.estado_caja_cambio.emit()
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))
        except Exception as e:
            registrar_excepcion(e, "_on_abrir_caja (abrir)")
            QMessageBox.critical(self, "Error inesperado", f"No se pudo abrir la caja.\n{e}")

    # Recoge el arqueo, cierra la caja y regenera el reporte.
    def _on_cerrar_caja(self) -> None:
        try:
            caja = self.caja_service.obtener_caja_abierta()
            if not caja:
                QMessageBox.warning(self, "Caja", "No hay caja abierta para cerrar.")
                return

            arqueo = self._recoger_arqueo()
            if arqueo is None:
                return
            billetes_bs, billetes_usd, observaciones = arqueo

            caja_id = caja.id
            if caja_id is None:
                QMessageBox.critical(self, "Error", "La caja no tiene un ID valido.")
                return

            cerrada = self.caja_service.cerrar_caja(
                caja_id,
                billetes_bs,
                billetes_usd,
                observaciones,
            )
            sobrante = cerrada.sobrante_faltante_bs or Decimal("0.00")
            vuelto_txt = ""
            try:
                vuelto = self.caja_service.vuelto_entregado_bs(caja_id)
                if vuelto > 0:
                    vuelto_txt = f"\nVuelto entregado en Bs.: {formatear_bs(vuelto)}"
            except Exception as e:
                registrar_excepcion(e, "_on_cerrar_caja (vuelto)")
            QMessageBox.information(
                self,
                "Cierre Exitoso",
                f"Caja cerrada correctamente.\nSobrante/Faltante: {formatear_bs(sobrante)}"
                f"{vuelto_txt}",
            )
            self._actualizar_estado_caja()
            self.estado_caja_cambio.emit()
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        except Exception as e:
            registrar_excepcion(e, "_on_cerrar_caja")
            QMessageBox.critical(self, "Error inesperado", f"No se pudo cerrar la caja.\n{e}")
            return

        try:
            if self.reporte_service is not None:
                self.reporte_service.generar_reporte(fecha_param=hoy())
        except Exception as e:
            registrar_excepcion(e, "_on_cerrar_caja (reporte)")
            QMessageBox.warning(
                self,
                "Reporte",
                f"La caja se cerro correctamente, pero no se pudo regenerar el reporte.\n{e}",
            )

    # Pide el total en billetes de Bs para el arqueo.
    def _pedir_billetes_bs(self) -> Decimal | None:
        billetes_bs, ok_bs = QInputDialog.getDouble(
            self,
            "Cierre de Caja",
            "Ingrese el total en billetes de bolivares (solo billetes):",
            0,
            0,
            99999999,
            2,
        )
        if not ok_bs:
            return None
        return Decimal(str(billetes_bs))

    # Pide el total en billetes de USD para el arqueo.
    def _pedir_billetes_usd(self) -> Decimal | None:
        billetes_usd, ok_usd = QInputDialog.getDouble(
            self,
            "Cierre de Caja",
            "Ingrese el total en billetes de dolares (solo billetes):",
            0,
            0,
            99999999,
            2,
        )
        if not ok_usd:
            return None
        return Decimal(str(billetes_usd))

    # Dialogo de observaciones: devuelve (aceptado, texto|None).
    def _pedir_observaciones_cierre(self) -> tuple[bool, str | None]:
        """Dialogo de observaciones: devuelve (aceptado, texto|None)."""
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Observaciones Cierre")
        dialogo.resize(400, 150)
        layout_obs = QVBoxLayout(dialogo)
        layout_obs.addWidget(QLabel("Observaciones opcionales para el cierre:"))
        campo_obs = QLineEdit()
        campo_obs.setPlaceholderText("Ej: Cierre normal, sin observaciones")
        layout_obs.addWidget(campo_obs)
        botonera = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            dialogo,
        )
        botonera.accepted.connect(dialogo.accept)
        botonera.rejected.connect(dialogo.reject)
        layout_obs.addWidget(botonera)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            return True, campo_obs.text().strip() or None
        return False, None

    # Pide billetes Bs, billetes USD y observaciones.
    def _recoger_arqueo(self) -> tuple[Decimal, Decimal, str | None] | None:
        """Pide billetes Bs, billetes USD y observaciones. None si se cancela."""
        billetes_bs = self._pedir_billetes_bs()
        if billetes_bs is None:
            return None

        billetes_usd = self._pedir_billetes_usd()
        if billetes_usd is None:
            return None

        aceptado, observaciones = self._pedir_observaciones_cierre()
        if not aceptado:
            return None

        return billetes_bs, billetes_usd, observaciones

    # Crea la barra con Nueva Venta y Refrescar.
    def _crear_barra_herramientas(self) -> QHBoxLayout:
        barra = QHBoxLayout()
        self.btn_nueva = QPushButton("+ Nueva Venta")
        self.btn_nueva.setProperty("rol", "primario")
        self.btn_nueva.clicked.connect(self.nueva_venta.emit)
        barra.addWidget(self.btn_nueva)
        self.btn_refrescar = QPushButton("Refrescar")
        self.btn_refrescar.clicked.connect(self.cargar)
        barra.addWidget(self.btn_refrescar)
        barra.addStretch()
        return barra

    # Crea el selector de fechas con su boton Filtrar.
    def _crear_filtro_fechas(self) -> QHBoxLayout:
        filtro = QHBoxLayout()
        self.selector_fechas = SelectorFecha(dias_por_defecto=30)
        filtro.addWidget(self.selector_fechas)
        btn_filtrar = QPushButton("Filtrar")
        btn_filtrar.clicked.connect(self.cargar)
        filtro.addWidget(btn_filtrar)
        filtro.addStretch()
        return filtro

    # Metodos con monto > 0 de la venta, en orden de columnas.
    @staticmethod
    def _metodos_de_pago(venta: object) -> list[str]:
        """Metodos con monto > 0 de la venta, en orden de columnas."""
        etiquetas = {
            "efectivo_bs": "Efectivo Bs",
            "efectivo_usd": "Efectivo USD",
            "tarjeta": "Tarjeta",
            "pago_movil": "Pago Movil",
            "bio_pago": "BioPago",
            "transferencia": "Transferencia",
        }
        metodos: list[str] = []
        for campo, etiqueta in etiquetas.items():
            monto = getattr(venta, campo, None)
            if monto is not None and Decimal(str(monto)) > 0:
                metodos.append(etiqueta)
        return metodos

    # Celda 'Total de Venta': UNA cantidad clara.
    @staticmethod
    def _crear_celda_total(venta: object) -> QWidget:
        """Celda 'Total de Venta': UNA cantidad clara."""
        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        solo_usd = VentasPagina._metodos_de_pago(venta) == ["Efectivo USD"]
        texto = (
            formatear_usd(venta.total_usd)  # type: ignore[attr-defined]
            if solo_usd
            else formatear_bs(venta.total_bs)  # type: ignore[attr-defined]
        )
        lbl_total = QLabel(texto)
        lbl_total.setProperty("rol", "total_tabla_bs")
        layout.addWidget(lbl_total)

        return contenedor

    # (texto_celda, tooltip) para la columna 'Metodo de Pago'.
    @staticmethod
    def _resumen_metodo_pago(venta: object) -> tuple[str, str]:
        """(texto_celda, tooltip) para la columna 'Metodo de Pago'."""
        metodos = VentasPagina._metodos_de_pago(venta)

        if not metodos:
            return "-", ""
        if len(metodos) == 1:
            return metodos[0], ""
        detalle = "Pago Mixto (" + " + ".join(metodos) + ")"
        if len(metodos) >= VentasPagina.MAX_METODOS_LISTADOS:
            return "Pago Mixto", detalle
        return detalle, detalle

    # Crea la tabla de ventas con columnas por rol.
    def _crear_tabla_ventas(self) -> TablaProductos:
        columnas = [
            ("ID", 50),
            ("Factura", 140),
            ("Fecha", 150),
            ("Total de Venta", 160),
            ("Metodo de Pago", 190),
            ("Estado", 100),
        ]
        self.es_administrador = self.usuario_actual.rol == ROL_ADMINISTRADOR
        if self.es_administrador:
            columnas.append(("Acciones", 90))
        tabla = TablaProductos(columnas)
        tabla.cellDoubleClicked.connect(self._detalle_venta)
        return tabla

    # Recarga el estado de caja y el historial del rango de fechas.
    def cargar(self) -> None:
        self._actualizar_estado_caja()

        desde, hasta = self.selector_fechas.rango_datetime()

        ventas = self.controlador_ventas.historial_por_fecha(desde, hasta)

        self.tabla_ventas.setRowCount(len(ventas))
        for fila, venta in enumerate(ventas):
            self.tabla_ventas.setItem(fila, 0, QTableWidgetItem(str(venta.idventa)))
            factura = venta.numero_factura or "-"
            self.tabla_ventas.setItem(fila, 1, QTableWidgetItem(factura))
            fv = venta.fecha_venta
            fecha_str = a_local(fv).strftime("%d/%m/%Y %H:%M") if fv else ""
            self.tabla_ventas.setItem(fila, 2, QTableWidgetItem(fecha_str))
            self.tabla_ventas.setCellWidget(fila, 3, self._crear_celda_total(venta))
            texto_metodo, tooltip_metodo = self._resumen_metodo_pago(venta)
            item_metodo = QTableWidgetItem(texto_metodo)
            if tooltip_metodo:
                item_metodo.setToolTip(tooltip_metodo)
            self.tabla_ventas.setItem(fila, 4, item_metodo)
            item_estado = QTableWidgetItem(venta.estado)
            if venta.estado == "ANULADA":
                item_estado.setForeground(QColor("#dc2626"))
            else:
                item_estado.setForeground(QColor("#16a34a"))
            self.tabla_ventas.setItem(fila, 5, item_estado)

            if self.es_administrador:
                btn_anular_fila = QPushButton("🚫")
                btn_anular_fila.setProperty("rol", "anular_fila")
                btn_anular_fila.setFixedSize(48, 26)
                btn_anular_fila.setToolTip(
                    f"Anular factura {factura}" if venta.estado != "ANULADA" else "Ya anulada",
                )
                es_anulada = venta.estado == "ANULADA"
                btn_anular_fila.setEnabled(not es_anulada)
                btn_anular_fila.clicked.connect(
                    lambda _=False, f=fila: self._anular_venta(f),
                )
                self.tabla_ventas.setCellWidget(fila, 6, btn_anular_fila)

    # Anula la venta de la fila con doble autorizacion de admin.
    def _anular_venta(self, fila: int) -> None:
        item_id = self.tabla_ventas.item(fila, 0)
        if item_id is None:
            QMessageBox.information(
                self, "Anular Venta", "No se pudo identificar la venta seleccionada."
            )
            return
        idventa = int(item_id.text())

        venta = self.controlador_ventas.obtener_por_id(idventa)
        if venta is None:
            return

        if venta.estado == "ANULADA":
            return

        dialogo = DialogoAnulacion(self, numero_factura=venta.numero_factura)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        motivo = dialogo.motivo()
        autorizante = dialogo.usuario_autorizante()
        if not motivo or autorizante is None:
            return

        try:
            self.controlador_ventas.anular(
                idventa,
                motivo_anulacion=motivo,
                anulado_por=autorizante.usuario,
            )
            QMessageBox.information(
                self,
                "Exito",
                f"Venta {venta.numero_factura} anulada correctamente.\n"
                f"Motivo: {motivo}\nAutorizada por: {autorizante.usuario}",
            )
            self.cargar()
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
        except Exception as e:
            registrar_excepcion(e, "_anular_venta")
            QMessageBox.critical(
                self,
                "Error inesperado",
                f"No se pudo anular la venta.\n{e}",
            )

    # Muestra el detalle de la venta seleccionada.
    def _detalle_venta(self) -> None:
        fila = self.tabla_ventas.currentRow()
        if fila < 0:
            QMessageBox.information(
                self, "Detalle", "Selecciona una venta en la tabla para ver su detalle."
            )
            return

        item_id = self.tabla_ventas.item(fila, 0)
        if item_id is None:
            return
        idventa = int(item_id.text())
        item_factura = self.tabla_ventas.item(fila, 1)
        factura = item_factura.text() if item_factura else "-"

        detalles = self.controlador_ventas.obtener_detalles(idventa)
        if not detalles:
            QMessageBox.information(self, "Detalle", "Esta venta no tiene productos registrados.")
            return

        lineas = [f"Factura: {factura}\n", "=" * 30]
        for det in detalles:
            producto = self.controlador_productos.obtener_por_id(det.producto_id)
            nombre = producto.nombre_producto if producto else f"ID {det.producto_id}"
            lineas.append(f"{det.cantidad}x {nombre} = {formatear_bs(det.subtotal_bs)}")
        lineas.append("=" * 30)

        QMessageBox.information(
            self,
            f"Detalle de Venta - {factura}",
            "\n".join(lineas),
        )

