"""Refuerzo de tecnología mediante Hacker News/Algolia."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..http import HttpClient, HttpError, guardar_crudo
from . import source_status


ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"


def recoger(
    client: HttpClient,
    days: int,
    raw_dir: str | Path,
    points_min: int = 50,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    try:
        payload = client.get_json(
            ALGOLIA_URL,
            params={
                "tags": "story",
                "numericFilters": f"created_at_i>{since},points>{points_min}",
                "hitsPerPage": 100,
            },
        )
        guardar_crudo(Path(raw_dir) / "hackernews.json", payload)
    except HttpError as exc:
        return [], source_status("Hacker News", "ERROR", detalle=str(exc))

    stories: list[dict[str, Any]] = []
    for hit in payload.get("hits", []) if isinstance(payload, dict) else []:
        title = str(hit.get("title", "")).strip()
        if not title:
            continue
        stories.append(
            {
                "titulo": title,
                "hn_puntos": int(hit.get("points", 0) or 0),
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                "created_at": hit.get("created_at", ""),
            }
        )
    stories.sort(key=lambda item: item["hn_puntos"], reverse=True)
    time.sleep(0.35)
    return stories[:60], source_status("Hacker News", "OK", min(60, len(stories)), f"ventana={days} días")
