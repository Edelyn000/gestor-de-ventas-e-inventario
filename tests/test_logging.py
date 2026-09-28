import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sistema_financiero.utils import logging_setup

pytestmark = pytest.mark.unitarias


# Redirige el log a un archivo temporal y resetea el logger.
@pytest.fixture(autouse=True)
def _log_en_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirige el log a un archivo temporal y resetea el logger."""
    directorio = tmp_path / "logs"
    archivo = directorio / "errores.log"
    monkeypatch.setattr(logging_setup, "LOG_DIR", directorio)
    monkeypatch.setattr(logging_setup, "LOG_FILE", archivo)
    monkeypatch.setattr(logging_setup, "_estado", {})
    logging.getLogger(logging_setup.NOMBRE_LOGGER).handlers.clear()

    monkeypatch.setattr(logging_setup.QMessageBox, "critical", MagicMock())


class TestConfigurarLogging:
    # configurar_logging() crea logs/errores.
    def test_crea_archivo_y_directorio(self, tmp_path: Path) -> None:
        """configurar_logging() crea logs/errores.log."""
        logger = logging_setup.configurar_logging()

        assert logger is not None
        assert (tmp_path / "logs" / "errores.log").exists()

    # Llamar dos veces no duplica handlers ni recrea el logger.
    def test_reutiliza_el_mismo_logger(self) -> None:
        """Llamar dos veces no duplica handlers ni recrea el logger."""
        primero = logging_setup.configurar_logging()
        segundo = logging_setup.configurar_logging()

        assert primero is segundo
        assert len(primero.handlers) == 1


class TestRegistrarExcepcion:
    # El archivo del log contiene contexto, mensaje y traceback.
    def test_escribe_error_con_traceback(self, tmp_path: Path) -> None:
        """El archivo del log contiene contexto, mensaje y traceback."""
        try:
            raise ValueError("monto invalido")
        except ValueError as exc:
            error = exc

        logging_setup.registrar_excepcion(error, "test_ctx")

        contenido = (tmp_path / "logs" / "errores.log").read_text(encoding="utf-8")
        assert "test_ctx" in contenido
        assert "monto invalido" in contenido
        assert "Traceback" in contenido


class TestManejarExcepcionNoManejada:
    # Una excepcion que escapa de un slot queda en el log.
    def test_registra_error_no_manejado(self, tmp_path: Path) -> None:
        """Una excepcion que escapa de un slot queda en el log."""
        try:
            raise RuntimeError("fallo en boton")
        except RuntimeError as exc:
            error = exc

        logging_setup.manejar_excepcion_no_manejada(type(error), error, error.__traceback__)

        contenido = (tmp_path / "logs" / "errores.log").read_text(encoding="utf-8")
        assert "fallo en boton" in contenido
        assert "manejador global" in contenido

    # KeyboardInterrupt se deja pasar al excepthook original.
    def test_keyboard_interrupt_no_se_registra(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """KeyboardInterrupt se deja pasar al excepthook original."""
        mock_registrar = MagicMock()
        monkeypatch.setattr(logging_setup, "registrar_excepcion", mock_registrar)

        try:
            raise KeyboardInterrupt()
        except KeyboardInterrupt as exc:
            error = exc

        logging_setup.manejar_excepcion_no_manejada(type(error), error, error.__traceback__)

        mock_registrar.assert_not_called()

