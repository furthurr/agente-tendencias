# SPEC — Agente/Skill de Informes Semanales de Tendencias (contenido YouTube, MX)

> Documento maestro para replicar con una IA el sistema completo construido y
> probado el **2026-08-24** (`trend-report/`). Todo lo aquí indicado fue
> verificado contra las APIs reales en esa fecha. Si una fuente cambia,
> la sección 11 lista los síntomas típicos y cómo diagnosticar.

---

## 1. Objetivo

Generar cada semana un informe Markdown con:

1. **Top 3 nichos más TRENDING** (mayor volumen absoluto de atención de la semana).
2. **Top 3 nichos con MAYOR CRECIMIENTO** (aceleración vs sus 3 semanas previas).
3. **Los 5 temas populares de cada nicho seleccionado**, con métricas y enlaces.
4. **Oportunidades YouTube**: búsquedas reales que el autocomplete de YT México sugiere por nicho.
5. Metodología documentada dentro del propio informe + anexos auditables.

Restricciones: solo fuentes públicas **sin clave API**, geografía **México/español**,
propósito **creación de contenido en YouTube**.

## 2. Entregables del sistema

```
trend-report/
├── README.md              # uso semanal
├── requirements.txt       # requests, PyYAML
├── config.yaml            # taxonomía de nichos, claves ES, pesos, umbrales
├── run_report.py          # orquestador CLI (--geo --gdelt --sin-yt --out)
├── src/
│   ├── http.py            # sesión UA propio, get_json/get_texto con backoff, guardar_crudo
│   ├── classify.py        # normalización, matcher palabra-completa, caché wiki
│   ├── scoring.py         # scores tema/nicho, selección top N
│   ├── report_md.py       # plantilla del informe
│   └── collectors/
│       ├── rss_mx.py      # Google Trends RSS
│       ├── wikipedia.py   # pageviews diarios + cálculo de ventanas
│       ├── yt_suggest.py  # autocomplete modo YouTube + validador de temas
│       ├── hackernews.py  # HN vía Algolia
│       └── gdelt.py       # OPCIONAL volumen noticioso
├── data/
│   ├── raw/<corrida>/     # JSON crudo por fuente + auditoria.json + temas_completos.json
│   └── wiki_cache.json    # caché persistente de clasificaciones
└── reports/informe_tendencias_<AAAA>-W<SS>.md
```

## 3. Pipeline (orden exacto)

```
1. colectores (RSS, Wikipedia 30d, HN; YT después)   → data/raw/<marca>/*.json
2. universo de temas (Wikipedia base + RSS sin match + HN top30)
3. clasificación por nicho (keywords → fallback descripción Wikipedia)
4. scoring pass 1 → ranking de nichos → candidatos = top3 trending ∪ top3 growth
5. señal YouTube: sugerencias por semilla de cada nicho candidato
   + validar cada uno de los 10 mejores temas de esos nichos
6. scoring pass 2 (ahora con yt_rank)
7. selección final top3/top3 + top5 temas por nicho
8. informe MD + auditoria.json
```

Duración típica: **2–4 min** (800 lookups máx. a la API de resumen + validaciones YT).

## 4. Fuentes verificadas (2026-08-24)

### 4.1 Google Trends RSS — señal "hoy"
- `GET https://trends.google.com/trending/rss?geo=MX`
- XML RSS 2.0, namespace `ht="https://trends.google.com/trending/rss"`.
- Por `<item>`: `title`, `ht:approx_traffic` (texto tipo `"2,000+"` → limpiar no-dígitos),
  `pubDate`, hasta varias `ht:news_item` con `ht:news_item_title/url/source`.
- MX devuelve pocos términos (~10/día). **Limitación clave**: solo cubre el día
  de la corrida → la ventana semanal se reconstruye con otras fuentes.

### 4.2 Wikipedia Pageviews — columna vertebral semanal
- Top diario: `GET https://wikimedia.org/api/rest_v1/metrics/pageviews/top/es.wikipedia/all-access/{YYYY}/{MM}/{DD}`
  - Respuesta: `items[0].articles[] = {article, views, rank}` (títulos con `_`, hasta 1000).
  - **Retraso ~2 días**: empezar en `hoy-2` y retroceder; si hay 404/vacío es "aún no publicado".
- Resumen de página (para clasificar): `GET https://es.wikipedia.org/api/rest_v1/page/summary/{titulo_con_guiones_bajos_URL-encoded}`
  - Devuelve `description` + `extract`; sigue redirects. Requiere User-Agent propio.
- Ritmo seguro observado: `sleep 0.35 s` entre requests (con 0.12 s se truncó el
  historial a 20 días, sospecha de throttling). Reintentos=2, timeout 25 s.

### 4.3 Google Suggest modo YouTube — demanda de búsqueda en YT
- `GET https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=es&gl=MX&q={q}`
- Respuesta JSON: `[consulta, [sugerencias...], [], {"google:suggestsubtypes": ...}]`
- Sin clave, funciona con `requests` normal. Pausa 0.35–0.4 s entre consultas.

### 4.4 Hacker News (Algolia) — refuerzo tech
- `GET https://hn.algolia.com/api/v1/search?tags=story&numericFilters=created_at_i>{unix_hace_7d},points>{50}&hitsPerPage=100`
- Ordenar por `points` desc, tomar 60.

### 4.5 GDELT (opcional, off por defecto)
- `GET https://api.gdeltproject.org/api/v2/doc/doc?query={q}&mode=timelinevol&format=json&startdatetime={AAAAMMDDHHMMSS}&enddatetime={...}`
- Comparar media de la serie semana actual vs semana anterior → % cobertura noticiosa.
- **Rate-limit agresivo (429)**: reintentos con backoff + `sleep 2 s` entre consultas.

### 4.6 Descartadas (verificado)
- **pytrends**: archivado abr-2025, `interest_over_time` inestable → NO usar.
- **Reddit JSON público**: 403 desde algunos proxies; si se usa, requiere
  User-Agent propio y aceptar límites estrictos. No es parte del pipeline v1.

## 5. Universo de temas

Partir de los títulos únicos de Wikipedia (~3 500 con 30 días × top500/día) y aplicar:

- Excluir prefijos internos: `Especial:, Wikipedia:, Ayuda:, Categoría:, Portal:,
  Plantilla:, Archivo:, Módulo:, Discusión:, Usuario:, MediaWiki:, Anexo:` (las páginas-lista contaminan).
- Excluir exactos: `Portada`, `Main_Page`, páginas-país/ciudad
  (`México, España, Argentina, Colombia, ..., Ciudad de México, Madrid, Barcelona, Buenos Aires`)
  porque son navegacionales y mal "tema popular".
- Descartar títulos de longitud < 4 y temas con `vistas_semana < 30`.
- RSS sin match en Wikipedia entran como temas nuevos (solo señal de búsqueda);
  igual las top-30 historias HN (marcadas `es_historia_hn`, sin lookup wiki).

Matcheo RSS→tema: título normalizado igual, o contención mutua si `len≥5`.

Esquema de tema (dict):
```
titulo, vistas_semana, base_semana, growth_pct, dias_semana, dias_base,
rss_trafico, hn_puntos, yt_rank, nicho, es_historia_hn,
trending_score, growth_score, score_final
```

## 6. Clasificación en nichos

### 6.1 Normalización (aplicar a TÍTULOS y a CLAVES por igual)
```python
_PUNCTUATION = str.maketrans({c: " " for c in "-_/\\|,.:;!?¿¡()[]{}\"'`´~*+#&@$%^=<>" +
                              "\u2013\u2014\u2018\u2019\u201c\u201d"})
def normalizar(t):
    t = t.lower().strip().translate(_PUNCTUATION)
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.split())
```
Convertir puntuación a espacio hace equivalentes `spider-man` ↔ `spider man`,
`h&m` ↔ `h m`. Quitar acentos hace equivalente `méxico` ↔ `mexico`.

### 6.2 Matcher por PALABRA COMPLETA (crítico)
```python
patron = re.compile(rf"(?<![a-z0-9]){re.escape(clave_norm)}(?![a-z0-9])")
# match sobre f" {titulo_norm} " (y sobre descripción si hay fallback)
```
**Lección aprendida**: el substring ingenuo producía `terremoto→clave "moto"`
(Autos), Lorca→Deportes, etc. Con límites de palabra, 8/8 casos de prueba OK.

### 6.3 Taxonomía (`config.yaml`) — 17 nichos, ~850 claves
IA y Tecnología · Gaming y Esports · Deportes · Finanzas y Cripto · Salud y Fitness ·
Entretenimiento y Música · Cine y TV · Comida y Cocina · Viajes y Turismo ·
Ciencia y Educación · Negocios y Emprendimiento · Moda y Belleza · Autos y Motores ·
Clima y Fenómenos Naturales · Sociedad y Política · Literatura e Ideas · Fe y Espiritualidad.

Reglas de diseño:
- **Orden importa**: primer nicho con match gana; específicos antes que genéricos.
- Incluir **claves de profesión** ("futbolista", "actriz", "chef", "cantante",
  "político", "escritor", "ilusionista", "medico", "automovilismo"...): casi nunca
  aparecen en títulos pero SÍ en las descripciones de Wikipedia → son las que
  clasifican personas.
- Cada nicho lleva `semillas_yt`: 2–3 queries para pedir sugerencias reales
  (ej. Deportes: `["resumen liga mx", "highlights deportivos", "analisis partido"]`).

### 6.4 Fallback Wikipedia + caché con política de purga
1. Keyword sobre título → si falla y `vistas_semana ≥ 300` y no es historia HN →
   consultar `page/summary` (tope **800 lookups/corrida**, ordenando temas por
   vistas desc) y repetir keywords sobre `description + extract[:400]`.
2. Cachear resultado en `data/wiki_cache.json`.
3. **En cada corrida purgar entradas `None`** (`invalidar_nones()`): los pendientes
   se reintenta con la taxonomía actual; los confirmados persisten. Sin esto,
   clasificar con taxonomía vieja quedaba "congelado" (bug real: Lee Kang-in).

Cobertura alcanzada: ~50% del top-400; el resto queda visible en el anexo
"Temas sin clasificar". Es honesto documentarlo como limitación.

## 7. Scoring (fórmulas exactas)

Ventanas: semana = últimos 7 días disponibles; base = 21 días anteriores.
**Comparar PROMEDIOS DIARIOS** por ventana (robusto a días faltantes):

```python
prom_dia_semana = sum(dias_semana_presentes)/len(...)
prom_dia_base   = sum(dias_base_presentes)/len(...)   # puede ser < 21 días
growth_pct      = (prom_dia_semana - prom_dia_base)/prom_dia_base * 100  si prom_dia_base > 1
base_semana_reportada = prom_dia_base * 7
```

**Trending** (volumen absoluto): componentes min-max normalizados (vistas y tráfico con `log1p`):
```
trending = 0.45*n_wiki + 0.25*n_rss + 0.20*n_yt + 0.10*n_hn
n_yt = rank en validación YT ∈ [0..1]  (0 si no aparece)
```

**Growth** (aceleración):
```
crecimiento = clip(growth_pct, 0, 500)/500     # solo si vistas_semana >= 300
tamano      = n_wiki (log-minmax)
growth      = 0.65*crecimiento + 0.35*tamano
```

**Tema**: `score_final = 0.6*trending + 0.4*growth`
**Nicho**: promedio de los **8 mejores miembros** en cada dimensión;
`min_temas_nicho = 3` (nichos más pequeños no compiten — evitó que "Comida y
Cocina" entrara al top con 1 solo tema).
Rankings excluyen el cajón **"Sin clasificar"** (no es nicho).

Validador YT (`validar_temas`): pedir sugerencias del propio título del tema;
si aparece dentro, `rank = (N - mejor_pos)/N` (×0.6 si no es la primera posición).

## 8. Informe MD — estructura obligatoria

1. **Cabecera**: semana ISO, rango analizado + rango base, fecha, geo, objetivo.
2. **Resumen ejecutivo**: tabla lado-a-lado trending vs crecimiento.
3. **Metodología y fuentes**: estado por fuente (OK con conteo / ERROR),
   fórmulas con los valores reales de config, limitaciones conocidas.
4. **Top 3 TRENDING**: por nicho → score, nº temas, tabla top-5 con
   `Vistas/semana | Δ% vs base | Trending | Growth | Enlaces(Wiki·Trends·YT)`.
   Δ con flechas ▲▼—.
5. **Top 3 CRECIMIENTO**: idéntico formato.
6. **Oportunidades YouTube**: destacar intersección de ambas listas
   ("máxima prioridad") y listar 8 sugerencias reales por nicho con link a
   búsqueda YT.
7. **Anexo**: temas sin clasificar (top por vistas), tendencias RSS de hoy con
   titular de contexto, notas de reproducibilidad.

URL helpers: Wiki `es.wikipedia.org/wiki/{quote(titulo.replace(' ','_'))}`,
Trends `trends.google.com/trends/explore?geo=MX&q={quote_plus}`,
YT `youtube.com/results?search_query={quote_plus}` (usar quote SIEMPRE, no replace de espacios).

## 9. CLI

```
python3 run_report.py             # corrida estándar geo MX
--geo US                          # otra geografía (RSS+Suggest+links)
--gdelt                           # añade señal noticiosa (lenta, opcional)
--sin-yt                          # omite fase YouTube (rápido)
--out ruta.md                     # salida personalizada
```

Salida secundaria de auditoría por corrida: `auditoria.json` (estado fuentes,
top niches con scores) y `temas_completos.json` (top 400 temas con todos sus campos).

## 10. Bugs reales encontrados (replicar = evitarlos)

| # | Síntoma | Causa | Solución aplicada |
|---|---|---|---|
| 1 | `Terremoto de Colombia` clasificado Autos | substring: "terre**moto**" | regex con límites de palabra |
| 2 | Personas famosas sin nicho | claves solo de temas, no profesiones | claves de profesión que disparan sobre `description` de la API resumen |
| 3 | Clasificación "congelada" tras cambiar taxonomía | caché guardaba `None` | purgar `None`s al inicio de cada corrida |
| 4 | Δ% absurdos (+2000%) | base calculada dividiendo siempre entre 3 semanas con días faltantes | comparar promedios diarios presentes por ventana |
| 5 | Historial truncado a 20 días | sleep 0.12s → throttling silencioso | sleep 0.35s + contar fallos consecutivos (stop ≥6) |
| 6 | Nicho top-3 con 1 solo tema | sin mínimo de miembros | `min_temas_nicho: 3` |
| 7 | "Sin clasificar" ganaba rankings | cajón catch-all competía | excluirlo de `rankear_nichos` |
| 8 | Fase YouTube fallaba sin mensaje claro | función renombrada (`time_pausa`) | try/except visible en tabla de estado de fuentes |
| 9 | País "México" como tema popular de Deportes | páginas-país navegacionales | stoplist de países/ciudades en el universo |
| 10 | Links YT rotos con acentos | `.replace(' ','+')` insuficiente | `urllib.parse.quote_plus` |

## 11. Diagnóstico rápido de fallos

- Wikipedia devuelve pocos días → revisar HTTP (429/420 = bajar ritmo, subir sleep).
- RSS vacío → probar `?geo=US`; MX tiene pocos términos algunos días (normal).
- Suggest vacío → verificar `ds=yt&hl=es&gl=MX`; el formato debe ser lista JSON.
- GDELT 429 constante → dejarlo deshabilitado; es opcional.
- Cobertura de clasificación baja → subir `MAX_LOOKUP_WIKI`, añadir claves
  de profesión, revisar anexo de sin-clasificar para nuevas reglas.

## 12. Prompt de reconstrucción para una IA

> Construye el sistema descrito en este documento en la carpeta `trend-report/`
> siguiendo la sección 2 (archivos), 3 (pipeline), 4 (endpoints exactos),
> 5–8 (datos, clasificación, scoring, informe) y 9 (CLI).
> Requisitos duros: matcher por palabra completa (§6.2), purga de `None` en caché
> (§6.4), promedios diarios para growth (§7), exclusión de "Sin clasificar" y
> `min_temas_nicho` (§7), stoplist de países (§5), User-Agent propio y backoff en
> todas las fuentes (§4), informe con la estructura §8 incluyendo metodología y
> anexos. Al terminar: ejecuta `python3 run_report.py`, verifica con la checklist
> §13 y corrige iterando sobre los errores tipo §10.

## 13. Checklist de validación de una corrida

- [ ] Wikipedia ≥ 25 días descargados (ideal 28–30) y > 3000 artículos únicos.
- [ ] Tabla de fuentes sin ERROR (o errores justificados en metodología).
- [ ] Ningún nicho del top-3 tiene menos de 3 temas.
- [ ] "Sin clasificar" NO aparece en rankings (solo en anexo).
- [ ] Los Δ% de la semana cuadran al comparar con semanas previas visibles en crudos.
- [ ] Intersección trending∩growth calculada y destacada.
- [ ] Enlaces Wiki/Trends/YT funcionan (sin espacios sin encodear).
- [ ] `auditoria.json` y `temas_completos.json` escritos en `data/raw/<corrida>/`.

## 14. Extensiones previstas

- Geografía dual MX+US combinando señales.
- Snapshot diario programado (cron) para Trends acumulado semanal real.
- Deduplicación de entidades con distinta ortografía (Klichkó/Klitschko).
- Señales extra: Pinterest Trends, Amazon Movers & Shakers, GitHub trending (tech).
- Salida complementaria JSON/CSV para dashboards.
