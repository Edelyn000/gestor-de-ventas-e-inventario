from datetime import date, datetime
from decimal import Decimal

from sqlmodel import select

from ..models import TasaCambio, get_session
from ..services.bcv import obtener_tasa as bcv_obtener_tasa


# ============================================================
# SERVICIO: TasaCambioService
# Gestion de tasas de cambio VES/USD.
# Permite registrar, consultar y activar/desactivar tasas.
# Tambien puede obtener la tasa desde el BCV via bcv.py.
#
# Metodos:
#   registrar()            → Crea una nueva tasa para una fecha
#   tasa_activa()          → Devuelve la tasa activa mas reciente
#   obtener_por_fecha()    → Busca tasa de una fecha especifica
#   historial()            → Todas las tasas ordenadas
#   desactivar_tasa()      → Marca una tasa como inactiva
#   obtener_desde_bcv()    → Obtiene la tasa actual del BCV
# ============================================================
class TasaCambioService:
    def registrar(
        self,
        fecha: date,
        tasa_venta: Decimal,
        tasa_compra: Decimal,
        activa: bool = True,
    ) -> TasaCambio:
        """Registra una nueva tasa de cambio para una fecha especifica.
        Si ya existe una tasa para esa fecha, lanza error."""
        if tasa_venta <= 0 or tasa_compra <= 0:
            raise ValueError("Las tasas deben ser mayores a cero.")

        # Verificar si ya existe una tasa para esta fecha.
        with get_session() as session:
            existente = session.exec(select(TasaCambio).where(TasaCambio.fecha == fecha)).first()
            if existente:
                raise ValueError(f"Ya existe una tasa registrada para la fecha {fecha}.")

            tasa = TasaCambio(
                fecha=fecha,
                tasa_venta=tasa_venta,
                tasa_compra=tasa_compra,
                activa=activa,
                fecha_registro=datetime.now(),
            )
            session.add(tasa)
            session.commit()
            session.refresh(tasa)

        return tasa

    def tasa_activa(self) -> TasaCambio | None:
        """Devuelve la tasa de cambio activa mas reciente.
        Si hay varias activas, retorna la de fecha mas reciente."""
        with get_session() as session:
            stmt = (
                select(TasaCambio)
                .where(TasaCambio.activa == True)  # noqa: E712
                .order_by(TasaCambio.fecha.desc())  # type: ignore[attr-defined]
            )
            return session.exec(stmt).first()

    def obtener_por_fecha(self, fecha: date) -> TasaCambio | None:
        """Busca la tasa registrada para una fecha especifica."""
        with get_session() as session:
            return session.exec(select(TasaCambio).where(TasaCambio.fecha == fecha)).first()

    def historial(self) -> list[TasaCambio]:
        """Devuelve todas las tasas registradas, de la mas reciente a la mas antigua."""
        with get_session() as session:
            stmt = select(TasaCambio).order_by(TasaCambio.fecha.desc())  # type: ignore[attr-defined]
            return list(session.exec(stmt).all())

    def desactivar_tasa(self, tasa_id: int) -> bool:
        """Marca una tasa como inactiva. Retorna False si no existe."""
        with get_session() as session:
            tasa = session.get(TasaCambio, tasa_id)
            if not tasa:
                return False
            tasa.activa = False
            session.add(tasa)
            session.commit()
        return True

    def obtener_desde_bcv(self) -> TasaCambio | None:
        """Obtiene la tasa actual desde el BCV via servicios/bcv.py
        y la registra en la BD. Retorna None si no se pudo obtener."""
        try:
            tasa_actual = bcv_obtener_tasa()
            hoy = date.today()
            tasa_redondeada = tasa_actual.quantize(Decimal("0.01"))
            return self.registrar(
                fecha=hoy, tasa_venta=tasa_redondeada, tasa_compra=tasa_redondeada
            )
        except ImportError, ValueError, ConnectionError:
            return None
