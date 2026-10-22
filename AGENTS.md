# AGENTS.md — instrucciones para agentes de desarrollo

## Objetivo
Desarrollar Gestión Inteligente POS: sistema local-first para una caja de kiosco argentino.
El repositorio contiene software local F1–F5 (0.5.1) y un candidato F6 en desarrollo.
F6 no se declara validada hasta completar la instalación limpia y recuperación en Windows.
Consultar ROADMAP para distinguir entregas verificadas, validación física pendiente y
fases futuras. No usar Lovable ni agregar servicios cloud obligatorios.

## Orden de lectura
1. docs/PROJECT_SPEC.md — alcance y actores
2. docs/BUSINESS_RULES.md — invariantes
3. docs/DOMAIN_MODEL.md — modelo de dominio
4. docs/ARCHITECTURE.md — capas y contratos
5. docs/PERSISTENCE.md — transacciones, integridad y respaldo
6. docs/INSTALLATION.md — instalación y ejecución local
7. docs/ROADMAP.md — secuencia de entregables
8. docs/DECISIONS.md — decisiones aceptadas y propuestas
9. docs/ACCEPTANCE_TESTS.md — verificación

Ante conflicto, **detener la implementación relacionada y señalarlo**. No reinterpretar decisiones explícitas para acomodar código existente.

## Rutina SDD obligatoria
- Leer las specs afectadas antes de modificar código.
- Definir cambio acotado, archivos afectados, riesgos y criterio de aceptación.
- Implementar el incremento más pequeño que pueda verificarse.
- Ejecutar pruebas relevantes; informar comandos y resultados reales (no inventarlos).
- Actualizar las specs y DECISIONS.md cuando cambie una decisión.
- No usar el historial de chat como fuente de verdad del producto.

## Reglas innegociables
- No confiar en permisos, precios ni totales enviados desde el navegador.
- Nunca vender sin stock suficiente ni dejar stock negativo.
- Venta y reversión: operaciones atómicas, idempotentes y auditables.
- No borrar ventas históricas ni productos referenciados por ellas.
- Roles autorizados en backend; usar usuarios individuales.
- No exposición pública del backend: escuchar solamente en loopback.
- Aplicar validaciones de origen/Host y proteger sesión y credenciales.
- No poner archivos de datos comerciales en el directorio de binarios.
- No introducir LLM, MCP operativo, pagos online o telemetría sin decisión documentada.
- Nunca registrar secretos ni contraseñas en logs, repositorio o respuestas.
- No ejecutar operaciones destructivas, migraciones irreversibles ni cambios sensibles sin autorización humana.

## Convenciones de código
- Estructura por capas y módulos de dominio; frontend sin acceso directo a SQLite.
- Tipado explícito, contratos OpenAPI y pruebas automáticas.
- Comandos de entorno y dependencias versionadas y documentadas en README.
- Mantener coherentes versiones de backend, API, frontend, lockfile y specs según
  docs/VERSIONS.md; la revisión Alembic es independiente de la versión del producto.
- Pruebas de integración reales para concurrencia de SQLite, auth y operaciones monetarias.
- GitHub es fuente de verdad. Un cambio no está listo por verse correcto visualmente.

## Definition of done
- Aceptación verificable; pruebas realizadas y resultados reportados.
- Sin regresión de reglas críticas ni cambios fuera de alcance.
- Documentación coherente y riesgos pendientes explícitos.
- La creación de documentación por sí sola **no implica software implementado**.

## Aprendizajes obligatorios para nuevas fases
- Leer [docs/ENGINEERING_FINDINGS.md](docs/ENGINEERING_FINDINGS.md) antes de trabajar en
  persistencia, migraciones, arranque o cierre de validación.
- Aplicar los puntos pertinentes de [docs/PROJECT_REVIEW_CHECKLIST.md](docs/PROJECT_REVIEW_CHECKLIST.md).
- No asumir atomicidad del DDL por usar un contexto transaccional: probar interrupción y reintento.
- No habilitar autogeneración con metadatos vacíos o parciales.
- Al cambiar el esquema, actualizar el contrato de arranque y probar versiones incompatibles.
- Documentar cada nuevo hallazgo con causa, fix, prueba de regresión y práctica reutilizable.

## Actualización voluntaria — instrucción del propietario (2026-10-22)

Nunca bloquear el arranque por existir una versión nueva, antigüedad del programa,
falta de conexión o falta de actualización. La instalación compatible debe seguir
funcionando offline. El propietario decide si actualiza, manualmente y mediante una
herramienta externa separada. No agregar comprobaciones remotas obligatorias ni
actualizadores automáticos/silenciosos. Se mantienen las protecciones de integridad
y compatibilidad de la base; no modificar datos ni migrar en el arranque normal.
