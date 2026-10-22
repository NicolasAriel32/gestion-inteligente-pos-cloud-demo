# ARCHITECTURE — arquitectura del MVP local

- Versión de referencia: 0.5.1 (2026-10-22)
- Estado: núcleo F1–F5 validado localmente; distribución Windows y partes futuras pendientes.
- Referencias: PROJECT_SPEC.md, BUSINESS_RULES.md y DECISIONS.md

## Despliegue objetivo Windows (F6)
La distribución final en un equipo Windows deberá ejecutar:
- Frontend estático compilado de **React + TypeScript + Vite**.
- **FastAPI** local que sirve frontend y API REST; por defecto 127.0.0.1:8765 (solo loopback).
- **SQLite** en carpeta privada de datos; el frontend **nunca** accede al archivo directamente.

El desarrollo actual ejecuta FastAPI y Vite por separado en loopback; véase README.
No se necesita internet para las operaciones implementadas. La distribución final buscará
empaquetar todos los runtimes necesarios, sujeta a pruebas en Windows.

## Capas y dependencias
- Presentation: componentes React, vistas, estados de UI.
- HTTP/API: rutas FastAPI, esquemas Pydantic, autenticación/autorización, respuestas.
- Application: casos de uso tipados (crear venta, anular venta, ajustar stock, estadísticas).
- Domain: entidades, estados e invariantes sin acoplamiento a FastAPI/SQLite.
- Infrastructure: repositorios SQLAlchemy, migraciones, rutas de archivos, respaldo.

Dependencias hacia adentro: UI → API → Application → Domain; Infrastructure implementa puertos. No acoplar negocio al proveedor de base de datos.

## Módulos
auth, users, catalog, inventory, sales, reporting, audit, backup. Evitar servicios genéricos masivos y no introducir complejidad multiempresa prematuramente.

## API prevista (contratos a formalizar vía OpenAPI)
- POST /api/auth/login; POST /api/auth/logout; GET /api/auth/me
- GET/POST/PATCH /api/products; GET/POST /api/categories
- POST /api/stock/adjustments; GET /api/stock/movements
- POST /api/sales; GET /api/sales; GET /api/sales/{id}; POST /api/sales/{id}/void
- GET /api/reports/summary; GET /api/reports/top-products; GET /api/reports/peak-hours
- GET/POST/PATCH /api/employees
- POST /api/backups; procedimientos de restauración administrados y fuera de sesiones activas
- GET /api/health (sin información sensible)

Implementados y verificados en F2: health, auth/login, auth/logout, auth/me,
employees (GET/POST y PATCH de desactivación), además de auth/setup (GET/POST).
Implementados en F3: GET/POST /api/categories, PATCH /api/categories/{id},
GET/POST /api/products, GET/PATCH /api/products/{id}, POST /api/stock/adjustments y
GET /api/stock/movements. Contratos tipados y límites en OpenAPI; detalle en
[F3_DEVELOPMENT.md](../F3_DEVELOPMENT.md). Implementados en F4: POST /api/sales/quote,
GET/POST /api/sales, GET /api/sales/{id} y POST /api/sales/{id}/void.
F5 implementa GET /api/reports/summary con el reporte completo y consistente.
Los endpoints separados top-products/peak-hours de la API prevista se consolidan en
summary para que rankings, horas y KPIs compartan snapshot. Respaldos siguen pendientes.
Contratos de caja: F4_DEVELOPMENT.md; reportes: F5_DEVELOPMENT.md.
Contratos y errores F2: [F2_DEVELOPMENT.md](../F2_DEVELOPMENT.md).

## Seguridad local
- Credenciales únicas; contraseñas Argon2id; sesiones con expiración.
- Autorización backend en todos los endpoints.
- Si se utilizan cookies: HttpOnly, SameSite adecuado, defensa CSRF; origen y Host permitidos explícitamente.
- Escuchar exclusivamente 127.0.0.1; no aceptar orígenes arbitrarios ni interfaces de red.
- Configurar Host/CORS para mitigar acceso no autorizado desde sitios externos y DNS rebinding.
- Inicialización de ADMIN de uso único y protegida contra carreras.
- Validar entrada tipada y prohibir SQL interpolado.
- La seguridad de un equipo local también depende de permisos de Windows, mantenimiento y acceso físico.

## Operaciones de negocio
El backend fija precios, valida rol, maneja transacciones de inventario; idem-potencia con clave única por venta. SQLite no soporta SELECT FOR UPDATE: usar transacciones de escritura apropiadas (por ejemplo BEGIN IMMEDIATE), busy_timeout y pruebas de carrera. Véase PERSISTENCE.md.

## Observabilidad y calidad
- Logs locales rotativos, sin secretos ni datos sensibles innecesarios.
- pytest para backend y pruebas de integración SQLite; pruebas frontend donde apliquen.
- Documentar scripts de desarrollo, builds Windows y versiones de dependencias.
- Proteger invariantes con restricciones DB + tests + validaciones de aplicación.

## Evolución AI-native
AGENTS.md, especificaciones, decisiones y pruebas hacen el repositorio accesible a Codex/Claude Code/Cursor. En el futuro las operaciones de Application podrían ofrecerse con MCP, con permisos distintos, confirmación humana y auditoría. No implementar MCP en el MVP.

## Exclusiones técnicas iniciales
Sin Lovable, Supabase, dependencia obligatoria de cloud, sincronización distribuida, Docker requerido en cliente ni MySQL cliente. MySQL quedará como alternativa futura con adaptación y pruebas de persistencia, no migración automática.

## Concreción de seguridad F2

La API no ofrece autorregistro. La inicialización requiere secreto local temporal y
transacción BEGIN IMMEDIATE. Las sesiones son opacas, revocables y almacenadas como hashes;
cookie HttpOnly/SameSite=Strict, expiración absoluta y CSRF en escrituras autenticadas.
Origin y JSON obligatorios para login/setup; ninguna respuesta refleja secretos de validación.
Las capas HTTP, casos de uso, contratos de dominio y persistencia están separadas.
La política de recuperación no se implementa hasta decisión del propietario.

## Catálogo e inventario F3

Casos de uso con puertos tipados y adaptadores SQLite. La sesión y el rol se revalidan
dentro de la misma transacción que realiza cada escritura. ADMIN gestiona catálogo,
costos y movimientos; EMPLOYEE solo consulta activos, precio de venta y stock.
PATCH de producto no admite stock: se registra por carga inicial o ajuste con motivo.
Los ajustes usan UUID idempotente, BEGIN IMMEDIATE y auditoría atómica, sin reintentos
automáticos. Interfaz decimal exacta; API y DB conservan centavos enteros.
audit_events es el registro general; audit_log permanece como compatibilidad de identidad
sin modificar ni borrar eventos existentes. No se añadieron dependencias ni servicios.

## Caja e historial F4

Ventas por capas con SalesService, puerto transaccional y adaptador SQLite. Cotización
del servidor sin reserva; confirmación recalculada bajo BEGIN IMMEDIATE, rechazo si cambió
el contenido económico y UUID idempotente. Pedido normalizado vinculado al actor; no se
aceptan precios, totales, estado ni vendedor desde el cliente.
Venta/pago/ítems/inventario/movimientos/auditoría confirman o revierten juntos.
EMPLOYEE ve solo sus ventas, ADMIN todas y anula con motivo. La anulación repone unidades
una sola vez y conserva instantáneas. No hay endpoints para editar/borrar historia.

La interfaz persiste un intento confirmado por usuario en sessionStorage antes del envío;
no guarda credenciales ni identificadores de sesión/CSRF. Una respuesta incierta bloquea
otro cobro hasta recuperar el mismo UUID. Se valida el comprobante antes de liberar el intento.
Ticket React y CSS print local de 48 mm de contenido para papel nominal de 58 mm, con
controlador Windows/diálogo del navegador. Sin conexión directa USB/ESC-POS ni éxito físico
inferido de window.print; esa compatibilidad queda pendiente de equipo real.

## Lecturas F5

ReportingService → puerto ReportingPersistence → ReportingStore SQLite con BEGIN de
lectura explícito antes de autorizar. Sesión/rol ADMIN y todas las consultas en un snapshot
WAL. pos_sum usa enteros Python y devuelve texto decimal; nunca SUM/float para agregados.
pos_hour usa zoneinfo Buenos Aires; tzdata proporciona IANA offline donde falta en SO.
Índice 0005 por estado/fecha acota consultas; tablas previas e invariantes de escritura intactas.
Vista React diferida, AbortController al reemplazar consulta/desmontar, carga/vacío/error y
reintento explícito; importes BigInt sin Number. Sin servicios cloud ni gráficos remotos.

## Operaciones F6 candidatas

ImportService usa puerto transaccional y helper de alta F3. MaintenanceService usa puerto
MaintenancePersistence, adaptador SQLite/archivos privados, Backup API y gate asíncrono
que drena HTTP/scheduler durante restauración. Contenedor de dos miembros conocidos,
estructura canónica de migraciones, hash y límites; no rutas recibidas por API.
Runtime serve solo dist/assets/licencias/index; directorios de datos nunca estáticos.
Launcher y servidor fuente oficial comparten bloqueo de instancia; mantenimiento offline
explícito y no reparaciones silenciosas. Detalles y límites en F6_DEVELOPMENT.md.

## Ayuda local de uso (0.5.1)

HelpCenter abre diálogo nativo modal desde encabezado; contenido estático versionado en
userHelp.ts, búsqueda local por términos sin distinguir acentos/mayúsculas. No consulta
APIs, escribe storage ni realiza acciones comerciales. Filtro por rol es de presentación;
la autorización backend de todos los módulos continúa intacta. Sin dependencias/esquema
nuevos. No introduce navegación que desmonte borradores ni modifica intento de caja.
