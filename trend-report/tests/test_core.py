from __future__ import annotations

import unittest

from src.classify import (
    clasificar_con_descripcion,
    clasificar_por_titulo,
    coincide_keyword,
    invalidar_nones,
    normalizar,
)
from src.report_md import youtube_url
from src.scoring import (
    calcular_scores,
    growth_porcentual,
    rankear_nichos,
    ventanas_disponibles,
)


class ClassifyTests(unittest.TestCase):
    def test_normalizar_ignora_acentos_y_puntuacion(self) -> None:
        self.assertEqual(normalizar("Spider-Man: México"), "spider man mexico")

    def test_keyword_usa_limites_de_palabra(self) -> None:
        self.assertFalse(coincide_keyword("Terremoto de Colombia", "moto"))
        self.assertTrue(coincide_keyword("Moto eléctrica", "moto"))

    def test_clasificacion_respeta_orden(self) -> None:
        taxonomy = [
            {"nombre": "Clima", "claves": ["terremoto"]},
            {"nombre": "Autos", "claves": ["moto"]},
        ]
        self.assertEqual(clasificar_por_titulo("Terremoto de Colombia", taxonomy), "Clima")

    def test_fallback_prioriza_evidencia_profesional(self) -> None:
        taxonomy = [
            {"nombre": "Gaming", "claves": ["videojuegos", "mario"]},
            {"nombre": "Entretenimiento", "claves": ["actriz", "cantante"]},
        ]
        self.assertEqual(
            clasificar_con_descripcion(
                "Hayden Panettiere",
                "actriz, cantante y modelo estadounidense",
                "Su carrera también incluye videojuegos.",
                taxonomy,
            ),
            "Entretenimiento",
        )

    def test_cache_none_se_purga(self) -> None:
        cache = {"pendiente": None, "confirmado": "Deportes"}
        self.assertEqual(invalidar_nones(cache), 1)
        self.assertEqual(cache, {"confirmado": "Deportes"})


class ScoringTests(unittest.TestCase):
    def test_ventanas_separan_actual_y_base(self) -> None:
        current, base = ventanas_disponibles([f"2026-01-{day:02d}" for day in range(1, 11)], 3, 4)
        self.assertEqual(current, ["2026-01-08", "2026-01-09", "2026-01-10"])
        self.assertEqual(base, ["2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07"])

    def test_growth_usa_promedios_diarios(self) -> None:
        self.assertAlmostEqual(growth_porcentual([20, 20], [10, 10]), 100.0)

    def test_nicho_con_menos_de_tres_temas_no_compite(self) -> None:
        themes = [
            {"titulo": "a", "nicho": "Deportes", "vistas_periodo": 1000, "rss_trafico": 0, "hn_puntos": 0, "yt_rank": 0, "growth_pct": 20},
            {"titulo": "b", "nicho": "Deportes", "vistas_periodo": 800, "rss_trafico": 0, "hn_puntos": 0, "yt_rank": 0, "growth_pct": 10},
            {"titulo": "c", "nicho": "Deportes", "vistas_periodo": 500, "rss_trafico": 0, "hn_puntos": 0, "yt_rank": 0, "growth_pct": 5},
            {"titulo": "d", "nicho": "Salud", "vistas_periodo": 900, "rss_trafico": 0, "hn_puntos": 0, "yt_rank": 0, "growth_pct": 30},
        ]
        scoring = {"min_temas_nicho": 3, "top_miembros_nicho": 8}
        calcular_scores(themes, scoring)
        rankings = rankear_nichos(themes, scoring)
        self.assertEqual([item["nombre"] for item in rankings], ["Deportes"])


class ReportTests(unittest.TestCase):
    def test_youtube_url_codifica_acentos_y_ampersand(self) -> None:
        url = youtube_url("México & fútbol", "MX")
        self.assertIn("%C3%A9xico", url)
        self.assertIn("%26", url)


if __name__ == "__main__":
    unittest.main()
