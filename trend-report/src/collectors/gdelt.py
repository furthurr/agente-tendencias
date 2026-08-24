"""Señal noticiosa opcional de GDELT."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..http import HttpClient, HttpError, guardar_crudo
from . import source_status


GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def _stamp(value: datetime) -> str:
    return value.strftime("%Y%m%d%H%M%S")


def _timeline_average(payload: Any) -> float:
    values: list[float] = []
    if isinstance(payload, dict):
        timeline = payload.get("timeline", [])
        if isinstance(timeline, list):
            for row in timeline:
                if isinstance(row, dict):
                    for key in ("value", "volume", "count"):
                        if isinstance(row.get(key), (int, float)):
                            values.append(float(row[key]))
                            break
                    else:
                        if isinstance(row.get("data"), list):
                            values.extend(float(item) for item in row["data"] if isinstance(item, (int, float)))
    return sum(values) / len(values) if values else 0.0


def recoger(
    client: HttpClient,
    queries: list[str],
    days_current: int,
    days_base: int,
    raw_dir: str | Path,
    sleep_seconds: float = 2.0,
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    now = datetime.now(timezone.utc)
    current_start = now - timedelta(days=days_current)
    base_start = current_start - timedelta(days=days_base)
    result: dict[str, dict[str, float]] = {}
    errors = 0
    for query in queries:
        try:
            current = client.get_json(
                GDELT_URL,
                params={
                    "query": query,
                    "mode": "timelinevol",
                    "format": "json",
                    "startdatetime": _stamp(current_start),
                    "enddatetime": _stamp(now),
                },
            )
            base = client.get_json(
                GDELT_URL,
                params={
                    "query": query,
                    "mode": "timelinevol",
                    "format": "json",
                    "startdatetime": _stamp(base_start),
                    "enddatetime": _stamp(current_start),
                },
            )
            guardar_crudo(Path(raw_dir) / "gdelt" / f"{query[:60]}.json", {"current": current, "base": base})
            current_avg = _timeline_average(current)
            base_avg = _timeline_average(base)
            result[query] = {
                "actual": current_avg,
                "base": base_avg,
                "growth_pct": ((current_avg - base_avg) / base_avg * 100) if base_avg > 1 else 0.0,
            }
        except HttpError:
            errors += 1
        time.sleep(max(0.0, sleep_seconds))
    state = "OK" if queries and errors == 0 else "ERROR"
    return result, source_status("GDELT", state, len(result), f"{errors}/{len(queries)} consultas con error")
