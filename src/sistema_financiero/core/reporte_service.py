# ============================================================
# IMPORTACIONES
# ============================================================
# datetime: para manejar fechas (date = solo dia, datetime = con hora).
#   - date.today(): fecha actual.
#   - datetime.now(): fecha + hora actual.
# Decimal: tipo exacto para montos monetarios (evita errores de redondeo
#   de float como 0.1 + 0.2 = 0.30000000000000004).
from datetime import date, datetime
from decimal import Decimal

# openpyxl: libreria para crear/modificar archivos Excel (.xlsx).
#   - Workbook: representa un libro Excel completo.
#   - styles: formato de celdas (bordes, fuentes, colores, alineacion).
#
# Por que openpyxl y no pandas?
#   - pandas es mas pesado (dependencias adicionales).
#   - openpyxl nos da control fino sobre el formato (celdas,
#     bordes, titulos). Ideal para reportes bonitos.
#   - La app ya tiene openpyxl como dependencia.
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

# SQLModel: consultas a la BD.
#   - Session: la sesion de conexion.
#   - select: construye consultas SELECT.
from sqlmodel import select

# Importamos los modelos que necesitamos consultar.
#   - Producto: para contar stock bajo/sin stock.
#   - ReporteDiario: el modelo que vamos a crear/consultar.
#   - Venta, VentaDetalle: para consolidar las ventas del dia.
from ..models import Producto, ReporteDiario, Venta, VentaDetalle, get_session

# ----------------------------------------------------------
# CONSTANTES DE FORMATO PARA EXCEL
# ----------------------------------------------------------
# Las declaramos al inicio (fuera de la clase) para:
#   1. Reutilizarlas en varios metodos.
#   2. Evitar "magic numbers/strings" repetidos.
#   3. Si queremos cambiar el color del encabezado, solo
#      cambiamos esta linea.

# _THIN_BORDER: borde delgado para todas las celdas de la tabla.
_THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)

# _HEADER_FILL: color de fondo para las celdas de encabezado.
# El color "1a1a2e" es un azul oscuro (el mismo de la barra lateral).
_HEADER_FILL = PatternFill(start_color="1a1a2e", end_color="1a1a2e", fill_type="solid")

# _HEADER_FONT: fuente para los encabezados (blanco, negrita).
_HEADER_FONT = Font(bold=True, color="ffffff", size=11)

# _COL_ESTADO: indice de la columna "Estado" en la hoja de stock.
# Usamos una constante para evitar el "magic number" 5.
_COL_ESTADO: int = 5


# ============================================================
# SERVICIO: ReporteService
# ============================================================
# Servicio para generacion de reportes diarios y exportacion.
#
# QUE HACE:
#   - generar_reporte(): consolida LAS VENTAS de un dia en un ReporteDiario.
#   - obtener_por_fecha(): busca si ya existe un reporte para una fecha.
#   - listar_por_rango(): historial de reportes entre dos fechas.
#   - exportar_excel(): crea un archivo .xlsx con formato profesional.
#
# QUE NO HACE:
#   - No modifica ventas ni productos.
#   - No tiene metodos para crear/editar/eliminar reportes manualmente.
#     Los reportes se GENERAN automaticamente a partir de las ventas.
#
# Flujo tipico:
#   1. Usuario hace clic en "Cerrar Dia"
#   2. ReporteService.generar_reporte(fecha_hoy)
#   3. Se consultan todas las ventas COMPLETADA del dia
#   4. Se suman totales y metodos de pago
#   5. Se cuentan productos stock bajo / sin stock
#   6. Se guarda el ReporteDiario en BD
#   7. (opcional) Se exporta a Excel con exportar_excel()
# ============================================================
class ReporteService:
    # ------------------------------------------------------------------
    # generar_reporte(): genera (o regenera) el reporte diario
    # ------------------------------------------------------------------
    # Parametros:
    #   - fecha_param: la fecha del reporte (default = hoy).
    #
    # QUE HACE:
    #   1. Busca todas las ventas COMPLETADA de esa fecha.
    #   2. Suma totales (VES + USD) y metodos de pago.
    #   3. Cuenta la cantidad de productos vendidos.
    #   4. Cuenta productos con stock bajo o sin stock.
    #   5. Guarda (o actualiza) el ReporteDiario en BD.
    #
    # QUE PASA SI YA EXISTE UN REPORTE PARA ESA FECHA?
    #   - Lo reemplaza (primero lo elimina). Esto permite
    #     regenerar el reporte si se anulo una venta despues
    #     de haber cerrado el dia.
    #
    # Por que eliminar y no actualizar?
    #   - Es mas simple que calcular diferencias.
    #   - El reporte se genera desde cero con los datos actuales.
    # ------------------------------------------------------------------
    def generar_reporte(
        self,
        fecha_param: date | None = None,
    ) -> ReporteDiario:
        """Genera el reporte diario consolidando ventas de la fecha indicada."""
        # Si no se paso una fecha, usar la de hoy.
        hoy = fecha_param or date.today()

        with get_session() as session:
            # ----------------------------------------------------------
            # PASO 1: Buscar todas las ventas COMPLETADA del dia
            # ----------------------------------------------------------
            # Filtramos por:
            #   - fecha_venta entre las 00:00:00 y 23:59:59 del dia.
            #   - estado = "COMPLETADA" (las anuladas no cuentan).
            #
            # Por que usar datetime range y no solo date?
            #   - fecha_venta es un datetime (incluye hora).
            #   - Si solo comparamos con date, SQLite hace cast implicito
            #     que puede ser impredecible.
            #   - Con datetime range nos aseguramos de capturar TODO el dia.
            desde = datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0)
            hasta = datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59)

            ventas = session.exec(
                select(Venta).where(
                    Venta.fecha_venta >= desde,  # type: ignore[operator]
                    Venta.fecha_venta <= hasta,  # type: ignore[operator]
                    Venta.estado == "COMPLETADA",
                )
            ).all()

            # ----------------------------------------------------------
            # PASO 2: Calcular totales consolidados
            # ----------------------------------------------------------
            # Inicializar todos los totales en cero.
            # Usamos Decimal("0.00") para precision monetaria exacta.
            total_bs = Decimal("0.00")
            total_usd = Decimal("0.00")
            cantidad_ventas = len(ventas)
            cantidad_productos = 0
            efectivo_bs = Decimal("0.00")
            efectivo_usd = Decimal("0.00")
            tarjeta = Decimal("0.00")
            pago_movil = Decimal("0.00")
            bio_pago = Decimal("0.00")

            # Recorrer cada venta y sumar sus montos.
            for v in ventas:
                total_bs += v.total_bs
                total_usd += v.total_usd
                efectivo_bs += v.efectivo_bs
                efectivo_usd += v.efectivo_usd
                tarjeta += v.tarjeta
                pago_movil += v.pago_movil
                bio_pago += v.bio_pago

                # Contar la cantidad de productos en esta venta.
                # Obtenemos los detalles (lineas de productos).
                detalles = session.exec(
                    select(VentaDetalle).where(VentaDetalle.venta_id == v.idventa)
                ).all()
                cantidad_productos += sum(d.cantidad for d in detalles)

            # ----------------------------------------------------------
            # PASO 3: Contar alertas de stock
            # ----------------------------------------------------------
            # Productos con stock_actual entre 1 y stock_minimo → "stock bajo".
            # Productos con stock_actual = 0 → "sin stock".
            productos = session.exec(select(Producto)).all()
            stock_bajo = sum(1 for p in productos if 0 < p.stock_actual <= p.stock_minimo)
            sin_stock = sum(1 for p in productos if p.stock_actual == 0)

            # ----------------------------------------------------------
            # PASO 4: Guardar (o reemplazar) el reporte
            # ----------------------------------------------------------
            # Si ya existe un reporte para esta fecha, lo eliminamos.
            # Esto permite regenerar sin duplicados.
            reporte_existente = session.exec(
                select(ReporteDiario).where(ReporteDiario.fecha == hoy)
            ).first()
            if reporte_existente:
                session.delete(reporte_existente)
                session.flush()

            # Crear el nuevo reporte.
            reporte = ReporteDiario(
                fecha=hoy,
                total_ventas_bs=total_bs,
                total_ventas_usd=total_usd,
                cantidad_ventas=cantidad_ventas,
                cantidad_productos_vendidos=cantidad_productos,
                productos_stock_bajo=stock_bajo,
                productos_sin_stock=sin_stock,
                efectivo_bs=efectivo_bs,
                efectivo_usd=efectivo_usd,
                tarjeta=tarjeta,
                pago_movil=pago_movil,
                bio_pago=bio_pago,
                fecha_generacion=datetime.now(),
            )
            session.add(reporte)
            session.commit()
            session.refresh(reporte)

        return reporte

    # ------------------------------------------------------------------
    # obtener_por_fecha(): busca un reporte por fecha
    # ------------------------------------------------------------------
    def obtener_por_fecha(self, fecha_param: date | None = None) -> ReporteDiario | None:
        """Devuelve el reporte de una fecha, o None si no existe."""
        hoy = fecha_param or date.today()
        with get_session() as session:
            return session.exec(select(ReporteDiario).where(ReporteDiario.fecha == hoy)).first()

    # ------------------------------------------------------------------
    # listar_por_rango(): historial de reportes entre dos fechas
    # ------------------------------------------------------------------
    def listar_por_rango(
        self,
        desde: date,
        hasta: date,
    ) -> list[ReporteDiario]:
        """Devuelve todos los reportes entre dos fechas (ordenados descendente)."""
        with get_session() as session:
            stmt = (
                select(ReporteDiario)
                .where(
                    ReporteDiario.fecha >= desde,
                    ReporteDiario.fecha <= hasta,
                )
                .order_by(ReporteDiario.fecha.desc())  # type: ignore[attr-defined]
            )
            return list(session.exec(stmt).all())

    # ------------------------------------------------------------------
    # exportar_excel(): genera un archivo Excel con el reporte
    # ------------------------------------------------------------------
    # Crea un archivo .xlsx con 3 hojas:
    #   1. "Reporte Diario" → resumen del dia (totales, metodos de pago).
    #   2. "Ventas del Dia" → lista detallada de cada venta.
    #   3. "Alertas de Stock" → productos que necesitan reabastecimiento.
    #
    # El archivo tiene formato profesional:
    #   - Encabezados con fondo oscuro y texto blanco.
    #   - Bordes en todas las celdas.
    #   - Numeros formateados con 2 decimales.
    #   - Columnas con ancho ajustado automaticamente.
    #
    # Por que dividir en metodos privados (_exportar_*)?
    #   - Cada hoja es independiente (se puede modificar sin afectar las otras).
    #   - exportar_excel() se lee como un indice: "crea hoja 1, hoja 2, hoja 3".
    #   - Ruff recomienda metodos con menos de 50 declaraciones.
    # ------------------------------------------------------------------
    def exportar_excel(
        self,
        reporte_id: int,
        ruta_archivo: str,
    ) -> str:
        """Exporta un reporte a Excel. Devuelve la ruta del archivo."""
        # Cargar datos desde la BD (reporte, ventas, stock).
        reporte_opt, ventas, stock_bajo, sin_stock = self._cargar_datos_reporte(reporte_id)
        if reporte_opt is None:
            raise ValueError(f"No existe el reporte con ID {reporte_id}")
        reporte = reporte_opt

        # Crear el libro de Excel.
        wb = Workbook()

        # Crear cada hoja llamando a metodos separados.
        self._exportar_hoja_resumen(wb, reporte)
        self._exportar_hoja_ventas(wb, ventas)
        self._exportar_hoja_stock(wb, stock_bajo, sin_stock)

        # Guardar el archivo.
        wb.save(ruta_archivo)
        return ruta_archivo

    # ------------------------------------------------------------------
    # _cargar_datos_reporte(): carga los datos necesarios para exportar
    # ------------------------------------------------------------------
    # Metodo privado (empieza con _) que agrupa TODAS las consultas a la
    # BD necesarias para generar el Excel. Separado de exportar_excel()
    # para mantener cada metodo enfocado en una sola tarea.
    def _cargar_datos_reporte(
        self,
        reporte_id: int,
    ) -> tuple[
        ReporteDiario | None,
        list[Venta],
        list[Producto],
        list[Producto],
    ]:
        """Carga reporte, ventas, stock bajo y sin stock desde la BD."""
        with get_session() as session:
            reporte = session.get(ReporteDiario, reporte_id)
            if not reporte:
                return (None, [], [], [])

            # Calcular el rango de fechas para las ventas.
            desde = datetime(
                reporte.fecha.year,
                reporte.fecha.month,
                reporte.fecha.day,
                0,
                0,
                0,
            )
            hasta = datetime(
                reporte.fecha.year,
                reporte.fecha.month,
                reporte.fecha.day,
                23,
                59,
                59,
            )

            # Obtener las ventas COMPLETADA del dia.
            ventas = list(
                session.exec(
                    select(Venta).where(
                        Venta.fecha_venta >= desde,  # type: ignore[operator]
                        Venta.fecha_venta <= hasta,  # type: ignore[operator]
                        Venta.estado == "COMPLETADA",
                    )
                ).all()
            )

            # Obtener productos con stock bajo/sin stock.
            todos = session.exec(select(Producto)).all()
            stock_bajo = [p for p in todos if 0 < p.stock_actual <= p.stock_minimo]
            sin_stock = [p for p in todos if p.stock_actual == 0]

        return (reporte, ventas, stock_bajo, sin_stock)

    # ------------------------------------------------------------------
    # _exportar_hoja_resumen(): escribe la hoja de resumen del dia
    # ------------------------------------------------------------------
    # Parametros:
    #   - wb: el libro de Excel activo.
    #   - reporte: el ReporteDiario con los totales.
    #
    # Formato:
    #   - Fila 1: Titulo centrado (fusiona columnas A:B).
    #   - Fila 3: Encabezados (Concepto | Valor).
    #   - Fila 4+: Datos del reporte.
    # ------------------------------------------------------------------
    def _exportar_hoja_resumen(self, wb: Workbook, reporte: ReporteDiario) -> None:
        """Escribe la hoja 'Reporte Diario' con el resumen del dia."""
        # wb.active devuelve la hoja activa del libro.
        # Normalmente Workbook() crea 1 hoja llamada "Sheet", pero en
        # algunos estados internos de openpyxl puede devolver None.
        # Por eso verificamos: si ws es None, creamos una hoja nueva
        # en la posicion 0 con wb.create_sheet().
        ws = wb.active
        if ws is None:
            # Si no hay hoja activa, creamos una explicitamente.
            # create_sheet() recibe: (nombre, indice).
            # Indice 0 = primera posicion.
            ws = wb.create_sheet("Reporte Diario", 0)
        else:
            # Si existe hoja activa, solo le cambiamos el nombre.
            ws.title = "Reporte Diario"
        ws.page_setup.orientation = "portrait"

        # ws.sheet_properties.pageSetUpPr.fitToPage: ajusta la hoja
        # al ancho de la pagina al imprimir (escalado automatico).
        #
        # Por que el error "None no tiene atributo fitToPage"?
        #   - pageSetUpPr es un objeto PageSetupProperties que openpyxl
        #     crea automaticamente dentro de sheet_properties.
        #   - En teoria nunca es None, pero en la practica el usuario
        #     reporta que si. Podria ser una diferencia de version o
        #     un estado interno de openpyxl.
        #   - Para evitar el crash, verificamos con "if ... is not None".
        #
        # Explicacion de NONE en Python:
        #   None es un valor especial que significa "sin valor" / "vacio".
        #   Es como un casillero sin nada adentro.
        #   Si una variable es None y tratas de hacer variable.algo,
        #     Python dice: "None no tiene ese atributo".
        #   Ejemplo:
        #     x = None
        #     x.titulo = "Hola"  ← ERROR: None no tiene atributo 'titulo'
        #   Para evitarlo, SIEMPRE verificamos con "if x is not None:".
        page_setup_pr = ws.sheet_properties.pageSetUpPr
        if page_setup_pr is not None:
            page_setup_pr.fitToPage = True

        # Escribir el titulo del reporte (fila 1, centrado).
        ws.merge_cells("A1:B1")
        celda_titulo = ws["A1"]
        celda_titulo.value = f"Reporte Diario - {reporte.fecha}"
        celda_titulo.font = Font(bold=True, size=14)
        celda_titulo.alignment = Alignment(horizontal="center")

        # Encabezados de la tabla (fila 3).
        for col, enc in enumerate(["Concepto", "Valor"], start=1):
            celda = ws.cell(row=3, column=col, value=enc)
            celda.font = _HEADER_FONT
            celda.fill = _HEADER_FILL
            celda.alignment = Alignment(horizontal="center")
            celda.border = _THIN_BORDER

        # Datos del resumen (desde fila 4).
        # Cada tupla = (concepto, valor).
        datos_reporte = [
            ("Total Ventas Bs.", f"Bs. {reporte.total_ventas_bs:,.2f}"),
            ("Total Ventas USD", f"USD {reporte.total_ventas_usd:,.2f}"),
            ("Cantidad de Ventas", str(reporte.cantidad_ventas)),
            ("Productos Vendidos", str(reporte.cantidad_productos_vendidos)),
            ("", ""),
            ("— Metodos de Pago —", ""),
            ("Efectivo Bs.", f"Bs. {reporte.efectivo_bs:,.2f}"),
            ("Efectivo USD", f"USD {reporte.efectivo_usd:,.2f}"),
            ("Tarjeta", f"Bs. {reporte.tarjeta:,.2f}"),
            ("Pago Movil", f"Bs. {reporte.pago_movil:,.2f}"),
            ("BioPago", f"Bs. {reporte.bio_pago:,.2f}"),
            ("", ""),
            ("— Alertas de Stock —", ""),
            ("Productos Stock Bajo", str(reporte.productos_stock_bajo)),
            ("Productos Sin Stock", str(reporte.productos_sin_stock)),
        ]

        for i, (concepto, valor) in enumerate(datos_reporte, start=4):
            c1 = ws.cell(row=i, column=1, value=concepto)
            c2 = ws.cell(row=i, column=2, value=valor)
            c1.border = _THIN_BORDER
            c2.border = _THIN_BORDER
            if concepto.startswith("—"):
                c1.font = Font(bold=True)
            elif concepto.startswith("Total"):
                c1.font = Font(bold=True)
                c2.font = Font(bold=True)

        # Ajustar el ancho de las columnas.
        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["B"].width = 25

    # ------------------------------------------------------------------
    # _exportar_hoja_ventas(): escribe la hoja de ventas del dia
    # ------------------------------------------------------------------
    def _exportar_hoja_ventas(self, wb: Workbook, ventas: list[Venta]) -> None:
        """Escribe la hoja 'Ventas del Dia' con el detalle de cada venta."""
        ws = wb.create_sheet("Ventas del Dia")
        ws.page_setup.orientation = "landscape"

        # Encabezados.
        enc_ventas = [
            "Factura",
            "Hora",
            "Total Bs.",
            "Total USD",
            "Efec. Bs.",
            "Efec. USD",
            "Tarjeta",
            "PagoMovil",
            "BioPago",
        ]
        for col, enc in enumerate(enc_ventas, start=1):
            celda = ws.cell(row=1, column=col, value=enc)
            celda.font = _HEADER_FONT
            celda.fill = _HEADER_FILL
            celda.alignment = Alignment(horizontal="center")
            celda.border = _THIN_BORDER

        # Escribir cada venta en una fila.
        for i, v in enumerate(ventas, start=2):
            datos = [
                v.numero_factura or "S/N",
                v.fecha_venta.strftime("%H:%M") if v.fecha_venta else "",
                float(v.total_bs),
                float(v.total_usd),
                float(v.efectivo_bs),
                float(v.efectivo_usd),
                float(v.tarjeta),
                float(v.pago_movil),
                float(v.bio_pago),
            ]
            for col, val in enumerate(datos, start=1):
                celda = ws.cell(row=i, column=col, value=val)
                celda.border = _THIN_BORDER
                if isinstance(val, float):
                    celda.number_format = "#,##0.00"

        # Ajustar ancho de columnas.
        for col, ancho in enumerate([20, 10, 12, 12, 12, 12, 12, 12, 12], start=1):
            ws.column_dimensions[chr(64 + col)].width = ancho

    # ------------------------------------------------------------------
    # _exportar_hoja_stock(): escribe la hoja de alertas de stock
    # ------------------------------------------------------------------
    def _exportar_hoja_stock(
        self,
        wb: Workbook,
        stock_bajo: list[Producto],
        sin_stock: list[Producto],
    ) -> None:
        """Escribe la hoja 'Alertas de Stock'."""
        ws = wb.create_sheet("Alertas de Stock")
        ws.page_setup.orientation = "landscape"

        # Encabezados.
        enc_stock = ["Producto", "Categoria", "Stock Actual", "Stock Minimo", "Estado"]
        for col, enc in enumerate(enc_stock, start=1):
            celda = ws.cell(row=1, column=col, value=enc)
            celda.font = _HEADER_FONT
            celda.fill = _HEADER_FILL
            celda.alignment = Alignment(horizontal="center")
            celda.border = _THIN_BORDER

        # Productos con stock bajo (stock_actual > 0 pero <= stock_minimo).
        fila = 2
        for p in stock_bajo:
            datos: list[str | int] = [
                p.nombre_producto,
                p.categoria or "",
                p.stock_actual,
                p.stock_minimo,
                "STOCK BAJO",
            ]
            for col, val in enumerate(datos, start=1):
                celda = ws.cell(row=fila, column=col, value=val)
                celda.border = _THIN_BORDER
            fila += 1

        # Productos sin stock (stock_actual == 0).
        for p in sin_stock:
            datos = [
                p.nombre_producto,
                p.categoria or "",
                p.stock_actual,
                p.stock_minimo,
                "SIN STOCK",
            ]
            for col, val in enumerate(datos, start=1):
                celda = ws.cell(row=fila, column=col, value=val)
                celda.border = _THIN_BORDER
                if col == _COL_ESTADO:
                    celda.font = Font(color="ff0000", bold=True)
            fila += 1

        # Ajustar ancho de columnas.
        for letra, ancho in [("A", 30), ("B", 20), ("C", 15), ("D", 15), ("E", 15)]:
            ws.column_dimensions[letra].width = ancho
