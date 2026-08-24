# Historial de cambios

## [v0.1.0] - 2026-08-24

### MVP

- Informes para los periodos semana, mes y año.
- Ranking de 17 macronichos con señales de fuentes públicas sin claves API.
- Snapshot diario del RSS de Google Trends mediante GitHub Actions.
- Validador automático con reglas R1–R8.
- Agente, skill y comando reutilizable para opencode.

### Limitaciones conocidas

- El snapshot todavía no se integra al scoring hasta acumular siete días útiles.
- La evaluación de `trendspy` queda diferida como spike opcional.
