import html
from datetime import datetime
from decimal import Decimal

from PyQt6.QtGui import QTextDocument
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..utils import (
    METODO_PAGO_BIO_PAGO,
    METODO_PAGO_EFECTIVO_BS,
    METODO_PAGO_EFECTIVO_USD,
    METODO_PAGO_PAGO_MOVIL,
    METODO_PAGO_TARJETA,
    METODO_PAGO_TRANSFERENCIA,
    MONEDA_BS,
    MONEDA_USD,
    es_medida,
    formatear_bs,
    formatear_peso_kg,
    formatear_stock,
    formatear_usd,
)
from ..utils.logging_setup import registrar_excepcion

NOMBRE_NEGOCIO = "ABASTO PA' QUE JESUS"

ETIQUETAS_METODO_FACTURA: dict[str, str] = {
    METODO_PAGO_EFECTIVO_BS: "Efectivo Bs",
    METODO_PAGO_EFECTIVO_USD: "Efectivo USD",
    METODO_PAGO_TARJETA: "Tarjeta",
    METODO_PAGO_PAGO_MOVIL: "Pago Movil",
    METODO_PAGO_BIO_PAGO: "BioPago",
    METODO_PAGO_TRANSFERENCIA: "Transferencia",
}


# Convierte a Decimal un valor que viaja dentro de un dict tipado.
def _dec(valor: object) -> Decimal:
    """Convierte a Decimal un valor que viaja dentro de un dict tipado."""
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float, str)):
        return Decimal(str(valor))
    return Decimal("0.00")


# Construye el HTML (subset Qt rich text) de la factura.
def generar_html_factura(
    *,
    numero_factura: str | None,
    fecha_local: datetime,
    nombre_cajero: str | None,
    tasa_venta: Decimal | None,
    total_bs: Decimal,
    total_usd: Decimal,
    items: list[dict[str, object]],
    pagos: list[dict[str, object]],
) -> str:
    """Construye el HTML (subset Qt rich text) de la factura."""
    numero = html.escape(numero_factura or "-")
    fecha = html.escape(fecha_local.strftime("%d/%m/%Y %H:%M"))
    cajero = html.escape(nombre_cajero or "-")

    filas_items = ""
    for item in items:
        nombre = html.escape(str(item.get("nombre", "")))
        if es_medida(str(item.get("tipo_venta", ""))):
            cantidad = formatear_peso_kg(_dec(item.get("cantidad"))) or "-"
        else:
            cantidad = formatear_stock(_dec(item.get("cantidad")))
        precio = formatear_bs(_dec(item.get("precio")))
        subtotal = formatear_bs(_dec(item.get("subtotal")))
        filas_items += (
            f"<tr><td>{cantidad}</td><td>{nombre}</td>"
            f'<td align="right">{precio}</td><td align="right">{subtotal}</td></tr>'
        )

    filas_pagos = ""
    for pago in pagos:
        metodo = ETIQUETAS_METODO_FACTURA.get(
            str(pago.get("metodo", "")), str(pago.get("metodo", ""))
        )
        moneda = str(pago.get("moneda", MONEDA_BS))
        monto = _dec(pago.get("monto"))
        monto_txt = formatear_usd(monto) if moneda == MONEDA_USD else formatear_bs(monto)
        aplicado = formatear_bs(_dec(pago.get("monto_bs")))
        vuelto = _dec(pago.get("vuelto_bs"))
        vuelto_txt = formatear_bs(vuelto) if vuelto > 0 else "-"
        referencia = html.escape(str(pago.get("referencia") or ""))
        filas_pagos += (
            f'<tr><td>{metodo}</td><td align="right">{monto_txt}</td>'
            f'<td align="right">{aplicado}</td><td align="right">{vuelto_txt}</td>'
            f"<td>{referencia}</td></tr>"
        )

    fila_tasa = ""
    if tasa_venta is not None:
        fila_tasa = (
            '<tr><td colspan="4" align="right"><font size="2">'
            f"Tasa usada: {formatear_bs(tasa_venta)} / USD"
            "</font></td></tr>"
        )

    fila_usd = ""
    if total_usd > 0:
        fila_usd = (
            '<tr><td colspan="4" align="right"><font size="2">'
            f"Equivalente USD: {formatear_usd(total_usd)}"
            "</font></td></tr>"
        )

    return "\n".join(
        [
            "<div style=\"font-family:'Segoe UI', Arial, sans-serif;\">",
            '<div align="center">'
            f'<font size="6" color="#1e3a8a"><b>{html.escape(NOMBRE_NEGOCIO)}</b></font><br>'
            f'<font size="4"><b>FACTURA {numero}</b></font><br>'
            f'<font size="2" color="#475569">Fecha: {fecha} · Cajero: {cajero}</font>'
            "</div>",
            "<hr>",
            '<table width="100%" border="0" cellspacing="0" cellpadding="4">',
            '<tr bgcolor="#eff6ff"><td><b>Cant.</b></td><td><b>Producto</b></td>'
            '<td align="right"><b>P. Unitario</b></td><td align="right"><b>Subtotal</b></td></tr>',
            filas_items,
            "</table>",
            '<table width="100%" border="0" cellspacing="0" cellpadding="4">',
            fila_tasa,
            '<tr><td colspan="4" align="right">'
            f'<font size="5"><b>TOTAL {formatear_bs(total_bs)}</b></font>'
            "</td></tr>",
            fila_usd,
            "</table>",
            '<table width="100%" border="0" cellspacing="0" cellpadding="4">',
            '<tr bgcolor="#eff6ff"><td><b>Metodo</b></td><td align="right"><b>Monto</b></td>'
            '<td align="right"><b>Aplicado Bs.</b></td><td align="right"><b>Vuelto Bs.</b></td>'
            "<td><b>Referencia</b></td></tr>",
            filas_pagos,
            "</table>",
            '<div align="center"><font size="2" color="#475569">Gracias por su compra</font></div>',
            "</div>",
        ]
    )


# DialogoFactura: Factura con previsualizacion, impresion y PDF.
class DialogoFactura(QDialog):
    """Factura imprimible de una venta recien registrada."""

    # Monta el dialogo de factura con preview, imprimir, PDF y cerrar.
    def __init__(
        self,
        *,
        numero_factura: str | None,
        fecha_venta: datetime,
        nombre_cajero: str | None,
        tasa_venta: Decimal | None,
        total_bs: Decimal,
        total_usd: Decimal,
        items: list[dict[str, object]],
        pagos: list[dict[str, object]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Factura")
        self.resize(640, 720)

        self._numero_factura = numero_factura or "venta"
        self.html = generar_html_factura(
            numero_factura=numero_factura,
            fecha_local=fecha_venta,
            nombre_cajero=nombre_cajero,
            tasa_venta=tasa_venta,
            total_bs=total_bs,
            total_usd=total_usd,
            items=items,
            pagos=pagos,
        )

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        self.preview.setHtml(self.html)

        self.btn_imprimir = QPushButton("Imprimir…")
        self.btn_imprimir.setProperty("rol", "primario")
        self.btn_imprimir.setMinimumHeight(36)
        self.btn_imprimir.clicked.connect(self._imprimir)

        self.btn_pdf = QPushButton("Guardar PDF…")
        self.btn_pdf.setProperty("rol", "secundario")
        self.btn_pdf.setMinimumHeight(36)
        self.btn_pdf.clicked.connect(self._guardar_pdf)

        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.setProperty("rol", "secundario")
        self.btn_cerrar.setMinimumHeight(36)
        self.btn_cerrar.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, 1)
        fila_botones = QHBoxLayout()
        fila_botones.addWidget(self.btn_imprimir)
        fila_botones.addWidget(self.btn_pdf)
        fila_botones.addStretch(1)
        fila_botones.addWidget(self.btn_cerrar)
        layout.addLayout(fila_botones)

    # Devuelve un QTextDocument con el HTML de la factura (para imprimir/PDF).
    def _documento(self) -> QTextDocument:
        """Devuelve un QTextDocument con el HTML de la factura (para imprimir/PDF)."""
        doc = QTextDocument()
        doc.setHtml(self.html)
        return doc

    # Envia la factura a la impresora elegida por el usuario.
    def _imprimir(self) -> None:
        """Envia la factura a la impresora elegida por el usuario."""
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dialogo = QPrintDialog(printer, self)
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return
            self._documento().print(printer)
        except Exception as e:
            registrar_excepcion(e, "DialogoFactura._imprimir")
            QMessageBox.critical(
                self,
                "Imprimir",
                f"No se pudo imprimir la factura.\n{e}",
            )

    # Guarda la factura como PDF real (QPrinter en modo PdfFormat).
    def _guardar_pdf(self) -> None:
        """Guarda la factura como PDF real (QPrinter en modo PdfFormat)."""
        try:
            ruta, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar factura PDF",
                f"factura_{self._numero_factura}.pdf",
                "PDF (*.pdf)",
            )
            if not ruta:
                return
            if not ruta.lower().endswith(".pdf"):
                ruta += ".pdf"
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(ruta)
            self._documento().print(printer)
        except Exception as e:
            registrar_excepcion(e, "DialogoFactura._guardar_pdf")
            QMessageBox.critical(
                self,
                "Guardar PDF",
                f"No se pudo guardar el PDF.\n{e}",
            )

