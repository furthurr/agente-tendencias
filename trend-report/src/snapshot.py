"""Captura diaria e idempotente del RSS de Google Trends.

Ejecutar desde ``trend-report``:

    python3 -m src.snapshot --geo MX

Los fallos de la fuente se registran en JSONL y devuelven código 0 para que el
workflow pueda continuar; los errores de configuración o escritura sí devuelven
código distinto de cero.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    import yaml
except ImportError:  # pragma: no cover - el workflow instala requirements.txt
    yaml = None

if __package__ in (None, ""):  # permite también `python3 src/snapshot.py`
    script_dir = Path(__file__).resolve().parent
    sys.path = [
        entry
        for entry in sys.path
        if entry and Path(entry).resolve() != script_dir
    ]
    sys.path.insert(0, str(script_dir.parent))
    from src.classify import normalizar
    from src.collectors.rss_mx import RSS_URL, parsear_xml
    from src.http import HttpClient, HttpError, guardar_crudo
else:
    from .classify import normalizar
    from .collectors.rss_mx import RSS_URL, parsear_xml
    from .http import HttpClient, HttpError, guardar_crudo


ROOT = Path(__file__).resolve().parent.parent
MEXICO_ZONE = ZoneInfo("America/Mexico_City")
DEFAULT_UA = "AgenteTendencias/0.1 (snapshot RSS; contacto local)"


def _config() -> dict[str, Any]:
    if yaml is None:
        return {}
    path = ROOT / "config.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _client() -> HttpClient:
    config = _config()
    project = config.get("proyecto", {})
    http = config.get("http", {})
    return HttpClient(
        user_agent=str(project.get("user_agent", DEFAULT_UA)),
        timeout=float(http.get("timeout", 25)),
        retries=int(http.get("retries", 2)),
        backoff_initial=float(http.get("backoff_inicial", 1.0)),
    )


def _business_date(now_utc: datetime) -> str:
    return now_utc.astimezone(MEXICO_ZONE).date().isoformat()


def _utc_stamp(now_utc: datetime) -> str:
    return now_utc.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_jsonl_keys(path: Path, key_fields: tuple[str, ...]) -> set[tuple[str, ...]]:
    keys: set[tuple[str, ...]] = set()
    if not path.exists():
        return keys
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if not isinstance(value, dict):
            continue
        key: list[str] = []
        valid = True
        for field in key_fields:
            field_value = value.get(field)
            if field_value is None:
                valid = False
                break
            key.append(normalizar(str(field_value)) if field == "titulo" else str(field_value))
        if valid:
            keys.add(tuple(key))
    return keys


def _append_unique(path: Path, rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_jsonl_keys(path, key_fields)
    new_rows: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(
            normalizar(str(row[field])) if field == "titulo" else str(row[field])
            for field in key_fields
        )
        if key in existing:
            continue
        existing.add(key)
        new_rows.append(row)
    if new_rows:
        with path.open("a", encoding="utf-8") as handle:
            for row in new_rows:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(new_rows)


def _state_row(fecha: str, estado: str, detalle: str) -> dict[str, str]:
    return {"fecha": fecha, "estado": estado, "detalle": detalle}


def capturar(
    geo: str = "MX",
    data_dir: str | Path | None = None,
    *,
    client: HttpClient | Any | None = None,
    ahora: datetime | None = None,
) -> dict[str, Any]:
    """Captura RSS; recibe cliente/fecha inyectables para pruebas."""

    geo = geo.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", geo):
        raise ValueError("geo debe ser un código ISO de dos letras, por ejemplo MX")
    now_utc = ahora or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    fecha = _business_date(now_utc)
    captured = _utc_stamp(now_utc)
    target_dir = Path(data_dir) if data_dir is not None else ROOT / "data" / "snapshots"
    target_dir.mkdir(parents=True, exist_ok=True)
    trends_path = target_dir / f"trends_{geo}.jsonl"
    state_path = target_dir / f"estado_{geo}.jsonl"

    http = client or _client()
    try:
        xml_text = http.get_text(RSS_URL, params={"geo": geo})
        raw_path = target_dir / "raw" / f"trends_{geo}_{fecha}.xml"
        guardar_crudo(raw_path, xml_text, texto=True)
        items = parsear_xml(xml_text)
    except (HttpError, OSError, ValueError, ET.ParseError) as exc:
        detail = str(exc)
        _append_unique(state_path, [_state_row(fecha, "error", detail)], ("fecha", "estado", "detalle"))
        return {"geo": geo, "fecha": fecha, "estado": "error", "nuevos": 0, "detalle": detail}

    if not items:
        detail = "RSS sin términos"
        _append_unique(state_path, [_state_row(fecha, "vacio", detail)], ("fecha", "estado", "detalle"))
        return {"geo": geo, "fecha": fecha, "estado": "vacio", "nuevos": 0, "detalle": detail}

    rows: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for item in items:
        title = str(item.get("titulo", "")).strip()
        title_key = normalizar(title)
        if not title or not title_key or title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        news = item.get("news_items") or [{}]
        first_news = news[0] if isinstance(news[0], dict) else {}
        rows.append(
            {
                "fecha": fecha,
                "geo": geo,
                "titulo": title,
                "trafico_texto": str(item.get("rss_trafico_texto", "") or ""),
                "trafico_num": int(item.get("rss_trafico", 0) or 0),
                "titular": str(first_news.get("titulo", "") or ""),
                "url_noticia": str(first_news.get("url", "") or ""),
                "fuente_noticia": str(first_news.get("fuente", "") or ""),
                "capturado_utc": captured,
            }
        )
    added = _append_unique(trends_path, rows, ("fecha", "geo", "titulo"))
    return {
        "geo": geo,
        "fecha": fecha,
        "estado": "ok" if rows else "vacio",
        "nuevos": added,
        "terminos": len(rows),
        "ruta": str(trends_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarda un snapshot diario de Google Trends RSS")
    parser.add_argument("--geo", default="MX", help="geografía ISO de dos letras")
    parser.add_argument("--data-dir", help="directorio de snapshots; por defecto trend-report/data/snapshots")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = capturar(args.geo, args.data_dir)
    except (OSError, ValueError) as exc:
        print(f"Error duro de snapshot: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
