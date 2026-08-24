# Tareas — Mejoras MVP v2

## Snapshot

- [x] V2-T1. Extraer parser RSS reutilizable. (V2-RF-01, V2-RF-02)
- [x] V2-T2. Implementar snapshot JSONL, timezone MX, deduplicación y estados.
  (V2-RF-01..V2-RF-04)
- [x] V2-T3. Añadir workflow programado/manual con rutas correctas. (V2-RF-05)

## Validador

- [x] V2-T4. Implementar `regla_r1` a `regla_r8` y CLI standalone.
  (V2-RF-06, V2-RF-09)
- [x] V2-T5. Integrar gate al final de `run_report.py`. (V2-RF-07)
- [x] V2-T6. Añadir fixture buena y ocho escenarios rotos. (V2-RF-06)

## Documentación y verificación

- [x] V2-T7. Actualizar README y documentar que la integración espera 7 días.
  (V2-RF-08, V2-RF-09)
- [x] V2-T8. Ejecutar tests, snapshot simulado y corrida real validada.
  (V2-RF-01..V2-RF-09)
- [x] V2-T9. Completar `verification.md`; dejar `trendspy` como omitido con
  razón. (Integrity Gate)

## No ejecutado en esta wave

- [omitido: `trendspy` es spike opcional; requiere pruebas de estabilidad y no
  debe entrar como dependencia del núcleo sin evidencia]
- [omitido: integración `rss_snapshot.py` al scoring; se requiere acumular al
  menos 7 días útiles]
