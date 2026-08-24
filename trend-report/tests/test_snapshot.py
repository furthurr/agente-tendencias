from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.http import HttpError
from src.snapshot import capturar


RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:ht="https://trends.google.com/trending/rss">
  <channel>
    <item>
      <title>Querétaro</title>
      <ht:approx_traffic>2,000+</ht:approx_traffic>
      <pubDate>Mon, 24 Aug 2026 12:00:00 GMT</pubDate>
      <ht:news_item>
        <ht:news_item_title>Contexto de Querétaro</ht:news_item_title>
        <ht:news_item_url>https://example.test/queretaro</ht:news_item_url>
        <ht:news_item_source>Fuente MX</ht:news_item_source>
      </ht:news_item>
    </item>
    <item>
      <title>Spider-Man: Brand New Day</title>
      <ht:approx_traffic>500+</ht:approx_traffic>
    </item>
  </channel>
</rss>
"""


class FakeClient:
    def get_text(self, url: str, *, params: dict[str, str]) -> str:
        return RSS_FIXTURE


class FailingClient:
    def get_text(self, url: str, *, params: dict[str, str]) -> str:
        raise HttpError("429 simulado", url=url, status_code=429)


class SnapshotTests(unittest.TestCase):
    def test_snapshot_es_idempotente_y_conserva_esquema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = datetime(2026, 8, 24, 15, 0, tzinfo=timezone.utc)
            first = capturar("MX", directory, client=FakeClient(), ahora=now)
            second = capturar("MX", directory, client=FakeClient(), ahora=now)
            path = Path(directory) / "trends_MX.jsonl"
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

            self.assertEqual(first["nuevos"], 2)
            self.assertEqual(second["nuevos"], 0)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["fecha"], "2026-08-24")
            self.assertEqual(rows[0]["trafico_num"], 2000)
            self.assertEqual(rows[0]["fuente_noticia"], "Fuente MX")
            self.assertIn("capturado_utc", rows[0])

    def test_error_rss_se_registra_sin_romper_proceso(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = capturar("MX", directory, client=FailingClient(), ahora=datetime(2026, 8, 24, tzinfo=timezone.utc))
            state_path = Path(directory) / "estado_MX.jsonl"
            state = json.loads(state_path.read_text(encoding="utf-8").strip())
            self.assertEqual(result["estado"], "error")
            self.assertEqual(state["estado"], "error")


if __name__ == "__main__":
    unittest.main()
