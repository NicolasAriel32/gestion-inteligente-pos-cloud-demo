# Gestión Inteligente POS

**Este es el clon de demo funcional remota `gestion-inteligente-pos-cloud-demo`.**
Abrí [la guía para desplegar en Cloudflare y Render](docs/CLOUD_DEMO.md).
El repositorio original `NicolasAriel32/gestion-inteligente-pos` conserva la versión para PC.
La demo requiere ambos servicios: publicar solo el Worker no inicia el servidor Python.
El plan gratuito de Render usa datos efímeros; usá datos ficticios.

Sistema de gestión y punto de venta local para un kiosco o pequeño comercio argentino.
**Versión 0.5.1: identidad, catálogo, inventario, caja, historial y reportes ADMIN locales.**
F4 aprobada para integración mediante PR #4; la prueba física de impresoras de 58 mm sigue pendiente.
Versiones de producto, esquema y evidencias: [VERSIONS.md](docs/VERSIONS.md).
Diseño, contratos y resultados de F5: [F5_DEVELOPMENT.md](F5_DEVELOPMENT.md).

## Decisiones de producto

- MVP: un comercio, una sucursal, una caja y una PC.
- Funciona sin internet para las operaciones comerciales principales.
- Roles: **ADMIN** (dueño) y **EMPLOYEE** (empleado).
- Módulos: autenticación, productos, inventario, caja, historial de ventas, panel de indicadores y empleados.
- Idioma español argentino, moneda ARS, reportes en `America/Argentina/Buenos_Aires`.
- Las ventas no pueden producir stock negativo ni duplicarse por reintentos.
- No incluye facturación fiscal ARCA, pasarelas de pago, varias cajas ni agentes autónomos en el MVP.

## Arquitectura objetivo (sujeta a validación técnica)

- Frontend: React + TypeScript + Vite.
- Backend local: Python + FastAPI en loopback.
- Persistencia: SQLite + SQLAlchemy + Alembic.
- Distribución Windows: PyInstaller + Inno Setup.
- Extensiones futuras: MySQL, MCP, n8n.
- Sin Lovable, Supabase ni dependencias obligatorias de nube.

## Fuente de verdad

1. [Especificación del proyecto](docs/PROJECT_SPEC.md)
2. [Arquitectura](docs/ARCHITECTURE.md)
3. [Modelo de dominio](docs/DOMAIN_MODEL.md)
4. [Reglas de negocio](docs/BUSINESS_RULES.md)
5. [Persistencia](docs/PERSISTENCE.md)
6. [Instalación](docs/INSTALLATION.md)
7. [Roadmap](docs/ROADMAP.md)
8. [Decisiones](docs/DECISIONS.md)
9. [Criterios de aceptación](docs/ACCEPTANCE_TESTS.md)
10. [Instrucciones para agentes](AGENTS.md)

## Para Codex y otros agentes

Leer `AGENTS.md` y las especificaciones pertinentes **antes de escribir código**. No asumir que los archivos representan funcionalidades ya implementadas; cada etapa del roadmap requiere implementación, pruebas y revisión.

## Estado actual

FastAPI, React/Vite y SQLite/Alembic funcionan localmente. F2 agrega inicialización
protegida de ADMIN, sesiones y empleados. F3 incorpora categorías, productos, precios
en centavos, desactivación y ajustes de stock auditados e idempotentes, exclusivamente
por ADMIN. F4 agrega ventas atómicas/idempotentes, pagos declarados, historial,
anulación ADMIN y ticket no fiscal de 58 mm. EMPLOYEE vende y consulta sus ventas,
productos activos, precios y existencias, sin costos ni administración del catálogo.
Instalación, comandos y resultados: [F4_DEVELOPMENT.md](F4_DEVELOPMENT.md),
[F3_DEVELOPMENT.md](F3_DEVELOPMENT.md),
[F2_DEVELOPMENT.md](F2_DEVELOPMENT.md) y [F1_DEVELOPMENT.md](F1_DEVELOPMENT.md).
F5 agrega KPIs, comparación con período anterior, ranking por unidades/ingresos y ventas
por hora de Buenos Aires; excluye anuladas y mantiene instantáneas históricas.
Sin instalador ni piloto aprobado. F6 requiere autorización independiente.

## Desarrollo local

Requiere Python >=3.11 y Node >=22. Crear y activar un entorno virtual:
```sh
python -m venv backend/.venv
# Linux/macOS:
. backend/.venv/bin/activate
# Windows PowerShell: backend/.venv/Scripts/Activate.ps1
python -m pip install -e './backend[dev]'
cd backend
python -m alembic -c alembic.ini upgrade head
python -m app.bootstrap
python -m app
```

El comando bootstrap indica la ruta del secreto local; no imprime su contenido.
Abrir el archivo localmente e introducirlo en el formulario inicial. No compartirlo ni
versionarlo. Después de crear ADMIN eliminar ese archivo. No ejecutar bootstrap de nuevo
sobre una instalación ya inicializada. Para datos existentes: respaldo previo antes de migrar.

En otra terminal:
```sh
cd frontend
npm ci
npm run dev -- --strictPort
```
Abrir http://127.0.0.1:5173. Ambos servicios escuchan solo en loopback.
No se necesita un servicio cloud. Recuperación de credenciales pendiente de decisión;
no borrar SQLite ni recrear ADMIN para recuperar acceso.

## Prácticas aprendidas

El [registro de hallazgos](docs/ENGINEERING_FINDINGS.md) conserva causas, fixes y pruebas
de F2, diseño, F3 y F4. El [checklist reutilizable](docs/PROJECT_REVIEW_CHECKLIST.md) reúne
las prácticas para próximas fases y proyectos.

## Identidad visual aprobada

Manrope local y negro sobre amarillo, con superficies suaves y controles accesibles.
El diseño de acceso/empleados fue fusionado por autorización del propietario (PR #2,
merge 058a92f). F3 fue aprobada y fusionada en 3848d55; F4 conserva esa identidad.
Ver [sistema visual](docs/DESIGN_SYSTEM.md),
[validación original](FRONTEND_DESIGN_VALIDATION.md) y
[capturas reales de catálogo/inventario](docs/screenshots/f3/).

## Caja y tickets

Agregá productos, revisá el importe y elegí un medio de pago informado manualmente.
Confirmar registra venta, pago y stock juntos. Si una respuesta se pierde, la aplicación
conserva el intento y ofrece recuperar la misma venta, incluso después de recargar o
volver a ingresar. No generar otra venta para recuperar un comprobante.

Historial permite consultar/reimprimir; ADMIN puede anular con motivo, devolviendo las
unidades una sola vez. El ticket de 58 mm se imprime desde el diálogo del navegador
con el controlador de Windows. Cancelar la impresión no cancela la venta.
[Preparación y límites Global/Waggs](docs/PRINTING.md) y
[capturas/PDF reales](docs/screenshots/f4/). Compatibilidad física pendiente de modelo y prueba.

## Dashboard y reportes (ADMIN)

Abrí Reportes y consultá hoy, ayer, últimos 7/30 días o fechas personalizadas (máximo
366 días, sin futuros). Si incluye hoy, corta al instante de consulta y compara con
el mismo corte del período anterior; ambos intervalos se muestran explícitamente.
Facturación, ventas, ticket promedio y unidades excluyen todas las anuladas. Ranking
hasta 10 productos por unidades/ingresos; hora pico por transacciones, con alternativa
de facturación por hora. Sin ventas se muestra el estado vacío y la base cero no
inventa un porcentaje. Consultar actualiza los datos; no hay actualización automática.

F5 requiere migración explícita a **0005_reporting_indexes**, índice aditivo sin cambio
de tablas/historia. Sobre instalación existente, detener y respaldar de forma consistente
antes de migrar; para probar usar LOCALAPPDATA temporal. Conserva comandos locales de
arriba. Única dependencia nueva: `tzdata>=2025.2,<2027`, datos IANA para zoneinfo en
Windows, instalados junto al backend y disponibles offline. Sin servicios externos.
Contrato OpenAPI: GET /api/reports/summary. Dinero/unidades agregadas viajan como texto
decimal exacto y se formatean con BigInt; los contratos de ventas F4 no cambian.
[Criterios y evidencia](F5_DEVELOPMENT.md) · [capturas](docs/screenshots/f5/).

## Ayuda integrada

El botón **?** en la esquina superior derecha abre guías rápidas sin salir de la pantalla.
Buscá por palabras (por ejemplo «cambiar precio») o filtrá por tema y desplegá una respuesta.
Incluye carga de productos, precios, stock, caja/historial, reportes y problemas de acceso o
impresión. Las instrucciones administrativas aparecen para ADMIN; los empleados ven las
guías de su rol. Sin sesión sigue disponible la ayuda de acceso/conexión/impresión.

El contenido funciona sin internet y no ejecuta operaciones. Cerrar o presionar Escape
regresa al trabajo conservando los campos completados. No requiere dependencias ni
migraciones nuevas. [Diseño, validación y capturas](USER_HELP_DEVELOPMENT.md).
