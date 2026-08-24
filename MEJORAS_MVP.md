# SPEC — Mejoras al MVP v2 (informes semanales de tendencias, YouTube MX)

> Documento incremental que **extiende** (no modifica) `AGENTE_TENDENCIAS.md`,
> la especificación maestra del sistema `trend-report/` construido y probado el
> **2026-08-24**. Todo lo aquí indicado se definió tras una investigación web
> ese mismo día sobre skills, agentes y repos existentes.
>
> **Veredicto de la investigación**: NO existe ninguna skill o agente publicado
> que replique el sistema completo (informe semanal MD, contenido YouTube,
> MX/español, fuentes públicas sin clave API, ranking dual trending/growth por
> nichos con taxonomía y auditoría). Solo existen piezas parciales. Este
> documento selecciona las 3 mejoras con valor real y especifica su
> construcción. Presupuesto total: **$0**.

> **Estado de implementación local (2026-08-24):** snapshot y validador R1–R8
> implementados y probados en `trend-report/`. La ejecución real del workflow
> queda pendiente de publicar el repositorio; la integración del snapshot al
> scoring espera siete días acumulados; `trendspy` sigue diferido como spike.

---

## 0. Contexto, alcance y restricciones heredadas

### 0.1 Relación con el documento maestro

| Documento | Rol |
|---|---|
| `AGENTE_TENDENCIAS.md` | Especificación maestra v1: arquitectura, pipeline, endpoints verificados, scoring, formato del informe, bugs conocidos. **No se modifica.** |
| `MEJORAS_MVP.md` (este archivo) | Mejoras incrementales v2 sobre esa base: snapshot diario, validador automático, spike opcional de señal extra. |

Cualquier IA que ejecute este documento debe leer también el maestro: las
secciones del maestro se citan como «§N del maestro».

### 0.2 Restricciones duras heredadas (no negociables)

1. Solo fuentes públicas **sin clave API** (esto descarta MCPs alojados y la
   YouTube Data API oficial).
2. Geografía **México/español** (parametrizable como en el maestro, `--geo`).
3. Propósito: **creación de contenido en YouTube**.
4. Presupuesto: **$0** — sin servicios de pago ni freemium obligatorio.
5. Toda fuente nueva usa las convenciones del maestro §4/http: User-Agent
   propio, backoff/reintentos, timeout, guardado de crudos auditables.

### 0.3 Resumen de la investigación (2026-08-24)

Se revisaron: marketplaces de skills (awesome-claude-skills 73k⭐ y derivados),
registros de servidores MCP (Smithery/Glama/mcprepository), búsqueda de repos
GitHub (topics google-trends/youtube, keyword-research, trend-report agents) y
proyectos individuales. Resultado:

- **Skills de agente similares pero en otro dominio**: `ai-trend-radar-report`
  (diarios/semanales de industria IA en chino) y `ultraresearch` (harness de
  investigación multi-fuente X/Reddit/HN/arXiv). Ninguna genera informes
  semanales estructurados por nichos para creadores.
- **Servidores MCP de tendencias**: acceso a datos vía servicio alojado con
  clave (freemium). Violan la restricción 1 y tampoco generan informes.
- **Librerías/bloques sueltos**: alternativas mantenidas a pytrends
  (`trendspy`, MIT), scrapers simples de Google Suggest, datasets diarios de
  pageviews de Wikipedia. Útiles solo como inspiración o pieza puntual.

Las 3 mejoras adoptadas y su origen:

| # | Mejora | Inspiración | Valor para el MVP |
|---|---|---|---|
| 1 | Snapshot diario de Google Trends RSS con GitHub Actions | [`vtasca/wikipedia-pageviews`](https://github.com/vtasca/wikipedia-pageviews) (patrón de polling diario + dataset commiteado) | Elimina la limitación clave §4.1 del maestro: el RSS solo cubre el día de corrida |
| 2 | Validador automático del informe | Patrón `validate_report.py` de [`lgy1027/ai-trend-radar-report`](https://github.com/lgy1027/ai-trend-radar-report) | Convierte la checklist manual §13 del maestro en un gate del pipeline |
| 3 | Spike evaluación de `trendspy` | [`sdil87/trendspy`](https://github.com/sdil87/trendspy) (MIT, ⭐116) / fork mantenido [`flack0x/trendspyg`](https://github.com/flack0x/trendspyg) (⭐43) | Posible señal semanal real por keyword (hoy se depende 100 % de Wikipedia como columna vertebral) |

---

## 1. Mejora 1 — Snapshot diario de Google Trends RSS (GitHub Actions)

### 1.1 Problema que resuelve

El maestro §4.1 lo documenta: el RSS `trends.google.com/trending/rss?geo=MX`
devuelve ~10 términos **solo del día de la corrida**; la ventana semanal se
reconstruye indirectamente con Wikipedia/HN. Además el maestro §14 ya prevé
«Snapshot diario programado (cron) para Trends acumulado semanal real».
Esta mejora lo implementa con infraestructura gratuita.

**Asimetría importante (documentar siempre)**: solo Trends necesita snapshot.
La API de pageviews de Wikimedia conserva el histórico consultable
(retraso ~2 días, ver maestro §4.2), así que **no** se snapshottea Wikipedia;
el RSS es efímero y por eso sí se captura cada día.

### 1.2 Referencia y licencia

El repo `vtasca/wikipedia-pageviews` implementa exactamente este patrón
(workflow de GitHub Actions que consulta una API pública cada día y commitea
un dataset acumulado). **Ese repo no tiene licencia** → NO copiar su código;
usarlo solo como referencia conceptual del patrón. El código propio se escribe
desde cero siguiendo las convenciones del maestro.

### 1.3 Qué construir

```
trend-report/
├── .github/workflows/snapshot_diario.yml   # workflow programado
└── src/
    └── snapshot.py                         # colector append-only
```

#### 1.3.1 `src/snapshot.py`

Comportamiento:

1. Descarga `GET https://trends.google.com/trending/rss?geo={GEO}` (por
   defecto `--geo MX`) usando la sesión HTTP del maestro (UA propio, timeout
   25 s, reintentos=2).
2. Parsea el XML (namespace `ht="https://trends.google.com/trending/rss"`),
   extrayendo por `<item>`: `title`, `ht:approx_traffic` (limpiar no-dígitos →
   entero, igual que hace el maestro), `pubDate` y los `ht:news_item`
   (`ht:news_item_title/url/source`).
3. Fecha de negocio en **America/Mexico_City** (formato ISO `AAAA-MM-DD`);
   registrar también el instante UTC de captura.
4. **Append-only** a `data/snapshots/trends_{geo}.jsonl`: una línea JSON por
   término/día. Clave de deduplicación `(fecha, geo, titulo)` — si la línea ya
   existe, no se duplica (idempotente: relanzar el mismo día es seguro).

Esquema de línea JSONL:

```json
{
  "fecha": "2026-08-24",
  "geo": "MX",
  "titulo": "querétaro",
  "trafico_texto": "2,000+",
  "trafico_num": 2000,
  "titular": "...",
  "url_noticia": "https://...",
  "fuente_noticia": "Milenio",
  "capturado_utc": "2026-08-24T13:05:11Z"
}
```

Notas de diseño:
- El dataset vive versionado en el propio repo (auditable con `git log`,
  cero costo de storage).
- Si el RSS viene vacío o falla: escribir entrada de estado en
  `data/snapshots/estado_{geo}.jsonl` (`{fecha, estado: "vacio"|"error", detalle}`)
  y salir con código 0 salvo error duro (el workflow no debe fallar ruidoso;
  el diagnóstico va en el dataset mismo).
- Compacción mensual opcional (nunca borrar crudos; solo opcional si crece).

#### 1.3.2 `.github/workflows/snapshot_diario.yml`

```yaml
name: snapshot-diario
on:
  schedule:
    - cron: "30 12 * * *"     # 12:30 UTC ≈ 06:30 CDMX, temprano del día
  workflow_dispatch:           # lanzamiento manual para pruebas
jobs:
  snapshot:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install requests pyyaml
      - run: python3 src/snapshot.py --geo MX
      - name: commit dataset
        run: |
          git config user.name "trends-bot"
          git config user.email "bot@users.noreply.github.com"
          git add data/snapshots/
          git diff --cached --quiet && echo "sin cambios" || {
            git commit -m "snapshot trends $(date -u +%F)"
            git push
          }
```

Requisitos operativos:
- Debe funcionar igual en local (`python3 src/snapshot.py`) y en Actions.
- Costo: público = minutos ilimitados; privado ≈ 30 min/mes contra 2,000
  gratis. En ambos casos **$0**.

### 1.4 Integración al pipeline (FASE SEPARADA — solo con ≥7 días acumulados)

⚠️ No integrar el día uno. Primero acumular datos (ver orden §6).

1. Nuevo colector `src/collectors/rss_snapshot.py` que lee
   `data/snapshots/trends_{geo}.jsonl` y agrega por título normalizado
   (normalización del maestro §6.1):
   `rss_trafico_semana = sum(trafico_num de últimos 7 días con datos)`.
2. En `rss_mx.py`/scoring: usar la señal agregada del snapshot cuando exista;
   **fallback graceful** al RSS del día si el snapshot está vacío/ausente
   (el sistema v1 debe seguir funcionando sin cambios).
3. Metodología del informe (maestro §8): declarar cobertura real
   «Snapshot Trends: N/7 días» y la fecha más antigua disponible.
4. `auditoria.json` gana `"snapshot_trends": {"dias": N, "geo": "MX",
   "ultima_fecha": ...}`.

### 1.5 Caveat operativo conocido

GitHub **desactiva workflows programados tras 60 días de inactividad del
repo**. Mitigación natural: la corrida semanal del informe commitea cambios
(los reports y crudos), lo que mantiene el repo activo. Aun así, el validador
(§2) debe avisar si la cobertura del snapshot cae por debajo de 7 días.

### 1.6 Criterios de aceptación

- [ ] 3 ejecuciones simuladas (`workflow_dispatch`) consecutivas verdes.
- [x] Relanzar el mismo día NO duplica líneas (dedup funciona).
- [x] RSS vacío/fallido queda registrado en `estado_*.jsonl` sin romper el job.
- [x] Esquema JSONL documentado y estable; fechas en ISO local MX.
- [x] Pipeline v1 sigue funcionando idéntico SIN snapshot (fallback OK).
- [ ] Con ≥7 días de snapshot: informe declara cobertura y usa tráfico semanal.

---

## 2. Mejora 2 — Validador automático del informe (gate del pipeline)

### 2.1 Problema que resuelve

La checklist §13 del maestro es manual y depende de memoria/disciplina. El
repo `lgy1027/ai-trend-radar-report` demuestra el patrón: un script que
valida el informe generado (estructura, enlaces, residuos) antes de darlo por
bueno. Aquí se automatizan las 8 reglas de la checklist, mapeadas 1:1.

### 2.2 Qué construir

`src/validar_informe.py` — Python stdlib-only (sin dependencias nuevas).
Doble modo:

```
python3 src/validar_informe.py --report reports/informe_...md --corrida data/raw/<marca>
python3 run_report.py ...            # invoca al validador al final, imprime resumen
```

Reglas (cada una produce `[FAIL]` o `[WARN]` con mensaje accionable):

| # | Regla | Fuente de verdad |
|---|---|---|
| R1 | Wikipedia ≥25 días descargados y >3000 artículos únicos | `auditoria.json` de la corrida |
| R2 | Tabla de fuentes sin ERROR (o ERROR justificado en metodología) | informe + `auditoria.json` |
| R3 | Ningún nicho del top-3 (trending ni growth) tiene <3 temas | informe + `temas_completos.json` |
| R4 | «Sin clasificar» ausente de secciones de ranking; permitido SOLO en anexo | parseo del informe |
| R5 | Δ% de cada tema recomputable: recalcular growth_pct desde las ventanas de `temas_completos.json` (promedios diarios, fórmula §7 del maestro) y comparar con lo impreso (tolerancia ±0.1 pp) | `temas_completos.json` |
| R6 | Intersección trending∩growth presente y destacada como máxima prioridad | informe |
| R7 | Todos los enlaces Wiki/Trends/YT bien encodeados: sin espacios literales, acentos percent-encoded (regex sobre URLs del informe; detectar `.replace(' ','+')` residual) | informe |
| R8 | `auditoria.json` y `temas_completos.json` existen, son JSON válidos y no vacíos | `data/raw/<corrida>/` |

Semántica de salida:

- `[FAIL] regla: detalle` → al menos un FAIL ⇒ exit code **1**.
- `[WARN] regla: detalle` → no falla la corrida pero se lista (p. ej. ERROR de
  GDELT justificado, snapshot <7 días).
- Resumen final: `VALIDACION: OK (0 FAIL, 2 WARN)` o `VALIDACION: FALLO (3 FAIL)`.

### 2.3 Notas de diseño

- El validador es **gate**, no corrector: reporta, no arregla. La IA/ejecutor
  corrige iterando (como pide el maestro §10/§11).
- Mantener las reglas en funciones independientes (`regla_r1(...)`)
  para poder testearlas con fixtures rotas a propósito.
- Modo standalone útil también para validar informes antiguos.

### 2.4 Criterios de aceptación

- [x] Las 8 reglas implementadas y probadas: para cada una existe un fixture
      roto a propósito que dispara el FAIL correspondiente.
- [x] Informe bueno de referencia pasa con exit 0.
- [x] Standalone funciona sobre informes históricos sin la corrida completa
      (degrada reglas dependientes de crudos a WARN con motivo).
- [x] `run_report.py` muestra el resumen de validación al terminar.

---

## 3. Mejora 3 (OPCIONAL) — Spike evaluación de `trendspy` como señal semanal

### 3.1 Motivación

El maestro §4.6 descartó correctamente `pytrends` (archivado abr-2025,
inestable). Existen alternativas mantenidas:

- [`sdil87/trendspy`](https://github.com/sdil87/trendspy) — MIT, ⭐116.
- [`flack0x/trendspyg`](https://github.com/flack0x/trendspyg) — fork/CLI
  gratuito mantenido, ⭐43 (trending now + interest over time + related).

Potencial: serie semanal REAL de interés por keyword (hoy el crecimiento se
apoya solo en pageviews de Wikipedia) y posiblemente más términos MX/día que
los ~10 del RSS. Riesgo conocido: puede sufrir el mismo throttling silencioso
clase bug#5 del maestro (sleep 0.12 s truncaba historial). Por eso es SPIKE
con decisión go/no-go, nunca adopción directa.

### 3.2 Protocolo del spike (time-box: máx 90 minutos)

Entorno aislado (`venv`), fuera del proyecto hasta pasar el filtro:

1. Instalar ambas librerías; probar primero `trendspy` (la original).
2. Script de prueba con **5 semillas** repartidas por taxonomía
   (config.yaml del maestro), p. ej.:
   `["resumen liga mx", "ia generativa", "receta chilaquiles", "formula 1", "bitcoin precio"]`
3. Para cada semilla: `interest_over_time` con `geo=MX`, ventana 28 días.
   Registrar: longitud de serie devuelta, códigos HTTP, valores nulos.
4. Ritmo conservador `sleep 0.35 s` entre llamadas (lección bug#5).
5. Repetir **3 corridas consecutivas** el mismo día y comparar.
6. Extra: contar términos de «trending now» MX y comparar contra el RSS
   (~10/día) durante 2 días.

### 3.3 Criterios de decisión (duros)

INTEGRAR solo si TODO se cumple:

- [ ] ≥4/5 semillas devuelven serie completa (`len == 28`, sin truncado silencioso).
- [ ] Sin errores 429/420 sostenidos al ritmo de 0.35 s.
- [ ] Resultados estables entre las 3 corridas (misma forma de serie, ±10 %
      de valores).
- [ ] Licencia compatible verificada en el código instalado (esperada MIT).

SI PASA → integración mínima y aislada:
- Colector nuevo `src/collectors/gt_interest.py` tras el flag CLI `--gt`
  (off por defecto, igual que `--gdelt`).
- `config.yaml` gana `gt_seeds` por nicho (reutilizar/expandir `semillas_yt`).
- Scoring v1 **sin cambiar pesos** (n_wiki sigue mandando); la señal GT entra
  como columna informativa del informe y, tras 2 semanas de datos, se evalúa
  sumarla como componente con peso pequeño.

SI FALLA → documentar síntomas en el estilo §11 del maestro (qué endpoint,
qué código HTTP, qué truncado) y **descartar sin tocar el núcleo**. La
columna vertebral sigue siendo Wikipedia pageviews.

---

## 4. Opciones evaluadas y DESCARTADAS (no re-explorar)

| Opción | Qué era | Por qué se descarta |
|---|---|---|
| [`trendsmcp-ai/Trends-MCP`](https://github.com/trendsmcp-ai/Trends-MCP) (⭐34) | MCP/API alojada de tendencias (Google/YT/TikTok/Wikipedia) | Servicio freemium con clave propia → viola restricción «sin clave»; no genera informes |
| [`trendsapi/trends-mcp`](https://github.com/trendsapi/trends-mcp) | MCP alojado multi-fuente | Igual que anterior |
| `andrewlwn77/google-trends-mcp` | MCP vía ScraperAPI | Requiere API key de pago |
| `wikipedia-trends-mcp` (trendsmcp) | MCP de pageviews | Alojado; además Wikipedia ya se consume directo gratis |
| [`cslis07/ultraresearch`](https://github.com/cslis07/ultraresearch) | Skill multi-fuente X/Reddit/HN/arXiv con verificación cruzada | Buen harness pero dominio distinto; sus fuentes violarían la geografía/enfoque actual |
| Scrapers de Suggest (`gsuggest`, `keyword-research`, etc.) | Scrapers simples de autocomplete | El maestro ya tiene `yt_suggest.py` verificado contra la API real; no aportan nada |
| Skills YouTube del awesome-list (Composio) | Transcripts/automatización vía Composio | Dependencia pesada; nada que ver con investigación de nichos |
| [`clayton-arch/niche-scout-demo`](https://github.com/clayton-arch/niche-scout-demo) | Agente de nichos YT por ratio demanda/oferta | Requiere YouTube Data API (clave + cuota) → viola restricción. Concepto de demanda/oferta anotado como posible v3 si algún día cambia la política de claves |

Notas de licencia verificadas: `sdil87/trendspy` = **MIT** (usable);
`vtasca/wikipedia-pageviews` = **sin licencia** (solo patrón conceptual,
código propio desde cero); `ai-trend-radar-report` = solo patrón del
validador, implementación propia stdlib.

---

## 5. Presupuesto

| Concepto | Costo | Justificación |
|---|---|---|
| GitHub Actions snapshot | $0 | Público: ilimitado. Privado: ~30 min/mes vs 2,000 gratis. Dataset vive como commits en el repo |
| APIs usadas (Trends RSS, Wikimedia, Suggest, HN) | $0 | Públicas y sin clave (ya verificadas en el maestro) |
| Validador | $0 | Python stdlib, corre en local |
| Spike trendspy | $0 | Librería MIT sobre endpoints públicos. Único riesgo: throttling (tiempo, no dinero) |

---

## 6. Orden de implementación (y por qué)

```
Paso 1  Snapshot MÍNIMO en marcha        (½ sesión)   ← PRIMERO: cada día sin
        src/snapshot.py + workflow                      snapshot es señal perdida
Paso 2  Validador automático             (½–1 sesión) ← independiente del paso 1
Paso 3  Integración snapshot→pipeline    (1 sesión)   ← SOLO con ≥7 días acumulados
        (colector + fallback + metodología)
Paso 4  Spike trendspy                   (≤90 min)    ← opcional, go/no-go duro
```

Racional: el paso 1 es pequeño y el valor crece con el tiempo (acumulación
diaria), así que arranca ya aunque la integración espere. El validador da
calidad inmediata sin infraestructura. El spike va al final porque es el único
con resultado incierto y nada del resto depende de él.

## 7. Prompt de reconstrucción para una IA

> Implementa las mejoras de `MEJORAS_MVP.md` sobre el sistema definido en
> `AGENTE_TENDENCIAS.md`. Respeta las restricciones de §0.2 (sin claves API,
> $0, convenciones HTTP del maestro §4). Orden exacto según §6: (1) snapshot
> mínimo — `src/snapshot.py` con esquema JSONL de §1.3.1 y workflow §1.3.2,
> idempotente y con fallback de estado; (2) `src/validar_informe.py` con las
> reglas R1–R8 de §2.2 como funciones independientes y fixtures rotas de
> prueba; (3) detente y espera a haber ≥7 días de snapshot antes de integrar
> (§1.4); (4) ejecuta el spike §3.2 solo si se te pide, aplicando los
> criterios duros §3.3 sin tocar el núcleo. Al terminar cada paso, valida con
> su checklist de aceptación (§1.6, §2.4) y documenta cualquier desviación
> encontrada en el estilo de §10/§11 del maestro.

## 8. Checklist global del proyecto de mejoras

- [ ] Snapshot corriendo a diario (workflow verde) y dataset creciendo 1 línea/día/término.
- [x] Dedup verificado (relanzamiento mismo día sin duplicados).
- [x] Validador integrado a `run_report.py` y pasando en informe de referencia.
- [x] Cada regla del validador demostrada con fixture rota.
- [ ] Integración snapshot→pipeline hecha SOLO tras ≥7 días, con fallback probado.
- [ ] Informe declara cobertura de snapshot («N/7 días») en metodología.
- [ ] Spike (si se hizo): decisión documentada go/no-go con evidencia.
- [x] Ningún cambio introdujo claves API, dependencias de pago ni rompió la corrida v1.
