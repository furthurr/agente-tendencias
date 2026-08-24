# Verificación — Mejoras MVP v2

**Fecha:** 2026-08-24  
**Resultado:** snapshot y validador implementados; integración del snapshot y
`trendspy` deliberadamente diferidos.

## Matriz

| Requisito | Evidencia | Estado |
|---|---|---|
| V2-RF-01 snapshot RSS | `trend-report/src/snapshot.py` + captura real temporal | ✅ |
| V2-RF-02 esquema JSONL | `tests/test_snapshot.py` + `data/snapshots` implementation | ✅ |
| V2-RF-03 idempotencia | test fake: segunda ejecución `nuevos=0`; captura real inmediata `nuevos=0` | ✅ |
| V2-RF-04 estados | `tests/test_snapshot.py::test_error_rss_se_registra_sin_romper_proceso` | ✅ |
| V2-RF-05 workflow | `.github/workflows/snapshot_diario.yml` | ✅ archivo; ⚠️ pendiente de ejecutar en GitHub |
| V2-RF-06 R1–R8 | `trend-report/src/validar_informe.py` + 8 mutaciones rotas | ✅ |
| V2-RF-07 gate | `trend-report/run_report.py` + auditoría real validada | ✅ |
| V2-RF-08 espera de 7 días | No existe `rss_snapshot.py` ni cambio de scoring | ✅ respetado |
| V2-RF-09 dependencias/seguridad | `requirements.txt` sin dependencias nuevas; grep sin secretos | ✅ |

## Pruebas locales

```text
python3 -m unittest discover -s tests -v
Ran 14 tests ... OK

python3 -m py_compile run_report.py src/*.py src/collectors/*.py tests/*.py
OK

python3 -m src.validar_informe \
  --report reports/informe_tendencias_2026-W35.md \
  --corrida data/raw/20260824T203201Z-semana
VALIDACION: OK (0 FAIL, 0 WARN)
```

La suite incluye una fixture buena y ocho mutaciones, una por cada regla R1–R8.

## Captura real

Comando ejecutado en un directorio temporal:

```text
python3 -m src.snapshot --geo MX --data-dir <temporal>
{"geo": "MX", "fecha": "2026-08-24", "estado": "ok", "nuevos": 10}
```

Una ejecución inmediata posterior no añadió duplicados (`nuevos=0`). Una
segunda consulta intermedia añadió un término nuevo porque el RSS cambió en el
mismo día; la tercera ejecución confirmó la deduplicación de la clave
`fecha+geo+titulo`.

## Corrida real con gate integrado

```text
python3 run_report.py --period semana --sin-yt --max-wiki-lookups 0
```

Evidencia:

```text
trend-report/data/raw/20260824T212739Z-semana/auditoria.json
```

Resultado: Wikipedia 28 días y 5.588 artículos únicos; 2.401 temas; R1–R8 en
`PASS`; `VALIDACION: OK (0 FAIL, 0 WARN)`; el bloque `validacion` quedó guardado
en `auditoria.json`.

## Pendiente deliberado

- El workflow no se ha ejecutado en GitHub porque el repositorio aún no está
  publicado; deben probarse tres `workflow_dispatch` cuando exista el remoto.
- El snapshot no se integra al scoring hasta acumular siete días útiles. La
  futura integración debe soportar semana, mes y año y declarar cobertura
  `N/días`.
- `trendspy` queda omitido: es un spike opcional que requiere cinco semillas,
  tres corridas estables, control 429/420 y verificación de licencia.
