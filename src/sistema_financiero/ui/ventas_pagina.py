# ============================================================
# ARCHIVO: ui/ventas_pagina.py  (PAGINA DE VENTAS)
# ============================================================
# Widget independiente para el historial y gestion de ventas.
#
# QUE MUESTRA:
#   1. Panel "Caja del Turno": estado de la caja (ABIERTA/CERRADA),
#      fondo, hora de apertura y botones Abrir/Cerrar Caja. La caja
#      vive AQUI (unida a ventas): sin caja abierta no se vende.
#   2. Botonera: Nueva Venta, Anular Venta, Refrescar.
#   3. Filtro de fechas (desde / hasta) para acotar el historial.
#   4. Tabla de ventas con doble clic para ver detalle.
#
# SENIALES (para VentanaPrincipal):
#   - nueva_venta: el usuario quiere registrar una venta.
#   - estado_caja_cambio: se abrio o cerro la caja del turno (la
#     ventana principal refresca el indicador de la barra de estado).
#
# QUE SE PUEDE MODIFICAR:
#   - Estilos (colores, fuentes, tamaños) en _crear_barra_herramientas().
#   - Columnas y anchos en _crear_tabla_ventas().
#   - Textos, etiquetas, placeholders.
#   - Logica de filtro en cargar().
#
# QUE NO SE DEBE TOCAR:
#   - Nombre de la clase (VentasPagina).
#   - Firma del __init__ (usuario_actual, controlador_ventas,
#     controlador_productos, caja_service, reporte_service).
#   - Las seniales nueva_venta y estado_caja_cambio.
#   - Los metodos _on_abrir_caja / _on_cerrar_caja (regla de negocio:
#     la caja es el turno unico que permite vender).
# ============================================================
from decimal import Decimal

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
from ..utils import formatear_bs, formatear_usd
from ..utils.fecha import hoy
from ..utils.logging_setup import registrar_excepcion
from .widgets import SelectorFecha, TablaProductos, TituloPagina


# ============ PAGINA DE VENTAS ============
# --- NO TOCAR: clase, seniales, conexiones a controladores.
# --- MODIFICABLE: estilos, columnas de tabla, textos, layout.
class VentasPagina(QWidget):
    # --- NO TOCAR: seniales para VentanaPrincipal.
    nueva_venta = pyqtSignal()
    estado_caja_cambio = pyqtSignal()

    # --- NO TOCAR: firma del constructor (recibe controladores).
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

        # --- MODIFICABLE: layout, titulo, estilos.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        layout.addWidget(TituloPagina("Ventas"))

        # Caja unida a ventas: el panel del turno va al inicio de la pagina.
        layout.addWidget(self._crear_panel_caja())
        layout.addSpacing(10)

        layout.addLayout(self._crear_barra_herramientas())
        layout.addSpacing(10)

        layout.addLayout(self._crear_filtro_fechas())
        layout.addSpacing(10)

        # --- MODIFICABLE: creacion de tabla de ventas.
        self.tabla_ventas = self._crear_tabla_ventas()
        layout.addWidget(self.tabla_ventas, 1)

        # --- NO TOCAR: carga inicial de datos.
        self.cargar()

    # ------------------------------------------------------------------
    # PANEL CAJA DEL TURNO (caja unida a ventas)
    # ------------------------------------------------------------------
    # --- NO TOCAR: la caja se abre/cierra aqui (regla de negocio).
    def _crear_panel_caja(self) -> QGroupBox:
        grupo = QGroupBox("Caja del Turno")
        formulario = QFormLayout(grupo)

        self.lbl_estado_caja = QLabel("---")
        self.lbl_estado_caja.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        formulario.addRow("Estado:", self.lbl_estado_caja)

        self.lbl_fondo_caja = QLabel("---")
        formulario.addRow("Fondo de Apertura (Bs.):", self.lbl_fondo_caja)

        self.lbl_hora_caja = QLabel("---")
        formulario.addRow("Hora Apertura:", self.lbl_hora_caja)

        self.lbl_observaciones_caja = QLabel("--")
        formulario.addRow("Observaciones:", self.lbl_observaciones_caja)
        self.lbl_observaciones_caja.setVisible(False)

        botones = QHBoxLayout()
        self.btn_abrir_caja = QPushButton("Abrir Caja")
        self.btn_abrir_caja.setProperty("rol", "caja_abrir")
        self.btn_abrir_caja.clicked.connect(self._on_abrir_caja)
        botones.addWidget(self.btn_abrir_caja)

        self.btn_cerrar_caja = QPushButton("Cerrar Caja")
        self.btn_cerrar_caja.setProperty("rol", "caja_cerrar")
        self.btn_cerrar_caja.clicked.connect(self._on_cerrar_caja)
        self.btn_cerrar_caja.setVisible(False)
        botones.addWidget(self.btn_cerrar_caja)
        botones.addStretch()
        formulario.addRow("", botones)

        return grupo

    # --- NO TOCAR: refleja el estado real de la caja en el panel.
    def _actualizar_estado_caja(self) -> None:
        caja = self.caja_service.obtener_caja_abierta()

        if caja:
            self.lbl_estado_caja.setText("ABIERTA")
            self.lbl_estado_caja.setStyleSheet(
                "color: #16a34a; font-size: 14px; font-weight: bold; padding: 5px;"
            )
            self.lbl_fondo_caja.setText(formatear_bs(caja.monto_apertura_bs))
            self.lbl_hora_caja.setText(f"Abierta: {caja.fecha_apertura.strftime('%H:%M:%S')}")
            self.lbl_observaciones_caja.setText(caja.observaciones or "--")
            self.lbl_observaciones_caja.setVisible(True)

            self.btn_abrir_caja.setVisible(False)
            self.btn_cerrar_caja.setVisible(True)
            self.btn_cerrar_caja.setEnabled(True)
        else:
            self.lbl_estado_caja.setText("CERRADA")
            self.lbl_estado_caja.setStyleSheet(
                "color: #dc2626; font-size: 14px; font-weight: bold; padding: 5px;"
            )
            self.lbl_fondo_caja.setText("---")
            self.lbl_hora_caja.setText("---")
            self.lbl_observaciones_caja.setVisible(False)

            self.btn_abrir_caja.setVisible(True)
            self.btn_abrir_caja.setEnabled(True)
            self.btn_cerrar_caja.setVisible(False)
            self.btn_cerrar_caja.setEnabled(False)

    # --- NO TOCAR: apertura de caja (pide el monto inicial).
    def _on_abrir_caja(self) -> None:
        try:
            self.caja_service.validar_caja_abierta()
            QMessageBox.warning(self, "Caja Abierta", "Ya existe una caja abierta.")
            return
        except ValueError:
            pass  # No hay caja abierta: se puede abrir
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
        if monto <= 0:
            QMessageBox.warning(
                self, "Monto Invalido", "El monto de apertura debe ser mayor a cero."
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

    # --- NO TOCAR: cierre de caja (arqueo + regenera el reporte del dia).
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
            # Informativo: el vuelto en Bs. de los pagos en divisa recortados
            # ya viene descontado del esperado; se muestra para que el cajero
            # entienda el arqueo. Si falla, no bloquea el cierre.
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

        # Cerrar caja = cerrar el dia: regenerar el reporte diario para que
        # quede consolidado con las ventas del turno (todos los pagos).
        # Se hace APARTE del cierre: si el reporte falla, la caja ya quedo
        # cerrada y solo se avisa (no debe parecer que fallo el cierre).
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

    # --- Dialogos del arqueo de cierre: None/cancelado = el usuario cancelo.
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

    # --- Arqueo completo: None si el usuario cancela en cualquier paso.
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

    # --- MODIFICABLE: botones, colores, textos en la barra de herramientas.
    def _crear_barra_herramientas(self) -> QHBoxLayout:
        barra = QHBoxLayout()
        # --- MODIFICABLE: estilo y texto del boton Nueva Venta.
        self.btn_nueva = QPushButton("+ Nueva Venta")
        self.btn_nueva.setProperty("rol", "primario")
        # --- NO TOCAR: senial de ventana nueva.
        self.btn_nueva.clicked.connect(self.nueva_venta.emit)
        barra.addWidget(self.btn_nueva)
        # --- MODIFICABLE: texto del boton Anular (color en ui/estilos.py).
        self.btn_anular = QPushButton("Anular Venta")
        self.btn_anular.setProperty("rol", "peligro")
        # --- NO TOCAR: conexion a _anular_venta.
        self.btn_anular.clicked.connect(self._anular_venta)
        barra.addWidget(self.btn_anular)
        self.btn_refrescar = QPushButton("Refrescar")
        self.btn_refrescar.clicked.connect(self.cargar)
        barra.addWidget(self.btn_refrescar)
        barra.addStretch()
        return barra

    # --- MODIFICABLE: filtro de fechas (SelectorFecha, boton Filtrar).
    def _crear_filtro_fechas(self) -> QHBoxLayout:
        filtro = QHBoxLayout()
        self.selector_fechas = SelectorFecha(dias_por_defecto=30)
        filtro.addWidget(self.selector_fechas)
        btn_filtrar = QPushButton("Filtrar")
        btn_filtrar.clicked.connect(self.cargar)
        filtro.addWidget(btn_filtrar)
        filtro.addStretch()
        return filtro

    # --- MODIFICABLE: columnas y anchos de la tabla de ventas.
    def _crear_tabla_ventas(self) -> TablaProductos:
        columnas = [
            ("ID", 50),
            ("Factura", 140),
            ("Fecha", 150),
            ("Total Bs", 100),
            ("Total USD", 100),
            ("Transf.", 90),
            ("Estado", 100),
        ]
        tabla = TablaProductos(columnas)
        # --- NO TOCAR: conexion a detalle de venta.
        tabla.cellDoubleClicked.connect(self._detalle_venta)
        return tabla

    # --- MODIFICABLE: logica de carga y poblado de la tabla.
    def cargar(self) -> None:
        # El panel de caja se refresca en cada carga (estado del turno).
        self._actualizar_estado_caja()

        desde, hasta = self.selector_fechas.rango_datetime()

        # --- NO TOCAR: consulta al controlador de ventas.
        ventas = self.controlador_ventas.historial_por_fecha(desde, hasta)

        self.tabla_ventas.setRowCount(len(ventas))
        for fila, venta in enumerate(ventas):
            self.tabla_ventas.setItem(fila, 0, QTableWidgetItem(str(venta.idventa)))
            factura = venta.numero_factura or "-"
            self.tabla_ventas.setItem(fila, 1, QTableWidgetItem(factura))
            fv = venta.fecha_venta
            fecha_str = fv.strftime("%d/%m/%Y %H:%M")
            self.tabla_ventas.setItem(fila, 2, QTableWidgetItem(fecha_str))
            self.tabla_ventas.setItem(fila, 3, QTableWidgetItem(formatear_bs(venta.total_bs)))
            self.tabla_ventas.setItem(fila, 4, QTableWidgetItem(formatear_usd(venta.total_usd)))
            self.tabla_ventas.setItem(fila, 5, QTableWidgetItem(formatear_bs(venta.transferencia)))
            item_estado = QTableWidgetItem(venta.estado)
            # --- MODIFICABLE: colores de estado (anulada rojo, completada verde).
            if venta.estado == "ANULADA":
                item_estado.setForeground(QColor("#dc2626"))
            else:
                item_estado.setForeground(QColor("#16a34a"))
            self.tabla_ventas.setItem(fila, 6, item_estado)

    # --- NO TOCAR: logica de anulacion de venta (reversa de stock incluida).
    def _anular_venta(self) -> None:
        fila = self.tabla_ventas.currentRow()
        if fila < 0:
            # Nunca fallar en silencio: avisar que falta seleccionar la venta.
            QMessageBox.information(
                self,
                "Anular Venta",
                "Selecciona primero la venta que quieres anular en la tabla.",
            )
            return

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

        # --- MODIFICABLE: texto de confirmacion de anulacion.
        respuesta = QMessageBox.question(
            self,
            "Confirmar anulacion",
            f"Seguro que deseas anular la factura {venta.numero_factura}?\n"
            "El stock de los productos se devolvera automaticamente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        # --- NO TOCAR: ejecucion de la anulacion via controlador.
        if respuesta == QMessageBox.StandardButton.Yes:
            try:
                self.controlador_ventas.anular(idventa)
                QMessageBox.information(
                    self,
                    "Exito",
                    f"Venta {venta.numero_factura} anulada correctamente.",
                )
                self.cargar()
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))
            except Exception as e:
                # Nunca dejar el fallo invisible: registrar y avisar.
                registrar_excepcion(e, "_anular_venta")
                QMessageBox.critical(
                    self,
                    "Error inesperado",
                    f"No se pudo anular la venta.\n{e}",
                )

    # --- NO TOCAR: logica de detalle de venta (doble clic en fila).
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

        # ADVERTENCIA: detalles viene de obtener_detalles() con sesion cerrada.
        # Accede solo a columnas directas (producto_id). NO hagas det.producto.nombre.
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
