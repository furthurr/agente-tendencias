# Verificación — Agente de informes de tendencias YouTube (MVP)

**Fecha de verificación:** 2026-08-24  
**Modo:** standard / Quick Plan  
**Resultado:** MVP funcional con una limitación operativa documentada para el
fallback completo de Wikipedia.

## Matriz de requisitos

| Requisito | Evidencia | Estado |
|---|---|---|
| RF-01 selector interactivo | `trend-report/run_report.py::seleccionar_periodo` | ✅ |
| RF-02 selector CLI | `trend-report/run_report.py` + `--help` | ✅ |
| RF-03 período inválido | `argparse choices` + comando de validación | ✅ |
| RF-04 ventanas semana/mes/año | `trend-report/config.yaml` (`periodos`) + `tests/test_core.py` | ✅ |
| RF-05 fuentes públicas | `src/collectors/{rss_mx,wikipedia,hackernews}.py` + corrida real | ✅ |
| RF-06 GDELT/YouTube opcionales | `src/collectors/{gdelt,yt_suggest}.py` + flags CLI | ✅ |
| RF-07 clasificación segura | `src/classify.py` + pruebas de límites/fallback | ✅ |
| RF-08 17 macronichos | `trend-report/config.yaml` (`len(nichos)=17`) | ✅ |
| RF-09 caché purgable | `src/classify.py` + auditoría `purgados None=1` | ✅ |
| RF-10 scoring | `src/scoring.py` + pruebas de ventanas/growth/ranking | ✅ |
| RF-11 informe Markdown | `src/report_md.py` + `reports/informe_tendencias_2026-W35.md` | ✅ |
| RF-12 auditoría JSON | `data/raw/20260824T203201Z-semana/auditoria.json` y `temas_completos.json` | ✅ |
| RF-13 errores/backoff | `src/http.py`, test HTTP 404 y estados de fuentes | ✅ |
| RF-14 reproducibilidad/privacidad | `README.md`, `.gitignore`, informe y auditoría | ✅ |

## Evidencia de comandos

### Pruebas locales

```text
python3 -m unittest discover -s tests -v
Ran 10 tests ... OK

python3 -m py_compile run_report.py src/*.py src/collectors/*.py tests/*.py
OK

python3 -c "...yaml..."
17 ['anio', 'mes', 'semana']
```

Las pruebas cubren normalización, límites de palabra, clasificación de
profesiones, purga de `None`, ventanas, growth por promedios, mínimo de tres
temas, encoding de enlaces y un HTTP no exitoso.

### Corrida real acotada sin YouTube

```text
python3 run_report.py --period semana --sin-yt --max-wiki-lookups 20
```

Evidencia:

```text
trend-report/reports/informe_tendencias_2026-W35.md
trend-report/data/raw/20260824T202829Z-semana/auditoria.json
```

Resultado observado: Wikipedia entregó 27 días y 5.499 artículos únicos; RSS
10 registros; Hacker News 60 historias; 2.399 temas; 12 nichos rankeados; el
informe incluyó top trending, top growth, anexos y estados de fuentes.

### Corrida real con YouTube

```text
python3 run_report.py --period semana --max-wiki-lookups 0
```

Evidencia:

```text
trend-report/data/raw/20260824T203201Z-semana/auditoria.json
```

Resultado observado: `YouTube Suggest: OK (24)` y
`YouTube validación: OK (30)`, con 0 errores en 9 consultas de semillas y 30
títulos.

### Límite operativo conocido

También se intentó una corrida completa:

```text
python3 run_report.py --period semana --sin-yt
```

En este entorno superó 300 segundos por el límite de 800 resúmenes de
Wikipedia, respuestas 404 y rate limiting. La orden fue terminada por timeout;
no se cuenta como evidencia de éxito. El MVP expone `--max-wiki-lookups N` para
controlar esta operación. La configuración conserva 800 como máximo
metodológico, tal como establece el documento maestro.

GDELT no se ejecutó en la verificación porque es opcional y su rate limit es
agresivo; el adaptador y el flag existen en disco.

## Spot-check del quality bar

- ✅ **Capas:** `classify.py`/`scoring.py` no importan UI ni escriben
  persistencia.
- ✅ **Composition root/DI:** `run_report.py` crea y pasa el `HttpClient` y los
  colectores; no hay singleton de infraestructura.
- ✅ **Errores:** `HttpError`, retries/backoff y tabla de estados; existe test de
  HTTP 404.
- ✅ **Persistencia encapsulada:** JSON de crudos/caché se escribe desde
  adaptadores y orquestador, no desde el dominio de scoring.
- ✅ **Lógica pura:** 10 pruebas estándar sin red.
- ✅ **RNF críticos:** matcher completo, purga de `None`, exclusión de `Sin
  clasificar`, mínimo de tres temas, estados de YouTube y enlaces encodeados.

## Integridad de tareas

Todas las tareas T1–T16 de `tasks.md` tienen un artefacto o comando de
verificación. T17 se completa con este archivo y su matriz. No se añadió
dependencia de PBT: no había una invariante algebraica que justificara una
dependencia adicional en el MVP.

## Huecos para la siguiente iteración

1. Añadir cacheo/planificación de pageviews para evitar redescargar todos los
   días en cada corrida.
2. Medir 8–12 semanas antes de promocionar nuevos macronichos.
3. Ejecutar una corrida GDELT controlada y documentar su estabilidad.
4. Decidir el nombre y URL del repositorio público antes de publicar.
