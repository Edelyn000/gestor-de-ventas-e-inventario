from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from sistema_financiero.utils import (
    ORIGEN_TASA_BCV,
    ORIGEN_TASA_MANUAL,
    ahora,
    hoy,
)

from ..models import TasaCambio, obtener_sesion
from ..services.bcv import obtener_tasa as bcv_obtener_tasa
from ..utils.logging_setup import registrar_excepcion


# TasaCambioService: Tasas de cambio BCV, manuales e historial.
class TasaCambioService:
    # Registra una nueva tasa de cambio para una fecha especifica.
    def registrar(
        self,
        fecha: date,
        tasa_venta: Decimal,
        tasa_compra: Decimal,
        activa: bool = True,
        db_session: Session | None = None,
        origen: str = ORIGEN_TASA_BCV,
        registrado_por: str | None = None,
    ) -> TasaCambio:
        """Registra una nueva tasa de cambio para una fecha especifica."""
        if tasa_venta <= 0 or tasa_compra <= 0:
            msg = "Las tasas deben ser mayores a cero."
            raise ValueError(msg)

        with obtener_sesion(db_session) as session:
            existente = session.exec(
                select(TasaCambio).where(
                    TasaCambio.fecha == fecha,
                    TasaCambio.origen == origen,
                )
            ).first()
            if existente:
                msg = f"Ya existe una tasa {origen} registrada para la fecha {fecha}."
                raise ValueError(msg)

            tasa = TasaCambio(
                fecha=fecha,
                origen=origen,
                registrado_por=registrado_por,
                tasa_venta=tasa_venta,
                tasa_compra=tasa_compra,
                activa=activa,
                fecha_registro=ahora(),
            )
            session.add(tasa)
            session.commit()
            session.refresh(tasa)

        return tasa

    # Devuelve la tasa BCV activa mas reciente.
    def tasa_activa(
        self,
        db_session: Session | None = None,
    ) -> TasaCambio | None:
        """Devuelve la tasa BCV activa mas reciente."""
        with obtener_sesion(db_session) as session:
            stmt = (
                select(TasaCambio)
                .where(
                    TasaCambio.activa == True,  # noqa: E712
                    TasaCambio.origen == ORIGEN_TASA_BCV,
                )
                .order_by(TasaCambio.fecha.desc())  # type: ignore[attr-defined]
            )
            return session.exec(stmt).first()

    # Busca la tasa BCV registrada para una fecha especifica.
    def obtener_por_fecha(
        self,
        fecha: date,
        db_session: Session | None = None,
    ) -> TasaCambio | None:
        """Busca la tasa BCV registrada para una fecha especifica."""
        with obtener_sesion(db_session) as session:
            return session.exec(
                select(TasaCambio).where(
                    TasaCambio.fecha == fecha,
                    TasaCambio.origen == ORIGEN_TASA_BCV,
                )
            ).first()

    # Devuelve todas las tasas registradas, de la mas reciente a la mas antigua.
    def historial(
        self,
        db_session: Session | None = None,
    ) -> list[TasaCambio]:
        """Devuelve todas las tasas registradas, de la mas reciente a la mas antigua."""
        with obtener_sesion(db_session) as session:
            stmt = select(TasaCambio).order_by(TasaCambio.fecha.desc())  # type: ignore[attr-defined]
            return list(session.exec(stmt).all())

    # Marca una tasa como inactiva.
    def desactivar_tasa(
        self,
        tasa_id: int,
        db_session: Session | None = None,
    ) -> bool:
        """Marca una tasa como inactiva. Retorna False si no existe."""
        with obtener_sesion(db_session) as session:
            tasa = session.get(TasaCambio, tasa_id)
            if not tasa:
                return False
            tasa.activa = False
            session.add(tasa)
            session.commit()
        return True

    # Obtiene la tasa actual desde el BCV via servicios/bcv.
    def obtener_desde_bcv(self) -> TasaCambio | None:
        """Obtiene la tasa actual desde el BCV via servicios/bcv.py
        y la registra/actualiza en la BD. Retorna None si no se pudo obtener.
        Actualiza SOLO la fila BCV (nunca pisa una tasa MANUAL del dia)."""
        try:
            tasa_actual = bcv_obtener_tasa()
            hoy_dt = hoy()
            tasa_redondeada = tasa_actual.quantize(Decimal("0.01"))

            with obtener_sesion() as session:
                existente = session.exec(
                    select(TasaCambio).where(
                        TasaCambio.fecha == hoy_dt,
                        TasaCambio.origen == ORIGEN_TASA_BCV,
                    )
                ).first()

                if existente:
                    existente.tasa_venta = tasa_redondeada
                    existente.tasa_compra = tasa_redondeada
                    existente.activa = True
                    existente.fecha_registro = ahora()
                    session.add(existente)
                    session.commit()
                    session.refresh(existente)
                    return existente
                else:
                    return self.registrar(
                        fecha=hoy_dt,
                        tasa_venta=tasa_redondeada,
                        tasa_compra=tasa_redondeada,
                        origen=ORIGEN_TASA_BCV,
                    )
        except (
            ImportError,
            ValueError,
            ConnectionError,
            KeyError,
            TimeoutError,
        ) as e:
            registrar_excepcion(e, "TasaCambioService.obtener_desde_bcv")
            return None

    # Registra (o actualiza si ya existe HOY) la tasa MANUAL del POS.
    def registrar_tasa_manual(
        self,
        tasa_venta: Decimal,
        registrado_por: str | None = None,
        db_session: Session | None = None,
    ) -> TasaCambio:
        """Registra (o actualiza si ya existe HOY) la tasa MANUAL del POS."""
        if tasa_venta <= 0:
            msg = "La tasa debe ser mayor a cero."
            raise ValueError(msg)

        with obtener_sesion(db_session) as session:
            existente = session.exec(
                select(TasaCambio).where(
                    TasaCambio.fecha == hoy(),
                    TasaCambio.origen == ORIGEN_TASA_MANUAL,
                )
            ).first()

            if existente:
                existente.tasa_venta = tasa_venta
                existente.tasa_compra = tasa_venta
                existente.activa = True
                existente.registrado_por = registrado_por
                existente.fecha_registro = ahora()
                session.add(existente)
                session.commit()
                session.refresh(existente)
                return existente

            tasa = TasaCambio(
                fecha=hoy(),
                origen=ORIGEN_TASA_MANUAL,
                registrado_por=registrado_por,
                tasa_venta=tasa_venta,
                tasa_compra=tasa_venta,
                activa=True,
                fecha_registro=ahora(),
            )
            session.add(tasa)
            session.commit()
            session.refresh(tasa)

        return tasa

    # Apaga la tasa MANUAL de hoy (activa=False).
    def desactivar_tasa_manual(
        self,
        db_session: Session | None = None,
    ) -> bool:
        """Apaga la tasa MANUAL de hoy (activa=False)."""
        with obtener_sesion(db_session) as session:
            existente = session.exec(
                select(TasaCambio).where(
                    TasaCambio.fecha == hoy(),
                    TasaCambio.origen == ORIGEN_TASA_MANUAL,
                )
            ).first()
            if not existente:
                return False
            existente.activa = False
            session.add(existente)
            session.commit()
        return True

