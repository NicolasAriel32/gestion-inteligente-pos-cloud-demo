# DECISIONS — decisiones arquitectónicas y de producto

Versión de referencia: 0.5.1. Actualización: 2026-10-22; decisiones originales: 2026-10-21.
Formato: ID, fecha, estado, decisión, motivo, consecuencias. Distinguir **aprobado**, **implementado** y **propuesto**.

## Aceptadas por el propietario
### ADR-001 — Una caja local sin conexión obligatoria (ACEPTADA)
El MVP opera en una sola PC del kiosco, un comercio, una sucursal y una caja. Venta y stock sin internet. Consecuencia: no necesita backend cloud ni sincronización remota inicial.

### ADR-002 — SDD, repositorio central y agentes de desarrollo (ACEPTADA)
GitHub es fuente de verdad; specs y AGENTS.md guían a Codex y otras herramientas. Las reglas críticas se validan con pruebas, no únicamente con prompts.

### ADR-003 — Retirar Lovable (ACEPTADA)
No usar Lovable en el proyecto. Controlamos el código y las decisiones de arquitectura directamente en el repositorio.

### ADR-004 — Roles y núcleo funcional (ACEPTADA)
Dos roles (ADMIN/EMPLOYEE), catálogo, inventario, venta, historial, productos más vendidos, horas pico y dashboard. Operaciones críticas con permisos backend.

## Tecnología implementada y propuestas de distribución
### ADR-005 — React/TypeScript/Vite + FastAPI (IMPLEMENTADA Y VALIDADA EN DESARROLLO)
Núcleo local F1–F4 implementado y probado. En desarrollo FastAPI y Vite corren por separado;
frontend estático servido por backend y empaquetado Windows siguen como objetivo F6.

### ADR-006 — SQLite/SQLAlchemy/Alembic (IMPLEMENTADA Y VALIDADA F1–F4)
Base local apropiada para una caja, sin MySQL instalado. Usar transacciones de escritura y backups consistentes. Futuro MySQL implica adaptación, migración y pruebas; no es automático.

### ADR-007 — PyInstaller + Inno Setup (PROPUESTA)
Binarios e instalador Windows sin runtimes de desarrollo. Validar con PC limpia.

### ADR-008 — Datos privados en LOCALAPPDATA (IMPLEMENTADA; VALIDACIÓN WINDOWS PENDIENTE)
Una cuenta Windows por instalación. Si cambia a uso multiusuario de Windows, revisar ACL, ruta y propiedad de datos.

### ADR-009 — MCP y automatización diferidos (ACEPTADA COMO ALCANCE)
Preparar contratos de negocio para uso posterior por agentes; no implementar MCP o LLM en MVP.

### ADR-010 — Un pago declarado por venta (IMPLEMENTADA F4; POLÍTICA DE PILOTO PENDIENTE)
Registrar efectivo, transferencia, débito o crédito; sin verificación externa de cobro ni pagos mixtos. Determinar política definitiva en piloto.

## Pendientes materiales
- Política de respaldo externo, restauración y frecuencia predeterminada.
- Criterio de soporte Windows 10, ya fuera de soporte general; Windows 11 es objetivo principal.
- Experiencia de cierre de aplicación sin dejar servidor huérfano.
- Política de recuperación de credenciales sin bypass de permisos.
- Comprobante no fiscal y requerimientos de impresora del piloto.
- Definir si exportación de ventas y stock en CSV se incorpora en F6 (solicitud previa; recomendable).
- Confirmar si lectura de código de barras mediante lector USB tipo teclado es prioritaria (distinto de cámara).

Registrar decisiones futuras con fecha y efecto en PROJECT_SPEC/BUSINESS_RULES/ACCEPTANCE_TESTS.

## Detalles de implementación F2 — 2026-10-22

Sesiones opacas revocables en SQLite, Argon2id, inicialización con secreto local de
uso único y CSRF se concretan en [F2_DEVELOPMENT.md](../F2_DEVELOPMENT.md).
Se mantienen las decisiones de despliegue y roles existentes. La recuperación de
credenciales continúa pendiente del propietario; F2 no introduce ningún bypass.

### Correcciones de implementación F2 — 2026-10-22

Se concreta la exigencia existente de migraciones seguras y rechazo de esquemas
incompatibles: transacción física SQLite, contrato de arranque y bloqueo de autogeneración
con metadatos incompletos. No cambia el stack ni las decisiones aceptadas. Las migraciones
permanecen manuales. Ver [ENGINEERING_FINDINGS.md](ENGINEERING_FINDINGS.md).

### ADR-011 — Identidad visual Manrope, negro y amarillo (APROBADA POR EL PROPIETARIO)
Fecha: 2026-10-22. Dirección C: comercial y enérgica, profesional y cercana.
Manrope local en WOFF2 con licencia SIL OFL; negro #171714, amarillo #FFD633 y superficies
#FFF3B0. Microinteracciones CSS discretas con reducción de movimiento.
La aplicación de esta identidad a F2 fue autorizada y fusionada en PR #2, merge 058a92f,
el 2026-10-22. No cambia contratos API ni arquitectura; F3 conserva estos criterios.
Especificación: [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).

### Concreción F3 — 2026-10-22

Se informó antes de implementar la ampliación aditiva de auditoría: audit_events conserva
los eventos de F2 y permite referencias de catálogo/inventario, mientras audit_log sigue
compatible con identidad. Ajustes serializados e idempotentes; dinero en centavos e
interfaz decimal exacta. Alcance y contratos en [F3_DEVELOPMENT.md](../F3_DEVELOPMENT.md).

### Concreción F4 — 2026-10-22

El propietario aprobó fusionar PR #3 e implementar F4 respetando las especificaciones.
Se conserva pago manual único, sin integración financiera, como define DOMAIN_MODEL.
Comprobante no fiscal mediante impresión del navegador; requisitos de impresora física
y política definitiva del piloto siguen pendientes, sin bloquear las operaciones locales.
Cotización calculada por servidor y revisión explícita si cambia el catálogo; venta con
UUID idempotente y recuperación del intento tras respuesta perdida. Anulación ADMIN
total e idempotente. Diseño previo, riesgos y contratos: [F4_DEVELOPMENT.md](../F4_DEVELOPMENT.md).

El propietario añadió formato de ticket para térmicas económicas de 58 mm (Global/Waggs).
Se concreta con controlador de Windows y diálogo local del navegador; compatibilidad
física pendiente del modelo y prueba real. No se presume impresión silenciosa/ESC-POS.
Un fallo de impresión conserva la venta y permite reimprimir: [PRINTING.md](PRINTING.md).

### Integración F4 y versiones — 2026-10-22

El propietario autorizó fusionar PR #4 a main, conservando la validación física de
impresión como pendiente, y solicitó actualizar specs/versiones. Se alinean backend,
API, frontend y lockfile en 0.4.0; esquema Alembic 0004_checkout_history sin cambios.
No cambia arquitectura ni reglas comerciales. Los estados anteriores se actualizan
según implementación/evidencia, sin certificar Windows, piloto ni impresora.
F5 todavía no se implementa; su siguiente instrucción se documenta en NEXT_STEP_F5.md.

### ADR-012 — Reporte consistente y exacto (IMPLEMENTADA F5, 2026-10-22)

Dentro del alcance F5 autorizado: una sola respuesta GET /api/reports/summary consolida
KPIs, comparación, rankings y horas sobre un snapshot de lectura explícito. Se concreta
la API prevista sin exponer endpoints separados con instantes distintos. No cambia stack.
Calendario, comparación comparable, límites 366 días y redondeo exacto se definen en
[F5_DEVELOPMENT.md](../F5_DEVELOPMENT.md). Agregados como strings enteros decimales para
superar int64/JS seguro, sin modificar DTO de F1–F4. SQLite pos_sum Python exacto;
BigInt en UI. Índice aditivo 0005 justificado por búsqueda global por estado/fecha.
Única nueva dependencia tzdata para datos horarios offline en Windows. No implica
instalador Windows aprobado. F6, CSV, backups y hardware siguen pendientes.

### ADR-013 — Ayuda local y guías por rol (IMPLEMENTADA 0.5.1, 2026-10-22)

El propietario propuso ayuda rápida con signo de pregunta para cargar productos, cambiar
precios y configurar funciones existentes. Se concreta en una guía estática local con
búsqueda y temas; no requiere servicios, IA ni conexión. Muestra pasos según rol y aclara
funciones pendientes sin presentarlas disponibles. No realiza acciones comerciales ni
reemplaza permisos backend. Es una mejora de uso separada de F6; F6 no está iniciada.
Diseño previo/criterios/resultados en USER_HELP_DEVELOPMENT.md.

### ADR-015 — Clon independiente de demo funcional remota (AUTORIZADA, 2026-10-23)

El propietario solicitó probar todas las funciones implementadas desde un enlace de
Cloudflare, sin instalar software en la PC del trabajo, y guardar la adaptación en
un repositorio clonado con nombre diferencial para desplegarlo desde su rama principal.

Se conserva el backend real Python/FastAPI/SQLite, sus transacciones y permisos, en
un servicio Render. Cloudflare Workers sirve React compilado y reenvía `/api/*` al
backend, conservando sesión/CSRF y sin reintentar escrituras. No se sustituye el negocio
por mocks. Se autoriza un entrypoint remoto de demo con opt-in explícito, allowlists
de Host/origen exactos, cookies Secure y límite global de intentos de autenticación.
El entrypoint local y el repositorio original conservan su modalidad aprobada.

El experimento usa `plan: free`, sin disco persistente ni cambio a plan pago. Sus datos
de prueba pueden perderse cuando Render suspenda/reinicie/republique el proceso; no es
una instalación comercial ni una solución durable. Solo se inicializa una base nueva
aislada; una existente incompatible se rechaza, sin reparación ni migración implícita.
No incorpora funciones futuras F6/F7 ni certifica impresión física. Guía y validación:
[CLOUD_DEMO.md](CLOUD_DEMO.md). La prueba estática anterior no equivale a esta demo funcional.
