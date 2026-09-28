# texto.py: Normalizacion de texto y claves de categoria.

import unicodedata
from typing import Final

CONECTORES_ESPANOL: Final[frozenset[str]] = frozenset(
    {
        "a",
        "al",
        "ante",
        "bajo",
        "cabe",
        "con",
        "contra",
        "de",
        "del",
        "desde",
        "durante",
        "e",
        "el",
        "en",
        "entre",
        "hacia",
        "hasta",
        "la",
        "las",
        "los",
        "mediante",
        "ni",
        "o",
        "para",
        "por",
        "que",
        "segun",
        "sin",
        "so",
        "sobre",
        "tras",
        "u",
        "un",
        "una",
        "unas",
        "unos",
        "y",
        "como",
        "cuando",
        "donde",
    }
)


def normalizar_nombre_categoria(texto: str | None) -> str:
    """Devuelve el nombre de una categoría en "Titulo Español"."""
    if not texto or not texto.strip():
        return ""

    palabras = texto.split()
    resultado: list[str] = []
    for indice, palabra in enumerate(palabras):
        if indice == 0:
            resultado.append(palabra.capitalize())
        elif clave_normalizada(palabra) in CONECTORES_ESPANOL:
            resultado.append(palabra.lower())
        else:
            resultado.append(palabra.capitalize())
    return " ".join(resultado)


def clave_normalizada(texto: str | None) -> str:
    """Clave canonica para comparar/almacenar nombres sin importar
    tildes ni mayúsculas/minúsculas (compatible con SQLite UNIQUE).

    Ejemplos:
        'Limpieza'      → 'limpieza'
        'LIMPIEZA'      → 'limpieza'
        'Lácteos'       → 'lacteos'
        'Aseo Personal' → 'aseo personal'
        '' o None       → ''
    """
    if not texto or not texto.strip():
        return ""

    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.split()).lower()

