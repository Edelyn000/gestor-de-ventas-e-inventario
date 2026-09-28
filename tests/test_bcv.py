"""Pruebas para services/bcv.py — conversion de moneda con tasa BCV."""

from decimal import Decimal

import pytest
import pytest_mock

from sistema_financiero.services.bcv import (
    convertir_a_bs,
    convertir_a_usd,
    obtener_tasa,
)

pytestmark = pytest.mark.unitarias


class TestConversion:
    @pytest.fixture(autouse=True)
    def _mock_tasa(self, mocker: pytest_mock.MockerFixture) -> None:
        """Fija la tasa BCV en 50 Bs/USD para todos los tests de esta clase."""
        mocker.patch(
            "sistema_financiero.services.bcv.obtener_tasa",
            return_value=Decimal("50.00"),
        )

    def test_convertir_a_usd_decimal(self) -> None:
        resultado = convertir_a_usd(Decimal("100.00"))
        assert resultado == Decimal("2.00")

    def test_convertir_a_usd_int(self) -> None:
        resultado = convertir_a_usd(100)
        assert resultado == Decimal("2.00")

    def test_convertir_a_usd_float(self) -> None:
        resultado = convertir_a_usd(50.0)
        assert resultado == Decimal("1.00")

    def test_convertir_a_usd_cero(self) -> None:
        resultado = convertir_a_usd(Decimal("0.00"))
        assert resultado == Decimal("0.00")

    def test_convertir_a_usd_redondeo(self) -> None:
        resultado = convertir_a_usd(Decimal("33.33"))
        assert resultado == Decimal("0.6666")

    def test_convertir_a_bs_decimal(self) -> None:
        resultado = convertir_a_bs(Decimal("2.00"))
        assert resultado == Decimal("100.00")

    def test_convertir_a_bs_int(self) -> None:
        resultado = convertir_a_bs(1)
        assert resultado == Decimal("50.00")

    def test_convertir_a_bs_float(self) -> None:
        resultado = convertir_a_bs(1.5)
        assert resultado == Decimal("75.00")

    def test_convertir_a_bs_cero(self) -> None:
        resultado = convertir_a_bs(Decimal("0.00"))
        assert resultado == Decimal("0.00")


class TestObtenerTasaFallos:
    """obtener_tasa() eleva a ConnectionError los fallos que el scraper
    traga en silencio (devuelve {} sin internet o con el BCV caido)."""

    @staticmethod
    def _cliente_con(mocker: pytest_mock.MockerFixture, respuesta: object) -> None:
        cliente = mocker.Mock()
        cliente.get_tasas.return_value = respuesta
        mocker.patch("sistema_financiero.services.bcv._get_client", return_value=cliente)

    def test_respuesta_vacia_lanza_connection_error(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """get_tasas() devuelve {} (fallo real de red/BCV tragado por el
        scraper) → ConnectionError, no KeyError."""
        self._cliente_con(mocker, respuesta={})
        with pytest.raises(ConnectionError):
            obtener_tasa()

    def test_respuesta_sin_usd_lanza_connection_error(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """get_tasas() devuelve otra moneda pero no USD → ConnectionError."""
        self._cliente_con(mocker, respuesta={"EUR": {"valor": "1.0"}})
        with pytest.raises(ConnectionError):
            obtener_tasa()

    def test_respuesta_valida_devuelve_decimal(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Con respuesta valida, obtener_tasa() devuelve el Decimal."""
        self._cliente_con(mocker, respuesta={"USD": {"valor": 857.01}})
        assert obtener_tasa() == Decimal("857.01")

