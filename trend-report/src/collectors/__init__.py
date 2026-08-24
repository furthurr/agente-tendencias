"""Adaptadores de fuentes públicas."""

from __future__ import annotations

from typing import Any


def source_status(
    fuente: str,
    estado: str,
    conteo: int = 0,
    detalle: str = "",
    **extra: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "fuente": fuente,
        "estado": estado,
        "conteo": conteo,
        "detalle": detalle,
    }
    result.update(extra)
    return result
