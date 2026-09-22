# ============================================================
# ARCHIVO: utils/logging_setup.py
# Configuracion de logging y manejo global de excepciones.
#
# PROPOSITO:
#   - registrar_excepcion(): guarda CUALQUIER error con su
#     traceback completo en logs/errores.log.
#   - registrar_evento(): guarda eventos de la aplicacion
#     (auditoria: logins exitosos/fallidos, etc.) en
#     logs/eventos.log. Jamas registrar contrasenas.
#   - manejar_excepcion_no_manejada(): sys.excepthook de la app.
#     Si un boton u operacion falla con una excepcion que no se
#     capturo en la UI, aqui se registra en el log y se muestra
#     un dialogo con el error. Asi NINGUN fallo queda invisible.
#
# QUE NO SE DEBE TOCAR:
#   - Nombres publicos (configurar_logging, registrar_excepcion,
#     registrar_evento, manejar_excepcion_no_manejada).
#   - Las rutas logs/errores.log y logs/eventos.log.
# ============================================================
import logging
import sys
from pathlib import Path
from types import TracebackType

from PyQt6.QtWidgets import QApplication, QMessageBox

# Ruta del log: <raiz-del-proyecto>/logs
LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "errores.log"
LOG_FILE_EVENTOS = LOG_DIR / "eventos.log"

NOMBRE_LOGGER = "sistema_financiero"
NOMBRE_LOGGER_EVENTOS = "sistema_financiero.eventos"

_estado: dict[str, logging.Logger] = {}


def configurar_logging() -> logging.Logger:
    """Prepara el logger del sistema: escribe en logs/errores.log."""
    logger = _estado.get("logger")
    if logger is None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(NOMBRE_LOGGER)
        logger.setLevel(logging.ERROR)
        if not logger.handlers:
            manejador = logging.FileHandler(LOG_FILE, encoding="utf-8")
            manejador.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            logger.addHandler(manejador)
        _estado["logger"] = logger
    return logger


def configurar_logging_eventos() -> logging.Logger:
    """Prepara el logger de eventos: escribe en logs/eventos.log (nivel INFO)."""
    logger = _estado.get("logger_eventos")
    if logger is None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(NOMBRE_LOGGER_EVENTOS)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            manejador = logging.FileHandler(LOG_FILE_EVENTOS, encoding="utf-8")
            manejador.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            logger.addHandler(manejador)
        _estado["logger_eventos"] = logger
    return logger


def registrar_evento(nivel: int, mensaje: str) -> None:
    """Registra un evento de la aplicacion (auditoria) en logs/eventos.log.

    nivel: logging.INFO / logging.WARNING / etc.
    mensaje: texto descriptivo. NUNCA incluir contrasenas.
    """
    logger = configurar_logging_eventos()
    logger.log(nivel, mensaje)


def registrar_excepcion(exc: BaseException, contexto: str) -> None:
    """Registra una excepcion (con traceback completo) en logs/errores.log.

    contexto: nombre del metodo/operacion donde ocurrio (ej. '_anular_venta').
    """
    logger = configurar_logging()
    logger.error(
        "Excepcion en %s: %s",
        contexto,
        exc,
        exc_info=(type(exc), exc, exc.__traceback__),
    )


def manejar_excepcion_no_manejada(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: TracebackType | None,
) -> None:
    """sys.excepthook: registra y muestra cualquier error no controlado.

    Se instala en __main__.py: si una excepcion escapa de un slot de
    PyQt6 (boton, timer, etc.), aqui queda registrada en el log y se
    muestra un dialogo, en lugar de desaparecer en silencio.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    registrar_excepcion(exc_value, "manejador global de excepciones")

    try:
        if QApplication.instance() is not None:
            QMessageBox.critical(
                None,
                "Error inesperado",
                f"Ocurrio un error en la aplicacion:\n{exc_value}",
            )
    except Exception:
        # El manejador de errores nunca debe fallar.
        pass
