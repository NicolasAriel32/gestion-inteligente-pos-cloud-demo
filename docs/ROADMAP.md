# ROADMAP — trabajo incremental SDD

**Versión de referencia**: 0.5.1 (2026-10-22); esquema candidato 0006_local_operations.
**Estado actual**: F1–F5 implementadas y validadas técnicamente; F5 fusionada por autorización (fb85521).
Identidad local, empleados, catálogo e inventario; evidencia en
[F1_DEVELOPMENT.md](../F1_DEVELOPMENT.md), [F2_DEVELOPMENT.md](../F2_DEVELOPMENT.md) y
[F3_DEVELOPMENT.md](../F3_DEVELOPMENT.md). F3 aprobada y fusionada a main en 3848d55.
El propietario autorizó integrar F4 mediante PR #4, manteniendo pendiente la prueba física
de la impresora de 58 mm. La autorización de fusión no certifica ese hardware. Evidencia en
[F4_DEVELOPMENT.md](../F4_DEVELOPMENT.md). Reportes F5 implementados; sin instalador. Ver [F5_DEVELOPMENT.md](../F5_DEVELOPMENT.md).

Cada etapa empieza con criterios de aceptación claros y termina con pruebas reproducibles y revisión humana. No intentar entregar todas las etapas de una vez.

## F0 — Constitución y specs
- [x] Establecer alcance de MVP y operación local offline.
- [x] Versionar los documentos SDD y AGENTS.md.
- [ ] Revisar propuestas técnicas con prototipo y cerrar decisiones pendientes.

## F1 — Esqueleto técnico
- [x] React/TypeScript/Vite + FastAPI.
- [x] SQLite/SQLAlchemy/Alembic con migración inicial vacía.
- [x] GET /api/health y frontend que consuma API local.
- [x] Comandos de desarrollo, pytest, tests frontend, lint.
- Aceptación: ejecutar ambos lados localmente sin servicios cloud, comandos documentados y tests básicos pasando.

## F2 — Identidad y usuarios
- [x] Inicialización segura de ADMIN de única ejecución.
- [x] Login, logout, sesión y autorización de empleados.
- [x] Auditoría básica.
- Aceptación: EMPLOYEE no accede a funciones admin vía API.

- Revisión posterior: H-F2-001/002/003 corregidos y revalidados; 47 pruebas aprobadas.
  [Hallazgos y prevención](ENGINEERING_FINDINGS.md).

## F3 — Catálogo e inventario
- [x] Categorías, productos, desactivación.
- [x] Ajustes de stock con motivo y movimientos.
- [x] Validaciones CHECK y FK.
- Aceptación: inventario consistente después de errores y reinicios.
- Evidencia: 78 pruebas backend, 20 frontend y 1 flujo E2E aprobados (99; 0 fallidas).
  Ruff, ESLint, TypeScript/Vite y migraciones sobre SQLite nuevo aprobados; concurrencia,
  idempotencia, rollback, upgrade desde F2 y reinicio real verificados. Revisión visual de
  la extensión F3 aprobada por el propietario. Windows/piloto continúan pendientes de sus fases.

## F4 — Caja e historial
- [x] Carrito y cobro manual registrado.
- [x] Venta atómica e idempotente en SQLite.
- [x] Anulación ADMIN y comprobante no fiscal (documento/flujo de impresión verificados).
- [x] Pruebas de concurrencia, rollback, duplicados.
- [ ] Validación física con modelo Global/Waggs u otra térmica de 58 mm y controlador Windows.
- Aceptación: superar todas las invariantes de venta.
- Software: 119 pruebas backend, 34 frontend y 1 flujo E2E aprobados; 154 en total,
  cero fallidas finales. Migraciones, Ruff, ESLint y build correctos. Recuperación después
  de perder respuesta, reautenticación, reinicio y PDF de 58 mm comprobados.
- Software aprobado para integración por el propietario en PR #4. No marcar validada la
  impresora: faltan modelo, controlador y prueba física. El cierre integral/piloto conserva
  ese pendiente. F5 autorizada posteriormente por instrucción explícita del propietario.

## F5 — Dashboard y reportes
- [x] KPIs y comparación temporal.
- [x] Ranking por unidades/ingresos, horas pico con timezone local.
- [x] Filtros y estados sin datos.
- Aceptación: reportes excluyen anuladas y coinciden con datos de prueba.

Software F5 verificado y fusionado en PR #5 (fb85521).
F6 autorizada por instrucción explícita posterior; implementación candidata en F6_DEVELOPMENT.md.

Mejora posterior 0.5.1: ayuda de uso local con guías rápidas y buscador, sin avanzar F6.
Evidencia en USER_HELP_DEVELOPMENT.md; revisión de la mejora independiente del merge F5.

## F6 — Respaldo, importación y distribución
- [x] Backup consistente y restauración probados en SQLite temporal/Linux; falta PC Windows objetivo.
- [x] CSV de altas nuevas con vista previa/validación, confirmación atómica y reintentos.
- [x] Build Windows, instalador y arranque único comprobados en CI Windows Server 2025; PC Windows 11 limpia pendiente.
- [x] Actualizaciones manuales documentadas; comprobación Windows pendiente.
- Aceptación: instalación limpia sin herramientas de desarrollo y recuperación demostrada.
- **F6 pendiente de cierre**: scripts/paquete candidato y validación Linux no certifican Windows 11 limpio.
  Ver F6_DEVELOPMENT.md y WINDOWS_VALIDATION.md. F7 no iniciada.

## F7 — Piloto y comercialización
- [ ] Pruebas de flujo real con dueño y empleado.
- [ ] Usabilidad, monitoreo de errores y ajustes.
- [ ] Guía de uso y recuperación de datos.
- Aceptación: aprobación explícita del piloto; no confundir demo con producción.

## Futuro, no MVP
MySQL multi-PC, servidor remoto, MCP, n8n, actualizador asistido, pagos online, varias cajas, facturación fiscal. Cada evolución requiere nueva spec y análisis de riesgos.

Actualización posterior: PR #6 autorizado e integrado en main 4b40e3f. Candidato F6
incorpora esa ayuda, mantiene producto 0.5.1 y conserva pendiente Windows 11 limpio.
La evidencia anterior describe su ejecución original; PR #7 no se fusiona.
