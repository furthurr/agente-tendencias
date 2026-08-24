from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.validar_informe import validar_corrida


FIXTURE = Path(__file__).parent / "fixtures" / "validator" / "good"


class ValidatorTests(unittest.TestCase):
    def _copy_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        corrida = root / "corrida"
        corrida.mkdir()
        shutil.copy(FIXTURE / "auditoria.json", corrida / "auditoria.json")
        shutil.copy(FIXTURE / "temas_completos.json", corrida / "temas_completos.json")
        report = root / "informe.md"
        shutil.copy(FIXTURE / "informe.md", report)
        return temporary, report, corrida

    def test_fixture_buena_pasa_las_ocho_reglas(self) -> None:
        temporary, report, corrida = self._copy_fixture()
        self.addCleanup(temporary.cleanup)
        result = validar_corrida(report, corrida)
        self.assertTrue(result.ok, [check.to_dict() for check in result.fails])
        self.assertEqual(len(result.checks), 8)

    def test_ocho_mutaciones_disparan_su_regla(self) -> None:
        mutations = {
            "R1": lambda audit, themes, report: audit["fuentes"][0].update({"conteo": 20}),
            "R2": lambda audit, themes, report: audit["fuentes"][0].update({"estado": "ERROR"}),
            "R3": lambda audit, themes, report: audit["top_trending"][0].update({"n_temas": 2}),
            "R4": lambda audit, themes, report: report.replace("### 1. Deportes", "### 1. Sin clasificar"),
            "R5": lambda audit, themes, report: themes[0].update({"growth_pct": 90.0}),
            "R6": lambda audit, themes, report: report.replace(
                "Intersección de máxima prioridad:** Deportes.",
                "Intersección de máxima prioridad:** Salud.",
            ),
            "R7": lambda audit, themes, report: report + "\n[bad](https://es.wikipedia.org/wiki/México)\n",
            "R8": lambda audit, themes, report: None,
        }
        for rule, mutation in mutations.items():
            with self.subTest(rule=rule):
                temporary, report_path, corrida = self._copy_fixture()
                audit_path = corrida / "auditoria.json"
                themes_path = corrida / "temas_completos.json"
                audit = json.loads(audit_path.read_text(encoding="utf-8"))
                themes = json.loads(themes_path.read_text(encoding="utf-8"))
                report = report_path.read_text(encoding="utf-8")
                value = mutation(audit, themes, report)
                if isinstance(value, str):
                    report = value
                audit_path.write_text(json.dumps(audit), encoding="utf-8")
                themes_path.write_text(json.dumps(themes), encoding="utf-8")
                if rule == "R8":
                    themes_path.unlink()
                report_path.write_text(report, encoding="utf-8")
                result = validar_corrida(report_path, corrida)
                self.assertTrue(any(check.regla == rule and check.estado == "FAIL" for check in result.checks))
                temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
