# Trend Report

Implementación CLI del agente de tendencias descrito en el documento maestro de
la raíz.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

No se necesita una API key. Las dependencias son `requests` y `PyYAML`.

## Uso

```bash
python3 run_report.py
```

La ejecución interactiva ofrece:

| Opción | Ventana actual | Ventana base | Uso recomendado |
|---|---:|---:|---|
| `semana` | 7 días | 21 días | decidir qué publicar ahora |
| `mes` | 30 días | 90 días | revisar una línea editorial mensual |
| `anio` | 365 días | 365 días | planificar temas de largo plazo |

Para tareas programadas se debe pasar siempre `--period`:

```bash
python3 run_report.py --period semana
python3 run_report.py --period mes --geo MX
python3 run_report.py --period anio --sin-yt
```

Flags disponibles:

- `--geo MX`: cambia la geografía de RSS, Suggest y enlaces.
- `--gdelt`: agrega volumen de cobertura noticiosa; puede recibir 429.
- `--sin-yt`: omite la fase de Suggest/validación para una corrida más rápida.
- `--max-wiki-lookups N`: limita el fallback de resúmenes de Wikipedia; el
  valor configurado es 800.
- `--out ruta.md`: reemplaza la ruta de salida.
- `--verbose`: muestra warnings de infraestructura.

## Snapshot diario

El RSS de Google Trends solo representa el día de la consulta. Para acumularlo
sin claves API:

```bash
python3 -m src.snapshot --geo MX
```

El resultado se guarda en `data/snapshots/trends_MX.jsonl` y los estados en
`data/snapshots/estado_MX.jsonl`. La operación es idempotente por
`fecha + geo + titulo`; los XML de diagnóstico quedan en `data/snapshots/raw/`.

El workflow del repositorio raíz (`.github/workflows/snapshot_diario.yml`) lo
ejecutará diariamente después de publicar el proyecto. La señal no se mezcla
con el scoring hasta tener al menos siete días útiles.

## Validador automático

Cada corrida ejecuta el validador después de escribir el informe y los JSON:

```bash
python3 -m src.validar_informe \
  --report reports/informe_tendencias_2026-W35.md \
  --corrida data/raw/<corrida>
```

Las reglas R1–R8 revisan cobertura de Wikipedia, errores de fuentes, mínimo de
temas, `Sin clasificar`, growth recomputable, intersección de rankings, URLs y
artefactos. `WARN` permite continuar; `FAIL` produce código 1 y conserva los
datos para diagnóstico.

## Pipeline

1. Descarga RSS, pageviews de Wikipedia y Hacker News.
2. Forma el universo de títulos y elimina páginas navegacionales.
3. Clasifica por palabra completa; usa resúmenes de Wikipedia para temas fuertes
   que no coinciden en el título.
4. Ejecuta scoring inicial y elige candidatos.
5. Consulta semillas y títulos candidatos en YouTube, salvo `--sin-yt`.
6. Ejecuta scoring final y selecciona top 3/top 3.
7. Escribe Markdown, auditoría y los 400 temas más visibles.

## Taxonomía

Los 17 macronichos y sus palabras clave están en `config.yaml`. El primer
nicho que coincide en el título gana; por eso los nichos y keywords específicos
deben aparecer antes que los genéricos. El fallback de descripción compara la
evidencia encontrada por nicho para evitar que una mención incidental de un
videojuego clasifique una biografía como Gaming.

Para proponer un nicho nuevo no se debe añadir directamente al ranking. Primero
se recomienda observarlo como grupo experimental durante 8–12 semanas y exigir
volumen, precisión, búsquedas de YouTube y bajo solapamiento. La explicación y
los criterios están en la conversación de diseño y en
`.sdd/specs/agente-tendencias-mvp/design.md`.

## Diagnóstico

- **Wikipedia devuelve pocos días:** aumenta `sleep_segundos` y revisa 429/420.
- **La corrida tarda demasiado:** usa `--max-wiki-lookups 20` o `--sin-yt` para
  pruebas; la corrida completa prioriza cobertura.
- **RSS vacío:** prueba otra geografía con `--geo US`; México puede devolver
  pocos términos.
- **Suggest vacío:** comprueba que la respuesta usa `ds=yt`, `hl=es` y `gl=MX`.
- **GDELT recibe 429:** déjalo deshabilitado; es opcional.
- **Muchos temas sin clasificar:** revisa el anexo, añade keywords o aumenta el
  límite de summaries de forma gradual.

## Datos generados

`data/raw/<corrida>/` y `data/wiki_cache.json` son artefactos locales. No deben
publicarse por defecto; están ignorados en el `.gitignore` del proyecto.
