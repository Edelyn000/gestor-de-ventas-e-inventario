# ============================================================
# SERVICIO: Caja
# Lógica de negocio para apertura y cierre de caja registradora.
# Controla el flujo: abrir -> vender -> cerrar -> reporte Z.
# Una sola caja debe estar abierta por momento de trabajo.
# ============================================================

from datetime import datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, col, select

from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.models.modelos import Caja, ReporteDiario, Venta
from sistema_financiero.utils.fecha import ahora, hoy


class CajaService:
    """Servicio para gestionar aperturas y cierres de caja."""

    def __init__(self, db_session: Session, tasa_service: TasaCambioService | None = None) -> None:
        self.db = db_session
        self.tasa_service = tasa_service or TasaCambioService()

    def abrir_caja(self, monto_apertura_bs: Decimal, usuario_id: int) -> Caja:
        caja_actual = self.db.execute(
            select(Caja).where(Caja.estado == "ABIERTA")
        ).scalar_one_or_none()
        if caja_actual:
            raise ValueError(
                "Ya existe una caja abierta. Cierre la actual antes de abrir una nueva."
            )

        caja = Caja(
            monto_apertura_bs=monto_apertura_bs,
            usuario_id=usuario_id,
            estado="ABIERTA",
            fecha_apertura=ahora(),
        )

        self.db.add(caja)
        self.db.commit()
        self.db.refresh(caja)

        return caja

    def cerrar_caja(
        self,
        caja_id: int,
        billetes_bs: Decimal,
        billetes_usd: Decimal,
        observaciones: str | None = None,
    ) -> Caja:
        caja = self.db.execute(select(Caja).where(Caja.id == caja_id)).scalar_one_or_none()
        if not caja:
            raise ValueError("No existe una caja con ese ID.")
        if caja.estado == "CERRADA":
            raise ValueError("La caja ya está cerrada.")

        tasa_actual = self.tasa_service.tasa_activa(self.db)
        tasa_venta = Decimal(str(tasa_actual.tasa_venta)) if tasa_actual else Decimal("1.00")
        total_fisico_bs = billetes_bs + (billetes_usd * tasa_venta)

        stmt = select(Venta).where(col(Venta.caja_id) == caja_id, col(Venta.estado) == "COMPLETADA")
        ventas = self.db.execute(stmt).scalars().all()

        total_ventas_bs = sum(
            (v.total_bs or Decimal("0") for v in ventas),
            Decimal("0"),
        )
        total_ventas_usd = sum(
            (v.total_usd or Decimal("0") for v in ventas),
            Decimal("0"),
        )
        cantidad_ventas = len(ventas) if ventas else 0

        efectivo_bs_total = (
            sum((v.efectivo_bs or Decimal("0")) for v in ventas) if ventas else Decimal("0.00")
        )
        efectivo_usd_total = (
            sum((v.efectivo_usd or Decimal("0")) for v in ventas) if ventas else Decimal("0.00")
        )
        tarjeta_total = (
            sum((v.tarjeta or Decimal("0")) for v in ventas) if ventas else Decimal("0.00")
        )
        pago_movil_total = (
            sum((v.pago_movil or Decimal("0")) for v in ventas) if ventas else Decimal("0.00")
        )
        bio_pago_total = (
            sum((v.bio_pago or Decimal("0")) for v in ventas) if ventas else Decimal("0.00")
        )

        caja.fecha_cierre = ahora()
        caja.monto_cierre_bs = total_fisico_bs
        caja.estado = "CERRADA"
        caja.total_ventas_bs = total_ventas_bs
        caja.total_ventas_usd = total_ventas_usd
        caja.cantidad_ventas = cantidad_ventas
        caja.efectivo_bs = efectivo_bs_total
        caja.efectivo_usd = efectivo_usd_total
        caja.tarjeta = tarjeta_total
        caja.pago_movil = pago_movil_total
        caja.bio_pago = bio_pago_total
        caja.sobrante_faltante_bs = total_fisico_bs - total_ventas_bs
        if observaciones:
            caja.observaciones = observaciones

        self.db.commit()
        self.db.refresh(caja)

        self._generar_reporte_z(caja)

        return caja

    def obtener_caja_abierta(self) -> Caja | None:
        return self.db.execute(select(Caja).where(Caja.estado == "ABIERTA")).scalar_one_or_none()

    def validar_caja_abierta(self) -> Caja:
        caja = self.obtener_caja_abierta()
        if not caja:
            raise ValueError("No hay caja abierta. Abra la caja antes de registrar ventas.")
        return caja

    def historial(
        self, fecha_desde: datetime | None = None, fecha_hasta: datetime | None = None
    ) -> list[Caja]:
        consulta = select(Caja).where(col(Caja.estado) == "CERRADA")

        if fecha_desde:
            consulta = consulta.where(col(Caja.fecha_apertura) >= fecha_desde)

        if fecha_hasta:
            consulta = consulta.where(col(Caja.fecha_apertura) <= fecha_hasta + timedelta(days=1))

        return list(self.db.exec(consulta.order_by(col(Caja.fecha_apertura).desc())).all())

    def _generar_reporte_z(self, caja: Caja) -> None:
        stmt = select(Venta).where(col(Venta.caja_id) == caja.id, col(Venta.estado) == "COMPLETADA")
        ventas = self.db.execute(stmt).scalars().all()

        total_ventas_bs = sum(
            (v.total_bs or Decimal("0") for v in ventas),
            Decimal("0"),
        )
        total_ventas_usd = sum(
            (v.total_usd or Decimal("0") for v in ventas),
            Decimal("0"),
        )
        cantidad_ventas = len(ventas) if ventas else 0
        productos_stock_bajo = 0
        productos_sin_stock = 0

        efectivo_bs = caja.efectivo_bs or Decimal("0.00")
        efectivo_usd = caja.efectivo_usd or Decimal("0.00")
        tarjeta = caja.tarjeta or Decimal("0.00")
        pago_movil = caja.pago_movil or Decimal("0.00")
        bio_pago = caja.bio_pago or Decimal("0.00")

        fecha_reporte = caja.fecha_cierre.date() if caja.fecha_cierre else hoy()
        reporte_existente = self.db.execute(
            select(ReporteDiario).where(ReporteDiario.fecha == fecha_reporte)
        ).scalar_one_or_none()

        if reporte_existente:
            reporte = reporte_existente
            reporte.total_ventas_bs = total_ventas_bs
            reporte.total_ventas_usd = total_ventas_usd
            reporte.cantidad_ventas = cantidad_ventas
            reporte.productos_stock_bajo = productos_stock_bajo
            reporte.productos_sin_stock = productos_sin_stock
            reporte.efectivo_bs = efectivo_bs
            reporte.efectivo_usd = efectivo_usd
            reporte.tarjeta = tarjeta
            reporte.pago_movil = pago_movil
            reporte.bio_pago = bio_pago
        else:
            reporte = ReporteDiario(
                fecha=fecha_reporte,
                total_ventas_bs=total_ventas_bs,
                total_ventas_usd=total_ventas_usd,
                cantidad_ventas=cantidad_ventas,
                productos_stock_bajo=productos_stock_bajo,
                productos_sin_stock=productos_sin_stock,
                efectivo_bs=efectivo_bs,
                efectivo_usd=efectivo_usd,
                tarjeta=tarjeta,
                pago_movil=pago_movil,
                bio_pago=bio_pago,
                fecha_generacion=ahora(),
            )
            self.db.add(reporte)

        self.db.commit()

    def obtener_datos_reporte_z(self, caja_id: int) -> dict[str, object]:
        caja = self.db.execute(select(Caja).where(Caja.id == caja_id)).scalar_one_or_none()
        if not caja or caja.estado != "CERRADA":
            raise ValueError("Caja no encontrada o no cerrada.")

        stmt = select(Venta).where(col(Venta.caja_id) == caja_id, col(Venta.estado) == "COMPLETADA")
        ventas = self.db.execute(stmt).scalars().all()

        total_ventas_bs = sum(
            (v.total_bs or Decimal("0") for v in ventas),
            Decimal("0"),
        )
        total_ventas_usd = sum(
            (v.total_usd or Decimal("0") for v in ventas),
            Decimal("0"),
        )
        cantidad_ventas = len(ventas) if ventas else 0

        return {
            "id_caja": caja.id,
            "fecha_apertura": caja.fecha_apertura,
            "fecha_cierre": caja.fecha_cierre,
            "monto_apertura_bs": caja.monto_apertura_bs,
            "monto_cierre_bs": caja.monto_cierre_bs,
            "estado": caja.estado,
            "usuario_id": caja.usuario_id,
            "total_ventas_bs": total_ventas_bs,
            "total_ventas_usd": total_ventas_usd,
            "cantidad_ventas": cantidad_ventas,
            "efectivo_bs": caja.efectivo_bs or Decimal("0.00"),
            "efectivo_usd": caja.efectivo_usd or Decimal("0.00"),
            "tarjeta": caja.tarjeta or Decimal("0.00"),
            "pago_movil": caja.pago_movil or Decimal("0.00"),
            "bio_pago": caja.bio_pago or Decimal("0.00"),
            "sobrante_faltante_bs": caja.sobrante_faltante_bs,
            "observaciones": caja.observaciones or "",
        }
