"""Validador stdlib-only del informe y sus artefactos de auditoría.

Uso:

    python3 -m src.validar_informe \
      --report reports/informe_tendencias_2026-W35.md \
      --corrida data/raw/20260824T203201Z-semana

El módulo no hace red. Cada regla es independiente para poder probar escenarios
rotos sin ejecutar el pipeline completo.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    regla: str
    estado: str
    detalle: str

    def to_dict(self) -> dict[str, str]:
        return {"regla": self.regla, "estado": self.estado, "detalle": self.detalle}


@dataclass
class ValidationResult:
    checks: list[CheckResult]

    @property
    def fails(self) -> list[CheckResult]:
        return [check for check in self.checks if check.estado == "FAIL"]

    @property
    def warnings(self) -> list[CheckResult]:
        return [check for check in self.checks if check.estado == "WARN"]

    @property
    def ok(self) -> bool:
        return not self.fails

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "fails": len(self.fails),
            "warnings": len(self.warnings),
            "checks": [check.to_dict() for check in self.checks],
        }

    def imprimir(self) -> None:
        for check in self.checks:
            print(f"[{check.estado}] {check.regla}: {check.detalle}")
        estado = "OK" if self.ok else "FALLO"
        print(f"VALIDACION: {estado} ({len(self.fails)} FAIL, {len(self.warnings)} WARN)")


def _json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _source(audit: dict[str, Any], name: str) -> dict[str, Any] | None:
    wanted = name.casefold()
    for item in audit.get("fuentes", []) if isinstance(audit.get("fuentes"), list) else []:
        if str(item.get("fuente", "")).casefold() == wanted:
            return item
    return None


def _growth(current: list[float], base: list[float]) -> float:
    current_avg = sum(current) / len(current) if current else 0.0
    base_avg = sum(base) / len(base) if base else 0.0
    if base_avg <= 1:
        return 0.0
    return (current_avg - base_avg) / base_avg * 100.0


def regla_r1(audit: dict[str, Any]) -> CheckResult:
    source = _source(audit, "Wikipedia pageviews")
    if source is None:
        return CheckResult("R1", "FAIL", "no existe estado de Wikipedia pageviews")
    days = int(source.get("conteo", 0) or 0)
    articles = int(source.get("articles_unique", 0) or 0)
    if days < 25 or articles <= 3000:
        return CheckResult("R1", "FAIL", f"Wikipedia: {days} días y {articles} artículos únicos; se requieren >=25 y >3000")
    return CheckResult("R1", "PASS", f"Wikipedia: {days} días y {articles} artículos únicos")


def regla_r2(audit: dict[str, Any], report_text: str) -> CheckResult:
    errors = [
        item
        for item in audit.get("fuentes", [])
        if str(item.get("estado", "")).upper() == "ERROR"
    ]
    if not errors:
        return CheckResult("R2", "PASS", "no hay fuentes con ERROR")
    unexplained = [
        str(item.get("fuente", "desconocida"))
        for item in errors
        if not (
            str(item.get("fuente", "")).casefold() in report_text.casefold()
            and "ERROR" in report_text
        )
    ]
    if unexplained:
        return CheckResult("R2", "FAIL", f"errores no visibles en metodología: {', '.join(unexplained)}")
    names = ", ".join(str(item.get("fuente", "desconocida")) for item in errors)
    return CheckResult("R2", "WARN", f"fuentes con ERROR declaradas en el informe: {names}")


def regla_r3(audit: dict[str, Any]) -> CheckResult:
    bad: list[str] = []
    for key in ("top_trending", "top_growth"):
        ranking = audit.get(key)
        if not isinstance(ranking, list):
            return CheckResult("R3", "FAIL", f"falta ranking {key}")
        for niche in ranking:
            if int(niche.get("n_temas", 0) or 0) < 3:
                bad.append(f"{niche.get('nombre', '?')} ({niche.get('n_temas', 0)})")
    if bad:
        return CheckResult("R3", "FAIL", "nichos con menos de 3 temas: " + ", ".join(bad))
    return CheckResult("R3", "PASS", "todos los nichos top tienen al menos 3 temas")


def regla_r4(report_text: str) -> CheckResult:
    start = report_text.find("## Top 3 TRENDING")
    end = report_text.find("## Oportunidades YouTube", start if start >= 0 else 0)
    if start < 0 or end < 0:
        return CheckResult("R4", "FAIL", "no se localizaron las secciones de rankings")
    ranking_text = report_text[start:end]
    if "Sin clasificar" in ranking_text:
        return CheckResult("R4", "FAIL", "Sin clasificar aparece dentro de los rankings")
    return CheckResult("R4", "PASS", "Sin clasificar solo puede aparecer fuera de rankings")


def regla_r5(temas: list[dict[str, Any]]) -> CheckResult:
    checked = 0
    for theme in temas:
        current = theme.get("valores_actuales")
        base = theme.get("valores_base")
        if current is None and base is None:
            continue
        if not isinstance(current, list) or not isinstance(base, list):
            return CheckResult("R5", "FAIL", f"ventanas inválidas en {theme.get('titulo', '?')}")
        try:
            expected = _growth([float(value) for value in current], [float(value) for value in base])
            actual = float(theme.get("growth_pct"))
        except (TypeError, ValueError):
            return CheckResult("R5", "FAIL", f"growth inválido en {theme.get('titulo', '?')}")
        checked += 1
        if abs(expected - actual) > 0.1:
            return CheckResult(
                "R5",
                "FAIL",
                f"growth no recomputable en {theme.get('titulo', '?')}: esperado {expected:.3f}, guardado {actual:.3f}",
            )
    if not checked:
        return CheckResult("R5", "WARN", "no hay temas con ventanas diarias para recomputar")
    return CheckResult("R5", "PASS", f"growth recomputable en {checked} temas")


def regla_r6(audit: dict[str, Any], report_text: str) -> CheckResult:
    trending = {str(item.get("nombre")) for item in audit.get("top_trending", [])}
    growth = {str(item.get("nombre")) for item in audit.get("top_growth", [])}
    intersection = trending & growth
    marker = "Intersección de máxima prioridad:"
    if marker not in report_text:
        return CheckResult("R6", "FAIL", "falta la declaración de máxima prioridad")
    if not intersection:
        return CheckResult("R6", "WARN", "no hubo intersección trending/growth en esta corrida")
    section = report_text[report_text.find(marker) : report_text.find("\n", report_text.find(marker))]
    missing = [name for name in intersection if name not in section]
    if missing:
        return CheckResult("R6", "FAIL", f"intersección no destacada: {', '.join(missing)}")
    return CheckResult("R6", "PASS", "intersección trending/growth destacada")


def regla_r7(report_text: str) -> CheckResult:
    urls = re.findall(r"https?://[^)\s]+", report_text)
    if not urls:
        return CheckResult("R7", "FAIL", "no se encontraron enlaces auditables")
    bad: list[str] = []
    for url in urls:
        if any(character.isspace() or ord(character) > 127 for character in url):
            bad.append(url[:100])
    if bad:
        return CheckResult("R7", "FAIL", "URL sin encoding: " + ", ".join(bad))
    return CheckResult("R7", "PASS", f"{len(urls)} URLs sin espacios ni caracteres no codificados")


def regla_r8(report_path: Path, corrida: Path) -> CheckResult:
    required = [corrida / "auditoria.json", corrida / "temas_completos.json"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        return CheckResult("R8", "FAIL", "faltan artefactos: " + ", ".join(missing))
    values = [_json(path) for path in required]
    if any(value is None or value == {} or value == [] for value in values):
        return CheckResult("R8", "FAIL", "auditoria.json o temas_completos.json no es JSON válido/no vacío")
    if not report_path.exists() or not report_path.read_text(encoding="utf-8").strip():
        return CheckResult("R8", "FAIL", "el informe Markdown no existe o está vacío")
    return CheckResult("R8", "PASS", "Markdown y JSON de auditoría presentes y no vacíos")


def validar_corrida(report_path: str | Path, corrida: str | Path) -> ValidationResult:
    report = Path(report_path)
    run_dir = Path(corrida)
    report_text = report.read_text(encoding="utf-8") if report.exists() else ""
    audit_value = _json(run_dir / "auditoria.json")
    themes_value = _json(run_dir / "temas_completos.json")
    audit = audit_value if isinstance(audit_value, dict) else {}
    themes = themes_value if isinstance(themes_value, list) else []
    checks = [
        regla_r1(audit),
        regla_r2(audit, report_text),
        regla_r3(audit),
        regla_r4(report_text),
        regla_r5(themes),
        regla_r6(audit, report_text),
        regla_r7(report_text),
        regla_r8(report, run_dir),
    ]
    return ValidationResult(checks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida un informe y sus artefactos")
    parser.add_argument("--report", required=True, help="ruta al informe Markdown")
    parser.add_argument("--corrida", required=True, help="directorio con auditoria.json y temas_completos.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = validar_corrida(args.report, args.corrida)
    except OSError as exc:
        print(f"Error leyendo artefactos: {exc}", file=sys.stderr)
        return 2
    result.imprimir()
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
