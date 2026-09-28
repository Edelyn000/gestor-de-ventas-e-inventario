
from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, col, select

from sistema_financiero.core.tasa_cambio_service import TasaCambioService
from sistema_financiero.models.modelos import Caja, PagoVenta, Venta
from sistema_financiero.utils.constantes import MONEDA_USD
from sistema_financiero.utils.fecha import ahora
from sistema_financiero.utils.moneda import DECIMAL_CENTIMO


# Redondea a 2 decimales (mismo criterio que el POS).
def _a_centimos(valor: Decimal) -> Decimal:
    """Redondea a 2 decimales (mismo criterio que el POS)."""
    return valor.quantize(DECIMAL_CENTIMO, rounding=ROUND_HALF_UP)


# CajaService: Apertura, cierre y arqueo de la caja del turno.
class CajaService:
    """Servicio para gestionar aperturas y cierres de caja."""

    # Guarda la sesion y reutiliza el servicio de tasas (o crea uno).
    def __init__(self, db_session: Session, tasa_service: TasaCambioService | None = None) -> None:
        self.db = db_session
        self.tasa_service = tasa_service or TasaCambioService()

    # Abre una caja nueva si no hay otra abierta; rechaza si ya existe una.
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

    # Vuelto en bolivares entregado en las ventas de la caja.
    def vuelto_entregado_bs(self, caja_id: int) -> Decimal:
        """Vuelto en bolivares entregado en las ventas de la caja."""
        pagos = self.db.exec(
            select(PagoVenta)
            .join(Venta, col(PagoVenta.venta_id) == col(Venta.idventa))
            .where(col(Venta.caja_id) == caja_id, col(Venta.estado) == "COMPLETADA")
        ).all()

        total = Decimal("0.00")
        for pago in pagos:
            recibido_bs = pago.monto or Decimal("0.00")
            if pago.moneda == MONEDA_USD:
                recibido_bs = _a_centimos(recibido_bs * (pago.tasa_cambio or Decimal("0.00")))
            excedente = recibido_bs - (pago.monto_bs or Decimal("0.00"))
            if excedente > 0:
                total += excedente

        return _a_centimos(total)

    # Cierra la caja con el arqueo de billetes y calcula sobrante o faltante.
    def cerrar_caja(
        self,
        caja_id: int,
        billetes_bs: Decimal,
        billetes_usd: Decimal,
        observaciones: str | None = None,
    ) -> Caja:
        caja: Caja | None = self.db.execute(
            select(Caja).where(Caja.id == caja_id)
        ).scalar_one_or_none()
        if not caja:
            raise ValueError("No existe una caja con ese ID.")
        if caja.estado == "CERRADA":
            raise ValueError("La caja ya está cerrada.")

        tasa_actual = self.tasa_service.tasa_activa(self.db)
        tasa_venta = Decimal(str(tasa_actual.tasa_venta)) if tasa_actual else Decimal("1.00")
        total_fisico_bs = billetes_bs + (billetes_usd * tasa_venta)

        stmt = select(Venta).where(col(Venta.caja_id) == caja_id, col(Venta.estado) == "COMPLETADA")
        ventas: Sequence[Venta] = self.db.execute(stmt).scalars().all()

        total_ventas_bs = sum(
            (v.total_bs or Decimal("0") for v in ventas),
            Decimal("0"),
        )
        total_ventas_usd = sum(
            (v.total_usd or Decimal("0") for v in ventas),
            Decimal("0"),
        )
        cantidad_ventas = len(ventas) if ventas else 0
        efectivo_bs_total = sum((v.efectivo_bs or Decimal("0.00") for v in ventas), Decimal("0.00"))
        efectivo_usd_total = sum(
            (v.efectivo_usd or Decimal("0.00") for v in ventas), Decimal("0.00")
        )
        tarjeta_total = sum((v.tarjeta or Decimal("0.00") for v in ventas), Decimal("0.00"))
        pago_movil_total = sum((v.pago_movil or Decimal("0.00") for v in ventas), Decimal("0.00"))
        bio_pago_total = sum((v.bio_pago or Decimal("0.00") for v in ventas), Decimal("0.00"))
        transferencia_total = sum(
            (v.transferencia or Decimal("0.00") for v in ventas), Decimal("0.00")
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
        caja.transferencia = transferencia_total
        vuelto_bs_total = self.vuelto_entregado_bs(caja_id)
        esperado_efectivo_bs = (
            (caja.monto_apertura_bs or Decimal("0.00"))
            + efectivo_bs_total
            + (efectivo_usd_total * tasa_venta)
            - vuelto_bs_total
        )
        caja.sobrante_faltante_bs = total_fisico_bs - esperado_efectivo_bs
        if observaciones:
            caja.observaciones = observaciones

        self.db.commit()
        self.db.refresh(caja)

        return caja

    # Devuelve la caja en estado ABIERTA o None.
    def obtener_caja_abierta(self) -> Caja | None:
        return self.db.execute(select(Caja).where(Caja.estado == "ABIERTA")).scalar_one_or_none()

    # Devuelve la caja abierta o lanza ValueError si no hay.
    def validar_caja_abierta(self) -> Caja:
        caja = self.obtener_caja_abierta()
        if not caja:
            raise ValueError("No hay caja abierta. Abra la caja antes de registrar ventas.")
        return caja

    # Lista las cajas cerradas, opcionalmente filtradas por rango de fechas.
    def historial(
        self, fecha_desde: datetime | None = None, fecha_hasta: datetime | None = None
    ) -> list[Caja]:
        consulta = select(Caja).where(col(Caja.estado) == "CERRADA")

        if fecha_desde:
            consulta = consulta.where(col(Caja.fecha_apertura) >= fecha_desde)

        if fecha_hasta:
            consulta = consulta.where(col(Caja.fecha_apertura) <= fecha_hasta + timedelta(days=1))

        return list(self.db.exec(consulta.order_by(col(Caja.fecha_apertura).desc())).all())

