"""Colector de top pageviews y resúmenes de Wikipedia en español."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ..http import HttpClient, HttpError, guardar_crudo
from . import source_status


TOP_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/es.wikipedia/all-access"
SUMMARY_URL = "https://es.wikipedia.org/api/rest_v1/page/summary"


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value)
    return cleaned[:100] or "item"


def recoger_pageviews(
    client: HttpClient,
    days_current: int,
    days_base: int,
    raw_dir: str | Path,
    sleep_seconds: float = 0.35,
    stop_failures: int = 6,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Descarga días disponibles desde hoy-2 y conserva cada respuesta cruda."""

    total_days = max(1, days_current + days_base)
    end_date = date.today() - timedelta(days=2)
    days_available: list[str] = []
    article_daily: dict[str, dict[str, int]] = {}
    failures = 0
    successful_articles = 0

    for offset in range(total_days - 1, -1, -1):
        current = end_date - timedelta(days=offset)
        stamp = current.strftime("%Y/%m/%d")
        url = f"{TOP_URL}/{stamp}"
        try:
            payload = client.get_json(url)
            guardar_crudo(Path(raw_dir) / "wikipedia" / f"{current.isoformat()}.json", payload)
            articles = payload.get("items", [{}])[0].get("articles", [])
            if not isinstance(articles, list) or not articles:
                failures += 1
                continue
            day = current.isoformat()
            days_available.append(day)
            failures = 0
            for article in articles:
                raw_title = str(article.get("article", "")).strip()
                if not raw_title:
                    continue
                views = int(article.get("views", 0) or 0)
                article_daily.setdefault(raw_title, {})[day] = views
                successful_articles += 1
        except HttpError:
            failures += 1
            if failures >= stop_failures:
                break
        if offset > 0:
            # La API necesita ritmo estable; el sleep también reduce throttling
            # silencioso observado en historiales largos.
            import time

            time.sleep(max(0.0, sleep_seconds))

    days_available = sorted(set(days_available))
    status = source_status(
        "Wikipedia pageviews",
        "OK" if days_available else "ERROR",
        len(days_available),
        f"{len(article_daily)} artículos únicos; {failures} fallos finales",
        articles_unique=len(article_daily),
        fallos=failures,
    )
    return {"days_available": days_available, "article_daily": article_daily}, status


def recoger_resumen(
    client: HttpClient,
    titulo: str,
    raw_dir: str | Path,
) -> dict[str, str]:
    encoded = quote(titulo.replace(" ", "_"), safe="")
    url = f"{SUMMARY_URL}/{encoded}"
    payload = client.get_json(url)
    guardar_crudo(Path(raw_dir) / "wikipedia_summaries" / f"{_safe_name(titulo)}.json", payload)
    return {
        "description": str(payload.get("description", "") or ""),
        "extract": str(payload.get("extract", "") or ""),
    }
