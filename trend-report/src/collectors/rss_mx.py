"""Colector de Google Trends RSS."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..http import HttpClient, HttpError, guardar_crudo
from . import source_status


RSS_URL = "https://trends.google.com/trending/rss"
HT_NS = "https://trends.google.com/trending/rss"


def _text(element: ET.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def _traffic(value: str) -> int:
    digits = re.sub(r"[^0-9]", "", value or "")
    return int(digits) if digits else 0


def parsear_xml(xml_text: str) -> list[dict[str, Any]]:
    """Parsea RSS sin I/O para reutilizarlo en el snapshot diario."""

    root = ET.fromstring(xml_text)
    items: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        news_items: list[dict[str, str]] = []
        for news in item.findall(f"{{{HT_NS}}}news_item"):
            news_items.append(
                {
                    "titulo": _text(news.find(f"{{{HT_NS}}}news_item_title")),
                    "url": _text(news.find(f"{{{HT_NS}}}news_item_url")),
                    "fuente": _text(news.find(f"{{{HT_NS}}}news_item_source")),
                }
            )
        traffic_text = _text(item.find(f"{{{HT_NS}}}approx_traffic"))
        items.append(
            {
                "titulo": _text(item.find("title")),
                "rss_trafico": _traffic(traffic_text),
                "rss_trafico_texto": traffic_text,
                "pub_date": _text(item.find("pubDate")),
                "news_items": news_items,
            }
        )
    return items


def recoger(client: HttpClient, geo: str, raw_dir: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        xml_text = client.get_text(RSS_URL, params={"geo": geo})
        guardar_crudo(Path(raw_dir) / "google_trends_rss.xml", xml_text, texto=True)
        items = parsear_xml(xml_text)
    except (HttpError, ET.ParseError) as exc:
        return [], source_status("Google Trends RSS", "ERROR", detalle=str(exc))
    return items, source_status("Google Trends RSS", "OK", len(items), f"geo={geo}; señal del día")
