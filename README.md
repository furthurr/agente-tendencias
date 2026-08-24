# Agente de Tendencias para YouTube

MVP de un agente que genera informes de oportunidades de contenido para
YouTube en México/español usando fuentes públicas y sin claves API.

## Qué hace

- Compara **semana**, **mes** o **año** hacia atrás.
- Calcula los 3 nichos más `TRENDING` y los 3 con mayor `CRECIMIENTO`.
- Muestra los 5 temas principales de cada nicho.
- Consulta sugerencias reales del autocompletado de YouTube.
- Incluye enlaces a Wikipedia, Google Trends y búsquedas de YouTube.
- Guarda metodología, estados de fuentes, datos crudos y auditoría JSON.
- Mantiene una taxonomía inicial de 17 macronichos, ampliable mediante
  `trend-report/config.yaml`.
- Captura diariamente el RSS de Google Trends con GitHub Actions para construir
  histórico propio; la integración al scoring espera siete días acumulados.
- Valida automáticamente la estructura del informe con ocho reglas antes de
  considerar correcta una corrida.

El documento maestro de alcance y metodología es
[`AGENTE_TENDENCIAS.md`](AGENTE_TENDENCIAS.md). La especificación trazable del
MVP está en [`.sdd/specs/agente-tendencias-mvp/`](.sdd/specs/agente-tendencias-mvp/).
Las mejoras posteriores (snapshot diario, validador automático y spike de otra
señal) están descritas, pero no implementadas, en
[`MEJORAS_MVP.md`](MEJORAS_MVP.md).

## Inicio rápido

Requiere Python 3.10 o superior.

```bash
cd trend-report
python3 -m venv .venv
source .venv/bin/activate       # macOS/Linux
python -m pip install -r requirements.txt
python run_report.py
```

Sin `--period`, la CLI pregunta:

1. Semana: 7 días actuales vs 21 días base.
2. Mes: 30 días actuales vs 90 días base.
3. Año: 365 días actuales vs 365 días base.

Para automatización o scripts:

```bash
python run_report.py --period semana
python run_report.py --period mes
python run_report.py --period anio
```

Opciones:

```bash
python run_report.py --period semana --geo MX
python run_report.py --period semana --sin-yt
python run_report.py --period semana --gdelt
python run_report.py --period semana --max-wiki-lookups 20
python run_report.py --period semana --out reports/prueba.md
```

`--max-wiki-lookups` mantiene 800 como máximo configurado por defecto, pero
permite una prueba rápida o controlar el tiempo/rate limit de Wikipedia.

## Snapshot diario y validación

La captura diaria se puede probar localmente desde `trend-report/`:

```bash
python3 -m src.snapshot --geo MX
```

Escribe el dataset idempotente en `trend-report/data/snapshots/`. El workflow
`.github/workflows/snapshot_diario.yml` lo ejecuta diariamente cuando el
repositorio esté publicado y hace commit solo si aparecen términos nuevos.

El validador se ejecuta automáticamente al final de `run_report.py`. También se
puede lanzar de forma independiente:

```bash
python3 -m src.validar_informe \
  --report reports/informe_tendencias_2026-W35.md \
  --corrida data/raw/20260824T203201Z-semana
```

Un `FAIL` devuelve código de salida 1, conserva los artefactos y explica qué
regla se incumplió. El snapshot todavía no modifica los scores: primero debe
acumular al menos siete días útiles.

## Usarlo como agente de opencode

El proyecto incluye:

- `.opencode/agent/tendencias.md`: agente conversacional.
- `.opencode/skills/tendencias-youtube/SKILL.md`: skill reutilizable.
- `.opencode/command/tendencias.md`: comando `/tendencias`.

Desde opencode se puede seleccionar el agente `tendencias` o ejecutar
`/tendencias`. Si no se ha indicado un período, el agente pregunta si se desea
`semana`, `mes` o `anio`, ejecuta la CLI y devuelve la ruta del informe.

Después de crear o modificar archivos de configuración de opencode, reinicia
opencode para que los detecte.

## Salidas

El informe se escribe en:

```text
trend-report/reports/informe_tendencias_AAAA-WSS.md
trend-report/reports/informe_tendencias_AAAA-MM.md
trend-report/reports/informe_tendencias_AAAA.md
```

Cada corrida guarda auditoría y datos completos en:

```text
trend-report/data/raw/<corrida>/auditoria.json
trend-report/data/raw/<corrida>/temas_completos.json
```

El historial descargado y los informes generados están excluidos del control de
versiones por `.gitignore`; esto evita publicar datos generados accidentalmente.

## Arquitectura

```text
trend-report/
├── run_report.py             # composition root y CLI
├── config.yaml               # períodos, fuentes, scoring y taxonomía
├── src/
│   ├── http.py               # User-Agent, timeout, retries y backoff
│   ├── classify.py           # normalización, matching y caché Wiki
│   ├── scoring.py            # universo, ventanas y rankings
│   ├── report_md.py          # informe Markdown
│   └── collectors/           # RSS, Wikipedia, YouTube, HN y GDELT
├── tests/test_core.py        # pruebas sin red
├── data/                     # caché y crudos generados
└── reports/                  # informes generados
```

## Pruebas

Desde `trend-report/`:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile run_report.py src/*.py src/collectors/*.py tests/*.py
```

Smoke test rápido contra las fuentes públicas:

```bash
python3 run_report.py --period semana --sin-yt --max-wiki-lookups 20
```

Una corrida completa puede tardar varios minutos. La corrida anual descarga un
historial mucho mayor y puede ser considerablemente más lenta.

## Fuentes y limitaciones

- Google Trends RSS aporta principalmente la señal del día de ejecución.
- Wikipedia pageviews es la columna vertebral histórica y suele tener unos dos
  días de retraso.
- YouTube Suggest no requiere API key, pero puede devolver vacío o aplicar
  límites.
- Hacker News refuerza tecnología; GDELT es opcional y lento.
- `Sin clasificar` aparece en el anexo, pero no compite en rankings.
- La detección automática de nuevos macronichos está fuera del MVP; primero se
  deben observar grupos emergentes durante varias semanas.

## Publicación posterior

El proyecto está preparado para un repositorio público: no contiene secretos,
los outputs están ignorados y la licencia es MIT. Todavía no se ha inicializado
ni publicado el repositorio Git. Antes de publicar conviene revisar la
taxonomía, ejecutar las pruebas y decidir el nombre/URL final del repositorio.
