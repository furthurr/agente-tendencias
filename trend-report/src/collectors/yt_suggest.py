"""Autocompletado de Google Suggest en modo YouTube."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from ..classify import normalizar
from ..http import HttpClient, HttpError, guardar_crudo
from . import source_status


SUGGEST_URL = "https://suggestqueries.google.com/complete/search"


def sugerencias(
    client: HttpClient,
    query: str,
    geo: str,
    raw_dir: str | Path,
) -> list[str]:
    payload = client.get_json(
        SUGGEST_URL,
        params={"client": "firefox", "ds": "yt", "hl": "es", "gl": geo, "q": query},
    )
    guardar_crudo(Path(raw_dir) / "youtube_suggest" / f"{quote_plus(query)[:120]}.json", payload)
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        return []
    return [str(value) for value in payload[1] if str(value).strip()]


def recoger_por_nicho(
    client: HttpClient,
    nichos: list[dict[str, Any]],
    geo: str,
    raw_dir: str | Path,
    max_per_seed: int = 8,
    sleep_seconds: float = 0.38,
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    result: dict[str, list[str]] = {}
    requested = 0
    errors = 0
    for niche in nichos:
        values: list[str] = []
        for seed in niche.get("semillas_yt", []):
            requested += 1
            try:
                values.extend(sugerencias(client, str(seed), geo, raw_dir)[:max_per_seed])
            except HttpError:
                errors += 1
            time.sleep(max(0.0, sleep_seconds))
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = normalizar(value)
            if key and key not in seen:
                seen.add(key)
                deduped.append(value)
        result[str(niche["nombre"])] = deduped[:8]
    state = "OK" if requested and errors < requested else "ERROR"
    return result, source_status("YouTube Suggest", state, sum(len(v) for v in result.values()), f"{errors}/{requested} consultas con error")


def validar_temas(
    client: HttpClient,
    temas: list[dict[str, Any]],
    geo: str,
    raw_dir: str | Path,
    max_sugerencias: int = 10,
    sleep_seconds: float = 0.38,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Valida títulos contra sus propias sugerencias y devuelve el mejor rank."""

    matches: dict[str, dict[str, Any]] = {}
    errors = 0
    for theme in temas:
        title = str(theme.get("titulo", ""))
        try:
            values = sugerencias(client, title, geo, raw_dir)[:max_sugerencias]
        except HttpError:
            values = []
            errors += 1
        best_rank = 0.0
        best_position: int | None = None
        best_suggestion = ""
        title_norm = normalizar(title)
        for position, suggestion in enumerate(values):
            suggestion_norm = normalizar(suggestion)
            if title_norm and (title_norm in suggestion_norm or suggestion_norm in title_norm):
                candidate = (len(values) - position) / max(1, len(values))
                if position > 0:
                    candidate *= 0.6
                if candidate > best_rank:
                    best_rank = candidate
                    best_position = position
                    best_suggestion = suggestion
        matches[title] = {
            "yt_rank": best_rank,
            "yt_position": best_position,
            "yt_sugerencia": best_suggestion,
        }
        time.sleep(max(0.0, sleep_seconds))
    state = "OK" if temas and errors < len(temas) else "ERROR"
    return matches, source_status("YouTube validación", state, len(matches), f"{errors}/{len(temas)} títulos con error")
