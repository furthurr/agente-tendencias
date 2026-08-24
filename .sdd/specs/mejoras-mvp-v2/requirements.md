# Requisitos — Mejoras MVP v2

**Fuente:** `MEJORAS_MVP.md` + `AGENTE_TENDENCIAS.md`  
**Alcance aprobado:** snapshot diario y validador automático.  
**Diferido:** integración del snapshot al scoring hasta contar con 7 días;
spike `trendspy` sin dependencia ni cambios en el núcleo.

## Objetivo y porqué

El RSS de Google Trends solo conserva la señal del día y la checklist del
informe es manual. El MVP v2 debe conservar diariamente el RSS y convertir la
checklist en un gate automático, sin claves API ni coste.

## Requisitos EARS

### V2-RF-01 — Snapshot diario

**CUANDO** se ejecute `python3 -m src.snapshot --geo MX`, **EL SISTEMA DEBERÁ**
descargar y parsear el RSS público de Google Trends y guardar una línea JSONL
por término en `data/snapshots/trends_MX.jsonl`.

### V2-RF-02 — Esquema del snapshot

**SIEMPRE** cada línea deberá contener `fecha`, `geo`, `titulo`,
`trafico_texto`, `trafico_num`, `titular`, `url_noticia`, `fuente_noticia` y
`capturado_utc`.

### V2-RF-03 — Idempotencia

**CUANDO** se repita la captura del mismo geo y fecha, **EL SISTEMA DEBERÁ**
evitar duplicar la clave `(fecha, geo, titulo)`.

### V2-RF-04 — Estado de fuente

**SI** el RSS está vacío o falla, **ENTONCES EL SISTEMA DEBERÁ** registrar
`vacio` o `error` en `data/snapshots/estado_<geo>.jsonl` y terminar sin error de
proceso para que Actions pueda diagnosticarlo.

### V2-RF-05 — Workflow

**CUANDO** se ejecute el workflow programado o manual, **EL SISTEMA DEBERÁ**
capturar MX, conservar el dataset en el repositorio y hacer commit solo si
hay cambios.

### V2-RF-06 — Validador R1–R8

**CUANDO** se ejecute `src/validar_informe.py`, **EL SISTEMA DEBERÁ** evaluar
las ocho reglas de `MEJORAS_MVP.md`, emitir `PASS`, `WARN` o `FAIL` y devolver
código 1 únicamente si existe al menos un `FAIL`.

### V2-RF-07 — Gate de corrida

**CUANDO** `run_report.py` termine de escribir el Markdown y sus JSON,
**EL SISTEMA DEBERÁ** ejecutar el validador, mostrar su resumen y conservarlo
en `auditoria.json`; si hay `FAIL`, la CLI deberá terminar con código 1 sin
borrar los artefactos.

### V2-RF-08 — No integración prematura

**MIENTRAS** el snapshot tenga menos de 7 días útiles, **EL SISTEMA NO DEBERÁ**
usar sus datos para modificar el scoring v1. El informe v1 seguirá funcionando
con RSS del día.

### V2-RF-09 — Dependencias y seguridad

**SIEMPRE** las mejoras deberán usar las dependencias existentes, fuentes
públicas, User-Agent, timeout, backoff y no incluir secretos.

## Fuera de alcance

- Agregar el snapshot al scoring antes de siete días.
- Ejecutar o integrar `trendspy`.
- Servicios alojados, API keys, dashboards o publicación automática del informe.
