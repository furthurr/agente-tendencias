"""Construcción del universo y scoring de temas/nichos."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any, Iterable

from .classify import es_tema_excluido, normalizar


def ventanas_disponibles(
    fechas: Iterable[str], days_current: int, days_base: int
) -> tuple[list[str], list[str]]:
    ordered = sorted(set(fechas))
    if not ordered:
        return [], []
    current = ordered[-days_current:]
    split = max(0, len(ordered) - len(current))
    base = ordered[max(0, split - days_base) : split]
    return current, base


def promedio_diario(valores: Iterable[float]) -> float:
    values = [float(value) for value in valores]
    return sum(values) / len(values) if values else 0.0


def growth_porcentual(current_values: Iterable[float], base_values: Iterable[float]) -> float:
    current_avg = promedio_diario(current_values)
    base_avg = promedio_diario(base_values)
    if base_avg <= 1:
        return 0.0
    return (current_avg - base_avg) / base_avg * 100.0


def _empty_theme(titulo: str, *, period_name: str) -> dict[str, Any]:
    return {
        "titulo": titulo,
        "periodo": period_name,
        "vistas_periodo": 0,
        "vistas_semana": 0,
        "base_periodo": 0.0,
        "base_semana": 0.0,
        "growth_pct": 0.0,
        "dias_semana": 0,
        "dias_base": 0,
        "rss_trafico": 0,
        "hn_puntos": 0,
        "yt_rank": 0.0,
        "nicho": "Sin clasificar",
        "es_historia_hn": False,
        "trending_score": 0.0,
        "growth_score": 0.0,
        "score_final": 0.0,
    }


def _match_title(candidate: str, titles: Iterable[str]) -> str | None:
    candidate_norm = normalizar(candidate)
    exact: dict[str, str] = {normalizar(title): title for title in titles}
    if candidate_norm in exact:
        return exact[candidate_norm]
    if len(candidate_norm) < 5:
        return None
    for normalized, original in exact.items():
        if len(normalized) >= 5 and (candidate_norm in normalized or normalized in candidate_norm):
            return original
    return None


def construir_universo(
    wiki_data: dict[str, Any],
    rss_items: list[dict[str, Any]],
    hn_items: list[dict[str, Any]],
    period_name: str,
    days_current: int,
    days_base: int,
    min_views: int = 30,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Une Wikipedia, RSS y HN en el esquema auditable de la spec."""

    article_daily: dict[str, dict[str, int]] = wiki_data.get("article_daily", {})
    available_dates = wiki_data.get("days_available", [])
    current_dates, base_dates = ventanas_disponibles(available_dates, days_current, days_base)
    themes: dict[str, dict[str, Any]] = {}

    for raw_title, daily in article_daily.items():
        title = raw_title.replace("_", " ").strip()
        if es_tema_excluido(title):
            continue
        current_values = [int(daily.get(day, 0)) for day in current_dates]
        base_values = [int(daily.get(day, 0)) for day in base_dates]
        current_total = sum(current_values)
        if current_total < min_views:
            continue
        theme = _empty_theme(title, period_name=period_name)
        theme.update(
            {
                "vistas_periodo": current_total,
                "vistas_semana": current_total,
                "base_periodo": promedio_diario(base_values) * max(1, len(current_dates)),
                "base_semana": promedio_diario(base_values) * 7,
                "growth_pct": growth_porcentual(current_values, base_values),
                "dias_semana": len([value for value in current_values if value > 0]),
                "dias_base": len([value for value in base_values if value > 0]),
                "valores_actuales": current_values,
                "valores_base": base_values,
            }
        )
        themes[title] = theme

    wiki_titles = list(themes)
    for item in rss_items:
        title = str(item.get("titulo", "")).strip()
        if not title or es_tema_excluido(title):
            continue
        match = _match_title(title, wiki_titles)
        if match:
            themes[match]["rss_trafico"] += int(item.get("rss_trafico", 0) or 0)
            themes[match].setdefault("rss_items", []).append(item)
            continue
        if title not in themes:
            theme = _empty_theme(title, period_name=period_name)
            theme["rss_trafico"] = int(item.get("rss_trafico", 0) or 0)
            theme["rss_items"] = [item]
            theme["es_tema_rss"] = True
            themes[title] = theme

    for item in hn_items[:30]:
        title = str(item.get("titulo", "")).strip()
        if not title or es_tema_excluido(title):
            continue
        match = _match_title(title, themes)
        target = themes.get(match) if match else None
        if target is None:
            target = _empty_theme(title, period_name=period_name)
            target["es_historia_hn"] = True
            themes[title] = target
        target["hn_puntos"] += int(item.get("hn_puntos", 0) or 0)
        target.setdefault("hn_items", []).append(item)
        target["es_historia_hn"] = True

    return list(themes.values()), current_dates, base_dates


def _log_minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    transformed = [math.log1p(max(0.0, value)) for value in values]
    low, high = min(transformed), max(transformed)
    if high == low:
        return [1.0 if high > 0 else 0.0 for _ in transformed]
    return [(value - low) / (high - low) for value in transformed]


def calcular_scores(temas: list[dict[str, Any]], scoring: dict[str, Any]) -> list[dict[str, Any]]:
    """Aplica las fórmulas exactas del documento maestro."""

    wiki_norm = _log_minmax([float(theme.get("vistas_periodo", 0)) for theme in temas])
    rss_norm = _log_minmax([float(theme.get("rss_trafico", 0)) for theme in temas])
    hn_norm = _log_minmax([float(theme.get("hn_puntos", 0)) for theme in temas])
    weights = scoring.get("trending", {})
    growth_weights = scoring.get("growth", {})
    theme_weights = scoring.get("tema", {})

    for index, theme in enumerate(temas):
        theme["n_wiki"] = wiki_norm[index]
        theme["n_rss"] = rss_norm[index]
        theme["n_hn"] = hn_norm[index]
        theme["n_yt"] = max(0.0, min(1.0, float(theme.get("yt_rank", 0.0))))
        theme["trending_score"] = (
            float(weights.get("wiki", 0.45)) * theme["n_wiki"]
            + float(weights.get("rss", 0.25)) * theme["n_rss"]
            + float(weights.get("yt", 0.20)) * theme["n_yt"]
            + float(weights.get("hn", 0.10)) * theme["n_hn"]
        )
        crecimiento = max(0.0, min(float(theme.get("growth_pct", 0.0)), 500.0)) / 500.0
        if float(theme.get("vistas_periodo", 0)) < 300:
            crecimiento = 0.0
        theme["growth_score"] = (
            float(growth_weights.get("crecimiento", 0.65)) * crecimiento
            + float(growth_weights.get("tamano", 0.35)) * theme["n_wiki"]
        )
        theme["score_final"] = (
            float(theme_weights.get("trending", 0.60)) * theme["trending_score"]
            + float(theme_weights.get("growth", 0.40)) * theme["growth_score"]
        )
    return temas


def rankear_nichos(temas: list[dict[str, Any]], scoring: dict[str, Any]) -> list[dict[str, Any]]:
    min_topics = int(scoring.get("min_temas_nicho", 3))
    top_members = int(scoring.get("top_miembros_nicho", 8))
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for theme in temas:
        niche = theme.get("nicho", "Sin clasificar")
        if niche != "Sin clasificar":
            groups[str(niche)].append(theme)

    rankings: list[dict[str, Any]] = []
    for name, members in groups.items():
        if len(members) < min_topics:
            continue
        best_trending = sorted(members, key=lambda item: item.get("trending_score", 0), reverse=True)[:top_members]
        best_growth = sorted(members, key=lambda item: item.get("growth_score", 0), reverse=True)[:top_members]
        trending = promedio_diario(item.get("trending_score", 0) for item in best_trending)
        growth = promedio_diario(item.get("growth_score", 0) for item in best_growth)
        rankings.append(
            {
                "nombre": name,
                "n_temas": len(members),
                "trending_score": trending,
                "growth_score": growth,
                "score_final": 0.60 * trending + 0.40 * growth,
            }
        )
    return sorted(rankings, key=lambda item: item["score_final"], reverse=True)


def seleccionar_top_nichos(rankings: list[dict[str, Any]], count: int, dimension: str) -> list[dict[str, Any]]:
    return sorted(rankings, key=lambda item: item.get(dimension, 0), reverse=True)[:count]


def temas_de_nicho(temas: list[dict[str, Any]], nombre: str, count: int = 5) -> list[dict[str, Any]]:
    members = [theme for theme in temas if theme.get("nicho") == nombre]
    return sorted(members, key=lambda item: item.get("score_final", 0), reverse=True)[:count]
