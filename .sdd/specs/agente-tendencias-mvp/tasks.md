# Tareas — Agente de informes de tendencias YouTube (MVP)

## Wave 1 — Contrato y configuración

- [x] T1. Crear `requirements.md`, `design.md` y este plan. (Req RF-01..RF-14)
- [x] T2. Crear `trend-report/config.yaml` con períodos, fuentes, pesos y los
  17 macronichos. (Req RF-04, RF-08, RNF-05)
- [x] T3. Crear `trend-report/requirements.txt` y estructura de datos/salidas.
  (Req RF-12, RNF-04)

## Wave 2 — Núcleo de dominio y adaptadores HTTP

- [x] T4. Implementar `src/http.py` con User-Agent, timeout, retries, backoff y
  errores visibles. (Req RF-13, RNF-01)
- [x] T5. Implementar `src/classify.py` con normalización, regex de palabra
  completa y caché purgable. (Req RF-07, RF-09, RF-14)
- [x] T6. Implementar `src/scoring.py` con ventanas parametrizadas, métricas y
  ranking. (Req RF-10, RNF-02)
- [x] T7. Implementar `src/report_md.py` y helpers de enlaces. (Req RF-11,
  RF-14)

## Wave 3 — Colectores

- [x] T8. Implementar RSS Google Trends México. (Req RF-05, RF-13)
- [x] T9. Implementar pageviews/resúmenes de Wikipedia. (Req RF-05, RF-07,
  RF-09, RF-13)
- [x] T10. Implementar Suggest YouTube y validación de temas. (Req RF-04,
  RF-06, RF-11)
- [x] T11. Implementar Hacker News y GDELT opcional. (Req RF-05, RF-06,
  RF-13)

## Wave 4 — Orquestación y experiencia

- [x] T12. Implementar `run_report.py`, selector interactivo, flags y pipeline
  de dos pasadas. (Req RF-01..RF-06, RF-10..RF-12)
- [x] T13. Crear pruebas de lógica pura y validación de argumentos. (RNF-02,
  quality bar)
- [x] T14. Crear agente y skill de proyecto en `.opencode/`. (Req RF-01,
  RF-02)

## Wave 5 — Documentación y verificación

- [x] T15. Crear README raíz, README del sistema, `.gitignore` y licencia.
  (Req RF-14, RNF-04)
- [x] T16. Ejecutar pruebas, smoke test y una corrida real semanal sin YouTube;
  registrar evidencia. (Todos los RF aplicables)
- [x] T17. Completar `verification.md` con matriz, comandos y limitaciones.
  (Integrity Gate)

## Dependencias

```text
T1 -> T2/T3 -> T4/T5/T6/T7 -> T8/T9/T10/T11 -> T12 -> T13/T14/T15 -> T16 -> T17
```

No se añade una librería de PBT: no existe un test PBT en esta entrega y las
pruebas de dominio se resuelven con `unittest` estándar.
