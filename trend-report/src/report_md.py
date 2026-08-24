"""Renderizador del informe Markdown y enlaces auditables."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote, quote_plus
from typing import Any, Iterable

from .scoring import temas_de_nicho


def wiki_url(title: str) -> str:
    return f"https://es.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}"


def trends_url(title: str, geo: str) -> str:
    return f"https://trends.google.com/trends/explore?geo={quote(geo)}&q={quote_plus(title)}"


def youtube_url(title: str, geo: str) -> str:
    # geo se conserva en el contexto aunque el enlace de búsqueda no lo expone.
    del geo
    return f"https://www.youtube.com/results?search_query={quote_plus(title)}"


def _pct(value: float | int | None) -> str:
    if value is None:
        return "—"
    number = float(value)
    arrow = "▲" if number > 0.5 else "▼" if number < -0.5 else "—"
    return f"{arrow} {number:+.1f}%"


def _score(value: float | int | None) -> str:
    return f"{float(value or 0):.3f}"


def _source_table(statuses: Iterable[dict[str, Any]]) -> list[str]:
    lines = ["| Fuente | Estado | Registros | Detalle |", "|---|---|---:|---|"]
    for status in statuses:
        state = status.get("estado", "ERROR")
        count = status.get("conteo", 0)
        detail = str(status.get("detalle", "")).replace("|", "\\|")
        lines.append(f"| {status.get('fuente', 'desconocida')} | {state} | {count} | {detail} |")
    return lines


def _topic_table(temas: list[dict[str, Any]], geo: str, period_label: str) -> list[str]:
    lines = [
        f"| Tema | Vistas/{period_label.lower()} | Δ vs base | Trending | Growth | Enlaces |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for theme in temas:
        title = theme.get("titulo", "")
        links = (
            f"[Wiki]({wiki_url(title)}) · "
            f"[Trends]({trends_url(title, geo)}) · "
            f"[YT]({youtube_url(title, geo)})"
        )
        lines.append(
            f"| {title} | {int(theme.get('vistas_periodo', 0)):,} | {_pct(theme.get('growth_pct'))} | "
            f"{_score(theme.get('trending_score'))} | {_score(theme.get('growth_score'))} | {links} |"
        )
    if not temas:
        lines.append("| _Sin temas suficientes_ | — | — | — | — | — |")
    return lines


def _niche_section(
    heading: str,
    rankings: list[dict[str, Any]],
    temas: list[dict[str, Any]],
    geo: str,
    period_label: str,
) -> list[str]:
    lines = [f"## {heading}", ""]
    for index, niche in enumerate(rankings, start=1):
        lines.extend(
            [
                f"### {index}. {niche['nombre']}",
                f"Score: **{_score(niche.get('score_final'))}** · temas elegibles: **{niche.get('n_temas', 0)}** · "
                f"trending: `{_score(niche.get('trending_score'))}` · growth: `{_score(niche.get('growth_score'))}`",
                "",
            ]
        )
        lines.extend(_topic_table(temas_de_nicho(temas, niche["nombre"], 5), geo, period_label))
        lines.append("")
    if not rankings:
        lines.extend(["_No hubo nichos con el mínimo de temas requerido._", ""])
    return lines


def generar_informe(context: dict[str, Any]) -> str:
    period_label = context["period_label"]
    geo = context["geo"]
    generated_at = context.get("generated_at") or datetime.now().astimezone().isoformat()
    current_dates = context.get("current_dates", [])
    base_dates = context.get("base_dates", [])
    trending = context.get("top_trending", [])
    growth = context.get("top_growth", [])
    themes = context.get("temas", [])
    statuses = context.get("source_statuses", [])
    intersection = sorted({item["nombre"] for item in trending} & {item["nombre"] for item in growth})

    lines = [
        f"# Informe de tendencias — {period_label}",
        "",
        f"- **Período:** `{context['period']}`",
        f"- **Rango actual:** `{current_dates[0] if current_dates else '—'}` → `{current_dates[-1] if current_dates else '—'}`",
        f"- **Rango base:** `{base_dates[0] if base_dates else '—'}` → `{base_dates[-1] if base_dates else '—'}`",
        f"- **Generado:** `{generated_at}`",
        f"- **Geografía:** `{geo}`",
        "- **Objetivo:** detectar nichos y temas accionables para crear contenido en YouTube.",
        "",
        "## Resumen ejecutivo",
        "",
        "| Ranking | TRENDING | MAYOR CRECIMIENTO |",
        "|---:|---|---|",
    ]
    max_rows = max(len(trending), len(growth), 1)
    for index in range(max_rows):
        trend_name = trending[index]["nombre"] if index < len(trending) else "—"
        growth_name = growth[index]["nombre"] if index < len(growth) else "—"
        lines.append(f"| {index + 1} | {trend_name} | {growth_name} |")
    lines.extend(
        [
            "",
            f"**Intersección de máxima prioridad:** {', '.join(intersection) if intersection else 'ninguna en esta corrida'}.",
            "",
            "## Metodología y fuentes",
            "",
            f"La ventana **{period_label.lower()}** usa {context['days_current']} días actuales y "
            f"{context['days_base']} días base. El crecimiento compara promedios diarios presentes, "
            "no totales divididos por una cantidad fija de días.",
            "",
            "Fórmulas principales:",
            "",
            "```text",
            "growth_pct = (promedio_actual - promedio_base) / promedio_base * 100, si promedio_base > 1",
            "trending = 0.45*n_wiki + 0.25*n_rss + 0.20*n_yt + 0.10*n_hn",
            "growth = 0.65*clip(growth_pct, 0, 500)/500 + 0.35*n_wiki",
            "score_final = 0.60*trending + 0.40*growth",
            "nicho = promedio de los 8 mejores miembros; mínimo 3 temas",
            "```",
            "",
            *(_source_table(statuses)),
            "",
            f"Temas en el universo: **{len(themes)}** · clasificados: **{len([t for t in themes if t.get('nicho') != 'Sin clasificar'])}** · "
            f"sin clasificar: **{len([t for t in themes if t.get('nicho') == 'Sin clasificar'])}**.",
            "",
        ]
    )
    lines.extend(_niche_section("Top 3 TRENDING", trending, themes, geo, period_label))
    lines.extend(_niche_section("Top 3 CRECIMIENTO", growth, themes, geo, period_label))

    lines.extend(["## Oportunidades YouTube", ""])
    suggestions = context.get("yt_suggestions", {})
    candidate_names = []
    for niche in trending + growth:
        if niche["nombre"] not in candidate_names:
            candidate_names.append(niche["nombre"])
    if intersection:
        lines.append("### Máxima prioridad")
        lines.append(f"{', '.join(intersection)} aparece en trending y crecimiento.")
        lines.append("")
    for name in candidate_names:
        lines.append(f"### {name}")
        niche_suggestions = suggestions.get(name, [])[:8]
        if not niche_suggestions:
            lines.append("- _Sin sugerencias disponibles (YouTube omitido o sin respuesta)._ ")
        else:
            for suggestion in niche_suggestions:
                lines.append(f"- [{suggestion}]({youtube_url(suggestion, geo)})")
        lines.append("")

    unclassified = sorted(
        [theme for theme in themes if theme.get("nicho") == "Sin clasificar"],
        key=lambda item: item.get("vistas_periodo", 0),
        reverse=True,
    )[:30]
    lines.extend(["## Anexo", "", "### Temas sin clasificar", ""])
    if unclassified:
        for theme in unclassified:
            lines.append(f"- {theme['titulo']} — {int(theme.get('vistas_periodo', 0)):,} vistas/{period_label.lower()}")
    else:
        lines.append("- Ninguno en esta corrida.")
    lines.extend(
        [
            "",
            "### Notas de reproducibilidad",
            "",
            f"- La corrida cruda está en `{context.get('raw_dir', 'data/raw/<corrida>')}`.",
            "- Wikipedia puede tener aproximadamente dos días de retraso y puede responder con throttling.",
            "- Google Trends RSS representa el día de la corrida; no es por sí solo una serie semanal/mensual/anual.",
            "- `Sin clasificar` no participa en los rankings; se conserva aquí para mejorar la taxonomía.",
            "",
        ]
    )
    return "\n".join(lines)
