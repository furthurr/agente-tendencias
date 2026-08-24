# Requisitos — Agente de informes de tendencias YouTube (MVP)

**Tipo:** feature  
**Modo:** standard / Quick Plan autorizado por la petición explícita de cerrar el MVP  
**Fuente de negocio:** `AGENTE_TENDENCIAS.md`  
**Estado:** implementado en esta entrega; la evidencia final está en `verification.md`.

## Objetivo y porqué

Permitir que un creador de contenido obtenga un informe reproducible de
tendencias de YouTube para México/español sin claves API. El usuario debe poder
pedir una ventana de una semana, un mes o un año hacia atrás, porque cada
ventana responde a una decisión editorial distinta: reacción rápida, revisión
mensual o planificación anual.

## Historias de usuario

### HU-01 — Seleccionar período

Como creador, quiero elegir semana, mes o año para decidir el horizonte del
informe sin editar archivos de configuración.

### HU-02 — Ejecutar desde CLI o agente

Como usuario, quiero ejecutar el sistema con una opción CLI o entrar al agente
de opencode y recibir la pregunta del período, para usar el mismo MVP de forma
manual o conversacional.

### HU-03 — Comparar popularidad y crecimiento

Como creador, quiero distinguir volumen absoluto de aceleración, para no
confundir un tema grande con uno que está empezando a crecer.

### HU-04 — Encontrar oportunidades de YouTube

Como creador, quiero ver sugerencias reales del autocompletado de YouTube y
enlaces de búsqueda, para convertir el informe en ideas accionables.

### HU-05 — Auditar el resultado

Como usuario, quiero conocer fuentes, ventanas, errores y datos crudos, para
valorar la calidad del informe y reproducirlo.

## Requisitos funcionales (EARS)

### RF-01 — Selector interactivo

**CUANDO** el usuario ejecute `run_report.py` sin `--period` en una terminal,
selección válida y continuar con ese período.

### RF-02 — Selector no interactivo

**CUANDO** el usuario proporcione `--period semana`, `--period mes` o
`--period anio`, **EL SISTEMA DEBERÁ** ejecutar sin solicitar entrada
interactiva.

### RF-03 — Validación del período

**SI** el período no pertenece a `semana|mes|anio`, **ENTONCES EL SISTEMA
DEBERÁ** mostrar un error accionable y no iniciar llamadas a fuentes.

### RF-04 — Ventanas configurables

**SIEMPRE** el sistema deberá usar estas ventanas por defecto:

| Período | Ventana actual | Ventana base |
|---|---:|---:|
| semana | 7 días disponibles | 21 días anteriores |
| mes | 30 días disponibles | 90 días anteriores |
| anio | 365 días disponibles | 365 días anteriores |

La configuración deberá estar separada del código para facilitar una futura
revisión metodológica.

### RF-05 — Fuentes públicas

**CUANDO** se ejecute una corrida, **EL SISTEMA DEBERÁ** intentar recoger
Google Trends RSS, pageviews de Wikipedia y Hacker News; no deberá requerir
claves API para esas fuentes.

### RF-06 — Fuentes opcionales

**CUANDO** se use `--gdelt`, **EL SISTEMA DEBERÁ** añadir la señal GDELT con
backoff; **CUANDO** se use `--sin-yt`, **EL SISTEMA DEBERÁ** omitir la fase de
YouTube y dejarlo explícito en el estado de fuentes.

### RF-07 — Clasificación segura

**SIEMPRE** la clasificación deberá normalizar acentos/puntuación y hacer match
por palabra completa; nunca deberá usar un substring ingenuo que convierta, por
ejemplo, `terremoto` en `moto`.

### RF-08 — Taxonomía MVP

**SIEMPRE** el MVP deberá incluir los 17 macronichos definidos en
`AGENTE_TENDENCIAS.md`, conservar el orden de prioridad de configuración y
mantener `Sin clasificar` fuera de los rankings.

### RF-09 — Caché de Wikipedia

**CUANDO** se consulte un resumen de Wikipedia, **EL SISTEMA DEBERÁ** guardar
la clasificación en `data/wiki_cache.json` y purgar las entradas `None` al
comienzo de una corrida.

### RF-10 — Scoring

**CUANDO** existan datos suficientes, **EL SISTEMA DEBERÁ** calcular promedio
diario, crecimiento, trending y score final con las fórmulas de la sección 7
del documento maestro, y exigir al menos 3 temas elegibles por nicho.

### RF-11 — Informe

**CUANDO** finalice una corrida, **EL SISTEMA DEBERÁ** escribir un informe
Markdown con cabecera, resumen, metodología, top trending, top crecimiento,
oportunidades YouTube y anexos de temas sin clasificar.

### RF-12 — Auditoría

**CUANDO** finalice una corrida, **EL SISTEMA DEBERÁ** escribir
`auditoria.json` y `temas_completos.json` dentro de `data/raw/<corrida>/`.

### RF-13 — Errores de infraestructura

**SI** una fuente responde con timeout, HTTP no exitoso, JSON/XML inválido o
rate limit, **ENTONCES EL SISTEMA DEBERÁ** reintentar según la política de la
fuente, registrar el error y continuar con las demás fuentes cuando sea
posible.

### RF-14 — Reproducibilidad y privacidad

**SIEMPRE** el sistema deberá documentar fecha, geografía, período, ventanas,
fuentes y limitaciones; no deberá incluir claves, cookies ni datos personales
en el repositorio ni en los archivos de auditoría.

## Requisitos no funcionales

- RNF-01: las llamadas HTTP deberán usar User-Agent propio, timeout y backoff.
- RNF-02: las reglas de dominio (normalización y scoring) deberán poder probarse
  sin red.
- RNF-03: una fuente caída no deberá ocultarse: el informe marcará `ERROR` o
  `OMITIDA` con motivo.
- RNF-04: el MVP deberá ser ejecutable con Python 3.10+ y dependencias mínimas.
- RNF-05: el sistema deberá ser ampliable a nuevos nichos sin cambiar el
  algoritmo central.

## Fuera de alcance del MVP

- Descubrimiento automático de nuevos macronichos.
- Dashboard web o base de datos interna.
- Credenciales de YouTube Data API.
- Programación cron y snapshots diarios.
- Publicación automática en GitHub.

## Supuestos y decisiones por defecto

1. `anio` significa los últimos 365 días disponibles frente a los 365 días
   anteriores; no significa año natural.
2. Google Trends RSS aporta la señal del día de la corrida en todos los
   períodos; la ventana histórica se apoya principalmente en Wikipedia.
3. La consulta anual puede tardar bastante más que la semanal y queda
   documentada como operación intensiva.
4. El usuario puede cambiar `geo`, activar GDELT u omitir YouTube mediante CLI.
