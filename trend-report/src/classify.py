"""Normalización y clasificación determinista de temas."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable


_PUNCTUATION = str.maketrans(
    {
        char: " "
        for char in "-_/\\|,.:;!?¿¡()[]{}\"'`´~*+#&@$%^=<>"
        + "\u2013\u2014\u2018\u2019\u201c\u201d"
    }
)

STOP_PREFIXES = (
    "especial:",
    "wikipedia:",
    "ayuda:",
    "categoría:",
    "categoria:",
    "portal:",
    "plantilla:",
    "archivo:",
    "módulo:",
    "modulo:",
    "discusión:",
    "discusion:",
    "usuario:",
    "mediawiki:",
    "anexo:",
)

STOP_EXACTOS = {
    "portada",
    "main page",
    "méxico",
    "mexico",
    "españa",
    "espana",
    "argentina",
    "colombia",
    "chile",
    "perú",
    "peru",
    "brasil",
    "venezuela",
    "ecuador",
    "bolivia",
    "uruguay",
    "paraguay",
    "costa rica",
    "panamá",
    "panama",
    "guatemala",
    "honduras",
    "nicaragua",
    "el salvador",
    "ciudad de méxico",
    "ciudad de mexico",
    "madrid",
    "barcelona",
    "buenos aires",
    "lima",
    "bogotá",
    "bogota",
    "santiago de chile",
}


def normalizar(texto: str | None) -> str:
    """Normaliza títulos y claves de forma idéntica."""

    value = str(texto or "").lower().strip().translate(_PUNCTUATION)
    value = unicodedata.normalize("NFD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.split())


def patron_palabra_completa(clave: str) -> re.Pattern[str]:
    clave_norm = normalizar(clave)
    return re.compile(rf"(?<![a-z0-9]){re.escape(clave_norm)}(?![a-z0-9])")


def coincide_keyword(texto: str, clave: str) -> bool:
    """Match seguro: evita el bug `terremoto` → `moto`."""

    texto_norm = normalizar(texto)
    clave_norm = normalizar(clave)
    if not texto_norm or not clave_norm:
        return False
    return patron_palabra_completa(clave_norm).search(f" {texto_norm} ") is not None


def es_tema_excluido(titulo: str) -> bool:
    raw = (titulo or "").strip().lower()
    norm = normalizar(titulo)
    return (
        len(norm) < 4
        or any(raw.startswith(prefix) for prefix in STOP_PREFIXES)
        or norm in {normalizar(item) for item in STOP_EXACTOS}
    )


def clasificar_por_titulo(titulo: str, nichos: Iterable[dict[str, Any]]) -> str | None:
    """Devuelve el primer nicho con match; el orden de config es significativo."""

    for nicho in nichos:
        if any(coincide_keyword(titulo, clave) for clave in nicho.get("claves", [])):
            return str(nicho["nombre"])
    return None


def clasificar_con_descripcion(
    titulo: str,
    description: str,
    extract: str,
    nichos: Iterable[dict[str, Any]],
) -> str | None:
    texto = f"{titulo} {description} {extract[:400]}"
    # En el fallback, un extracto biográfico puede mencionar de pasada un
    # videojuego, un club o una marca. Elegir el primer match global hacía que
    # una sola palabra incidental ganara a varias señales de profesión. El
    # título ya se intentó antes; aquí comparamos evidencia por nicho y usamos
    # el orden de configuración solo como desempate estable.
    candidates: list[tuple[int, int, int, int, str]] = []
    for index, nicho in enumerate(nichos):
        matches = [
            normalizar(clave)
            for clave in nicho.get("claves", [])
            if coincide_keyword(texto, str(clave))
        ]
        if matches:
            candidates.append(
                (
                    len(matches),
                    sum(len(match) for match in matches),
                    max(len(match) for match in matches),
                    -index,
                    str(nicho["nombre"]),
                )
            )
    if not candidates:
        return None
    return max(candidates)[-1]


def cargar_cache(path: str | Path) -> dict[str, str | None]:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def invalidar_nones(cache: dict[str, str | None]) -> int:
    """Purgar resultados fallidos para reintentar con la taxonomía actual."""

    keys = [key for key, value in cache.items() if value is None]
    for key in keys:
        del cache[key]
    return len(keys)


def guardar_cache(path: str | Path, cache: dict[str, str | None]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def clasificar_temas(
    temas: list[dict[str, Any]],
    nichos: list[dict[str, Any]],
    cache: dict[str, str | None],
    summary_loader: Callable[[str], dict[str, str]] | None = None,
    max_lookup: int = 800,
) -> dict[str, int]:
    """Clasifica por título y usa resúmenes Wiki solo para los casos fuertes."""

    lookups = 0
    cache_hits = 0
    fallback_matches = 0
    for tema in sorted(temas, key=lambda item: item.get("vistas_periodo", 0), reverse=True):
        titulo = str(tema.get("titulo", ""))
        cached = cache.get(titulo, "__missing__")
        if cached != "__missing__" and cached is not None:
            tema["nicho"] = cached
            cache_hits += 1
            continue

        nicho = clasificar_por_titulo(titulo, nichos)
        if nicho:
            tema["nicho"] = nicho
            cache[titulo] = nicho
            continue

        should_lookup = (
            summary_loader is not None
            and lookups < max_lookup
            and tema.get("vistas_periodo", 0) >= 300
            and not tema.get("es_historia_hn", False)
        )
        if should_lookup:
            lookups += 1
            try:
                summary = summary_loader(titulo)
                nicho = clasificar_con_descripcion(
                    titulo,
                    summary.get("description", ""),
                    summary.get("extract", ""),
                    nichos,
                )
            except Exception:
                # El colector registra el error; la clasificación conserva el
                # tema visible como Sin clasificar en vez de ocultarlo.
                nicho = None
            if nicho:
                fallback_matches += 1
            cache[titulo] = nicho

        tema["nicho"] = nicho or "Sin clasificar"

    return {
        "lookups": lookups,
        "cache_hits": cache_hits,
        "fallback_matches": fallback_matches,
    }
