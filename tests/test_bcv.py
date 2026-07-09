"""Pruebas para services/bcv.py — conversion de moneda con tasa BCV.

Requiere mockear obtener_tasa() porque consulta el BCV en vivo."""
from decimal import Decimal

import pytest
import pytest_mock

from sistema_financiero.services.bcv import convertir_a_bs, convertir_a_usd


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
