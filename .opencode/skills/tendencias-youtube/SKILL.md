---
name: tendencias-youtube
description: Use when the user asks for YouTube trend reports, niche rankings, growth opportunities, or weekly/monthly/yearly trend analysis in Mexico or Spanish.
---

# Skill de tendencias YouTube

Esta skill opera el MVP local situado en `trend-report/`.

## Interacción

Si el usuario no indica horizonte, pregunta si quiere el reporte de la última
**semana**, **mes** o **año**. Normaliza `año` a `anio` para la CLI. No preguntes
por una API key: el MVP usa endpoints públicos.

## Ejecución

Desde la raíz del proyecto, ejecuta:

```bash
python3 trend-report/run_report.py --period semana
python3 trend-report/run_report.py --period mes
python3 trend-report/run_report.py --period anio
```

Usa solo una de las tres opciones. Añade `--geo` solo si se solicitó otra
geografía, `--sin-yt` si se pidió omitir YouTube y `--gdelt` si se pidió señal
noticiosa. Para una prueba rápida puedes añadir
`--max-wiki-lookups 20` y declararlo en la respuesta.

## Respuesta

Después de la ejecución, lee el informe generado y comunica:

- período, rango actual y rango base;
- top 3 trending y top 3 crecimiento;
- intersección de máxima prioridad;
- sugerencias YouTube disponibles;
- cualquier fuente con `ERROR` u `OMITIDA`;
- rutas del informe y de `auditoria.json`.
- resultado del gate automático R1–R8, incluidos los `WARN` o `FAIL`.

No sustituyas la evidencia del informe por estimaciones propias. Si no hay
datos suficientes, explica la limitación y conserva los temas en el anexo.
