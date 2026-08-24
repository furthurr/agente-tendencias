#!/usr/bin/env python3
"""Orquestador CLI del informe de tendencias.

Uso rápido:
    python3 run_report.py
    python3 run_report.py --period semana --sin-yt
    python3 run_report.py --period mes --geo MX
    python3 run_report.py --period anio --gdelt
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - mensaje de instalación
    raise SystemExit("Falta PyYAML. Ejecuta: pip install -r requirements.txt") from exc

from src.classify import cargar_cache, clasificar_temas, guardar_cache, invalidar_nones
from src.collectors import source_status
from src.collectors.gdelt import recoger as recoger_gdelt
from src.collectors.hackernews import recoger as recoger_hackernews
from src.collectors.rss_mx import recoger as recoger_rss
from src.collectors.wikipedia import recoger_pageviews, recoger_resumen
from src.collectors.yt_suggest import recoger_por_nicho, validar_temas
from src.http import HttpClient
from src.report_md import generar_informe
from src.scoring import (
    calcular_scores,
    construir_universo,
    rankear_nichos,
    seleccionar_top_nichos,
)
from src.validar_informe import ValidationResult, validar_corrida


LOGGER = logging.getLogger("trend_report")
ROOT = Path(__file__).resolve().parent
VALID_PERIODS = ("semana", "mes", "anio")


class ValidacionInformeError(RuntimeError):
    """El informe quedó escrito, pero el gate detectó uno o más FAIL."""

    def __init__(self, result: ValidationResult):
        super().__init__(f"validación fallida: {len(result.fails)} FAIL")
        self.result = result


def cargar_config() -> dict[str, Any]:
    with (ROOT / "config.yaml").open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml no contiene un objeto YAML válido")
    return data


def seleccionar_periodo(requested: str | None) -> str:
    if requested is not None:
        if requested not in VALID_PERIODS:
            raise ValueError(f"Período inválido: {requested}. Usa: {', '.join(VALID_PERIODS)}")
        return requested
    if not sys.stdin.isatty():
        raise ValueError("No hay terminal interactiva; usa --period semana|mes|anio")

    print("¿Qué informe quieres generar?")
    print("  1) Semana — últimos 7 días")
    print("  2) Mes    — últimos 30 días")
    print("  3) Año    — últimos 365 días")
    answer = input("Selecciona 1, 2, 3 o escribe semana/mes/anio [1]: ").strip().lower()
    choices = {"": "semana", "1": "semana", "2": "mes", "3": "anio"}
    period = choices.get(answer, answer)
    if period not in VALID_PERIODS:
        raise ValueError("Selección inválida. Usa 1, 2, 3, semana, mes o anio.")
    return period


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera informes de tendencias para YouTube")
    parser.add_argument("--period", choices=VALID_PERIODS, help="semana, mes o anio; sin valor pregunta interactivamente")
    parser.add_argument("--geo", default=None, help="geografía ISO, por defecto MX")
    parser.add_argument("--gdelt", action="store_true", help="añade volumen noticioso GDELT (lento y opcional)")
    parser.add_argument("--sin-yt", action="store_true", help="omite sugerencias y validación de YouTube")
    parser.add_argument(
        "--max-wiki-lookups",
        type=int,
        default=None,
        help="limita resúmenes de Wikipedia; por defecto usa el máximo de config (útil para pruebas)",
    )
    parser.add_argument("--out", help="ruta personalizada para el Markdown final")
    parser.add_argument("--verbose", action="store_true", help="activa logs de infraestructura")
    return parser.parse_args()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _default_report_path(period: str) -> Path:
    today = date.today()
    if period == "semana":
        iso = today.isocalendar()
        name = f"informe_tendencias_{iso.year}-W{iso.week:02d}.md"
    elif period == "mes":
        name = f"informe_tendencias_{today.year}-{today.month:02d}.md"
    else:
        name = f"informe_tendencias_{today.year}.md"
    return ROOT / "reports" / name


def _config_niches(config: dict[str, Any], names: set[str]) -> list[dict[str, Any]]:
    return [item for item in config.get("nichos", []) if item.get("nombre") in names]


def ejecutar(args: argparse.Namespace) -> Path:
    config = cargar_config()
    period = seleccionar_periodo(args.period)
    if args.max_wiki_lookups is not None and args.max_wiki_lookups < 0:
        raise ValueError("--max-wiki-lookups debe ser mayor o igual que cero")
    period_config = config["periodos"][period]
    geo = (args.geo or config.get("proyecto", {}).get("geo_default", "MX")).upper()
    generated_at = datetime.now(timezone.utc).isoformat()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{period}"
    raw_dir = ROOT / "data" / "raw" / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)

    http_config = config.get("http", {})
    project_config = config.get("proyecto", {})
    client = HttpClient(
        user_agent=str(project_config.get("user_agent", "AgenteTendencias/0.1")),
        timeout=float(http_config.get("timeout", 25)),
        retries=int(http_config.get("retries", 2)),
        backoff_initial=float(http_config.get("backoff_inicial", 1.0)),
    )
    statuses: list[dict[str, Any]] = []

    rss_items, rss_status = recoger_rss(client, geo, raw_dir)
    statuses.append(rss_status)

    wiki_config = config.get("fuentes", {}).get("wikipedia", {})
    wiki_data, wiki_status = recoger_pageviews(
        client,
        int(period_config["dias_actual"]),
        int(period_config["dias_base"]),
        raw_dir,
        sleep_seconds=float(wiki_config.get("sleep_segundos", 0.35)),
        stop_failures=int(wiki_config.get("stop_fallos_consecutivos", 6)),
    )
    statuses.append(wiki_status)

    hn_config = config.get("fuentes", {}).get("hackernews", {})
    hn_items, hn_status = recoger_hackernews(
        client,
        int(period_config["dias_actual"]),
        raw_dir,
        points_min=int(hn_config.get("points_minimos", 50)),
    )
    statuses.append(hn_status)

    temas, current_dates, base_dates = construir_universo(
        wiki_data,
        rss_items,
        hn_items,
        period,
        int(period_config["dias_actual"]),
        int(period_config["dias_base"]),
    )

    cache_path = ROOT / "data" / "wiki_cache.json"
    cache = cargar_cache(cache_path)
    purged_nones = invalidar_nones(cache)
    summary_errors = 0

    def summary_loader(title: str) -> dict[str, str]:
        nonlocal summary_errors
        try:
            return recoger_resumen(client, title, raw_dir)
        except Exception as exc:  # el tema permanece auditable como no clasificado
            summary_errors += 1
            LOGGER.warning("Resumen Wikipedia no disponible para %s: %s", title, exc)
            raise
        finally:
            # Wikipedia puede truncar silenciosamente el historial cuando los
            # resúmenes se consultan en ráfaga.
            time.sleep(float(wiki_config.get("sleep_segundos", 0.35)))

    classification_stats = clasificar_temas(
        temas,
        list(config.get("nichos", [])),
        cache,
        summary_loader=summary_loader,
        max_lookup=(
            int(args.max_wiki_lookups)
            if args.max_wiki_lookups is not None
            else int(wiki_config.get("max_lookup", 800))
        ),
    )
    guardar_cache(cache_path, cache)
    statuses.append(
        source_status(
            "Wikipedia summaries",
            "OK" if summary_errors == 0 else "ERROR",
            classification_stats["lookups"],
            f"cache hits={classification_stats['cache_hits']}; purgados None={purged_nones}; errores={summary_errors}",
        )
    )

    scoring_config = config.get("scoring", {})
    calcular_scores(temas, scoring_config)
    rankings_pass1 = rankear_nichos(temas, scoring_config)
    top_pass1 = seleccionar_top_nichos(rankings_pass1, int(scoring_config.get("top_nichos", 3)), "score_final")
    top_trending_pass1 = seleccionar_top_nichos(rankings_pass1, int(scoring_config.get("top_nichos", 3)), "trending_score")
    top_growth_pass1 = seleccionar_top_nichos(rankings_pass1, int(scoring_config.get("top_nichos", 3)), "growth_score")
    candidate_names = {item["nombre"] for item in top_trending_pass1 + top_growth_pass1}

    yt_suggestions: dict[str, list[str]] = {}
    if args.sin_yt:
        statuses.append(source_status("YouTube", "OMITIDA", 0, "--sin-yt"))
    else:
        candidate_configs = _config_niches(config, candidate_names)
        yt_config = config.get("fuentes", {}).get("youtube", {})
        yt_suggestions, yt_seed_status = recoger_por_nicho(
            client,
            candidate_configs,
            geo,
            raw_dir,
            max_per_seed=int(yt_config.get("max_sugerencias_por_semilla", 8)),
            sleep_seconds=float(yt_config.get("sleep_segundos", 0.38)),
        )
        statuses.append(yt_seed_status)
        candidate_themes = [
            theme
            for theme in sorted(temas, key=lambda item: item.get("score_final", 0), reverse=True)
            if theme.get("nicho") in candidate_names
        ][: max(10, len(candidate_names) * 10)]
        yt_matches, yt_validation_status = validar_temas(
            client,
            candidate_themes,
            geo,
            raw_dir,
            max_sugerencias=10,
            sleep_seconds=float(yt_config.get("sleep_segundos", 0.38)),
        )
        for theme in temas:
            match = yt_matches.get(theme.get("titulo"))
            if match:
                theme.update(match)
        statuses.append(yt_validation_status)

    calcular_scores(temas, scoring_config)
    rankings = rankear_nichos(temas, scoring_config)
    top_trending = seleccionar_top_nichos(rankings, int(scoring_config.get("top_nichos", 3)), "trending_score")
    top_growth = seleccionar_top_nichos(rankings, int(scoring_config.get("top_nichos", 3)), "growth_score")

    if args.gdelt:
        gdelt_queries = [item["nombre"] for item in top_trending + top_growth]
        gdelt_data, gdelt_status = recoger_gdelt(
            client,
            sorted(set(gdelt_queries)),
            int(period_config["dias_actual"]),
            int(period_config["dias_base"]),
            raw_dir,
            sleep_seconds=float(config.get("fuentes", {}).get("gdelt", {}).get("sleep_segundos", 2.0)),
        )
        _write_json(raw_dir / "gdelt_resumen.json", gdelt_data)
        statuses.append(gdelt_status)

    period_label = str(period_config.get("etiqueta", period.title()))
    context = {
        "period": period,
        "period_label": period_label,
        "days_current": int(period_config["dias_actual"]),
        "days_base": int(period_config["dias_base"]),
        "geo": geo,
        "generated_at": generated_at,
        "current_dates": current_dates,
        "base_dates": base_dates,
        "temas": temas,
        "top_trending": top_trending,
        "top_growth": top_growth,
        "yt_suggestions": yt_suggestions,
        "source_statuses": statuses,
        "raw_dir": str(raw_dir.relative_to(ROOT)),
    }
    report = generar_informe(context)
    report_path = Path(args.out).expanduser() if args.out else _default_report_path(period)
    if not report_path.is_absolute():
        report_path = Path.cwd() / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    audit_payload = {
        "run_id": run_id,
        "period": period,
        "period_label": period_label,
        "geo": geo,
        "generated_at": generated_at,
        "ventanas": {"actual": current_dates, "base": base_dates},
        "fuentes": statuses,
        "clasificacion": classification_stats,
        "temas": {"total": len(temas), "clasificados": len([t for t in temas if t.get("nicho") != "Sin clasificar"])},
        "top_trending": top_trending,
        "top_growth": top_growth,
        "opciones": {
            "gdelt": bool(args.gdelt),
            "sin_yt": bool(args.sin_yt),
            "max_wiki_lookups": args.max_wiki_lookups,
        },
    }
    _write_json(raw_dir / "auditoria.json", audit_payload)
    _write_json(
        raw_dir / "temas_completos.json",
        sorted(temas, key=lambda item: item.get("vistas_periodo", 0), reverse=True)[:400],
    )

    validation = validar_corrida(report_path, raw_dir)
    audit_payload["validacion"] = validation.to_dict()
    _write_json(raw_dir / "auditoria.json", audit_payload)

    print(f"\nInforme generado: {report_path}")
    print(f"Auditoría: {raw_dir / 'auditoria.json'}")
    print(f"Temas: {len(temas)}; nichos rankeados: {len(rankings)}")
    for status in statuses:
        print(f"- {status['fuente']}: {status['estado']} ({status.get('conteo', 0)}) — {status.get('detalle', '')}")
    validation.imprimir()
    if not validation.ok:
        raise ValidacionInformeError(validation)
    return report_path


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    try:
        ejecutar(args)
    except ValidacionInformeError as exc:
        # Los artefactos quedan disponibles para diagnóstico y corrección.
        return exc.result.exit_code
    except (ValueError, OSError, KeyboardInterrupt) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
