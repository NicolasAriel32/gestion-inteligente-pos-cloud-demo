# F6 — Respaldo, importación y distribución

## Diseño previo — 2026-10-22

Autorización explícita en instrucción adjunta del propietario. Baseline main fb85521
(merge F5), contiene 95d2ada (F4), producto 0.5.0/esquema 0005_reporting_indexes.
Rama feat/f6-backup-import-distribution. PR #6/feat/local-user-help permanece separado;
no se incorporan sus commits ni se autoriza merge F6/release/F7.
Entorno observado: Linux x86_64, Python/Node/Chromium disponibles; no Windows conectado.
Se implementará y probará lo independiente y se conservará pendiente la instalación
limpia Windows si no se dispone de ejecución real. No se certifica por pruebas Linux.

### Diseño y decisiones del incremento

1. Respaldos: módulo maintenance por capas. SQLite Backup API a snapshot temporal privado;
   integrity_check/FK/revisión/esquema canónico, SHA-256 y manifiesto en ZIP de dos archivos
   conocidos. Publicación por rename atómico, sin copiar DB/WAL vivos. ADMIN lista/crea,
   descarga copia externa e incorpora un archivo para validar/restaurar. Sin rutas recibidas
   por HTTP, archivos acotados, sin extracción arbitraria, no secretos en logs.
   Programa automático optativo (desactivado por defecto): cada 24 h, configurable 1..168 h;
   retención 1..30 automáticos, manuales/pre-restauración nunca se borran automáticamente.
   Solo corre con aplicación abierta; al reabrir ejecuta vencido, sin prometer tareas OS.
   Errores visibles/registrados sin payloads ni contraseñas; reintento posterior, no bucle.
2. Restaurar: diálogo ADMIN con contraseña actual, verificación de esa misma cuenta en el
   respaldo y confirmación literal RESTAURAR. Rechazar otro comercio/cuenta o esquema distinto.
   Puerta de mantenimiento drena solicitudes DB y scheduler, rechaza nuevas con 503, copia
   previa obligatoria, journal durable y SQLite Backup API al destino (sin renombrar sobre WAL).
   Revalidar, revocar sesiones/bootstrap y auditar. Cambiar generación de cotización invalida
   intentos anteriores ausentes en el snapshot: no reenviar automáticamente una venta futura
   sobre historia restaurada. Fallo revierte al respaldo previo; si proceso se interrumpe,
   arranque falla cerrado y recuperación explícita con ADMIN, sin reparar silenciosamente.
3. CSV: solo alta de productos nuevos, hasta 500 filas/1 MiB UTF-8 con BOM opcional,
   separador punto y coma y cabecera fija: nombre;codigo;precio;stock_inicial;stock_minimo.
   Precio decimal ARS sin miles, coma/punto hasta 2 decimales, aritmética entera; cantidades
   enteras seguras, código string. Sin actualización de existentes, categorías/costos opcionales
   quedan para Catálogo. Previsualización con errores por fila; confirmación vuelve a parsear
   y validar dentro de BEGIN IMMEDIATE. Motivo común obligatorio para stock inicial.
   Extraer helper de alta de CatalogService para reutilizar movimiento INITIAL/auditoría.
   Nueva tabla csv_imports (0006) con UUID/hash/actor/resultado para reintento atómico, incluso
   con códigos vacíos; historial económico intacto. No se persiste CSV crudo.
4. Runtime: FastAPI sirve solo frontend/dist/assets/licencias/index conocidos; datos nunca
   bajo estáticos. Empaquetado PyInstaller onedir + Inno Setup por usuario Windows 11 x64,
   scripts de build versionados con licencias/checksums. Mutex/lock por instalación para
   arranque único, loopback 127.0.0.1:8765, browser después de health; puerto ocupado falla
   sin matar procesos. Cierre ADMIN en UI y señales controladas; cerrar pestaña no mata DB.
   Preparación/upgrade explícitos con herramienta empaquetada --prepare y confirmación;
   instalación nueva no inicia antes de migración/bootstrap. Conservar datos al desinstalar.
   Actualización manual: cerrar/respaldo/instalar/preparación explícita/salud; sin updater.

### Archivos, riesgos y aceptación

Archivos previstos: migración 0006/contrato de esquema, importación por capas, backup/restore
con gate y scheduler, servidor estático/launcher/scripts Windows, vista ADMIN Herramientas,
tests SQLite/API, runtime/E2E, documentación y capturas. Dependencias de ejecución sin cambios;
PyInstaller/Inno Setup exclusivamente build, versiones y licencias declaradas.
Riesgos: restore parcial, WAL/handles vivos, backup malicioso/corrupto, sesiones revividas,
operaciones pendientes posteriores al snapshot, import parcial/repetido, rutas expuestas,
actualización destructiva y falsas garantías Windows. Pruebas deben demostrar los casos.
Acceptance: suites F1–F5 y nuevas, fallo/reintento de migración/restauración, concurrenciaWAL,
CSV inválido/duplicado/overflow/UUID, permisos 403, exactitud monetaria, E2E sin red externa,
foco/contraste/móvil, instalación empaquetada/Windows real con evidencia independiente.
F6 solo completa si TODO pasa; versión 0.6.0 final solo tras validación completa. Mientras
falte Windows se mantiene baseline 0.5.0 como candidato en desarrollo y se informa claramente.
No datos comerciales reales, sin migraciones destructivas, sin release ni F7.


## Implementación y resultados observados — 2026-10-22

Implementados contratos `/api/imports/products/{preview,confirm}`, `/api/backups`,
settings/upload/download/restore y shutdown ADMIN. Herramientas es un módulo lazy para
ADMIN; EMPLOYEE no obtiene acceso por API. CSV reutiliza CatalogService, movimiento
INITIAL y auditoría dentro de una única transacción BEGIN IMMEDIATE; guarda UUID/hash/
actor/IDs, sin CSV crudo en SQLite. La intención incierta permanece en sessionStorage
hasta resolver con el mismo UUID, incluso tras recargar o reautenticar.

Backups usan SQLite Backup API con WAL activo, manifiesto, hash y esquema canónico exacto.
Límite candidato: snapshot 32 MiB (contenedor hasta 32 MiB + 64 KiB), CSV 500 filas/1 MiB.
No se presenta ese límite como capacidad ilimitada. Listado lee metadatos acotados;
creación, incorporación, descarga y restauración verifican contenido/integridad/esquema.
Automáticos optativos cada 24 h/retención 7 por defecto; solo con aplicación abierta.
El estado de éxito/error se expone a ADMIN; manuales y pre-restauración no se podan.

Restauración drena HTTP/scheduler, guarda copia previa y journal durable, autentica ADMIN
actual y en snapshot, restaura por Backup API y valida nuevamente. Revoca sesiones y
bootstrap y cambia generación de cotizaciones/importaciones. Una venta ausente del snapshot
con cotización anterior requiere consultar Historial y revisar otra cotización, evitando
confirmarla automáticamente contra historia retrocedida. Fallo inducido restaura estado
previo; interrupción deja arranque cerrado y recuperación explícita autenticada.

Runtime sirve frontend/Manrope/licencias locales, una instancia con lock/mutex, verificación
de nonce/health y loopback. Puerto ocupado no termina procesos ajenos. Herramientas permite
shutdown; Ctrl+C también cierra ordenadamente. Preparación/upgrade/recover son comandos
explícitos, nunca migraciones de arranque. PyInstaller/Inno Setup y CI nativa Windows están
preparados; no hay nuevas dependencias de ejecución respecto de main.

### Comandos y evidencia real

Linux x86_64; Python 3.12.14; Node 24.19.0; npm 11.9.0; Chromium 154 del sistema.
Todas las DB se crearon en directorios temporales con datos ficticios. No se migraron,
restauraron ni eliminaron datos comerciales de una PC. Las suites que usan sockets/
TestClient se ejecutaron fuera de la restricción de red del sandbox; el E2E bloquea
solicitudes externas expresamente y exige cero intentos externos/errores JS.

| Comando desde raíz salvo indicación | Resultado observado |
| --- | --- |
| backend: `.venv/bin/python -m pytest -q` | 171 aprobadas; 126.40 s |
| backend: `.venv/bin/python -m ruff check .` | All checks passed |
| backend: `.venv/bin/python -m pip check` | No broken requirements found |
| frontend: `npm run test` | 49 aprobadas; 2.65 s |
| frontend: `npm run lint` | Correcto |
| frontend: `npm run build` | TypeScript/Vite correcto; JS principal 76.67 kB gzip, Herramientas 5.07 kB gzip |
| frontend: `POS_TEST_CHROMIUM=/usr/bin/chromium POS_F6_CAPTURE_DIR=../docs/screenshots/f6 npm run test:e2e` | 1 flujo F1–F6 aprobado; última ejecución 35.8 s |
| `backend/.venv/bin/python packaging/build.py` | Paquete nativo Linux generado, aproximadamente 62 MiB; PyInstaller 6.16.0 |
| `backend/.venv/bin/python packaging/smoke_bundle.py` | 5 pasos aprobados con PATH vacío en el ejecutable hijo |
| `backend/.venv/bin/python scripts/benchmark_f6.py` | 500 productos/1.000 ventas reales API, reporte/restauración comprobados |

171 backend + 49 frontend + 1 E2E = **221 casos distintos aprobados**. Smoke empaquetado
y benchmark se informan aparte, sin contarlos como casos nuevos de esas suites.
El smoke preparado/importó/cobró/respaldó/alteró/restauró y comprobó stock 2 e ingresos
125 centavos, instancia única y cierre controlado sin Python/Node disponibles en PATH.
No se infiere independencia de todas las bibliotecas Linux ni compatibilidad Windows.

Benchmark de una ejecución sintética, no SLA ni capacidad de PC piloto: DB 1.142.784 bytes;
preview 29.15 ms, importación atómica 202.80 ms, reporte 10.79 ms, backup 20.89 ms,
restauración 565.44 ms incluyendo reautenticación ADMIN. Reporte contrastado con 1.000
ventas y 12.505.000 centavos. Evidencia JSON en docs/validation/f6. No se extrapola a
multi-PC, millones de ventas ni bases mayores al límite de respaldo.

### Revisión de seguridad, estructura y experiencia

- Backend revalida rol/sesión/CSRF, valores, hash, UUID y duplicados. Credenciales no se
  reflejan en errores ni se guardan con intentos CSV. ZIP restringe miembros/tamaño,
  rechaza enlaces y esquema adicional; no extrae rutas recibidas del usuario.
- Pruebas reales incluyen escritor concurrente/WAL, rollback de importación/auditoría,
  UUID simultáneo, restauración fallida y recuperación con contraseña incorrecta/correcta.
  Migración 0006 aditiva preserva F5/sesión, revierte DDL interrumpido y reintenta; las
  migraciones publicadas 0001–0005 y documentos históricos F1–F5 no se reescriben.
- Dominio CSV parsea valores exactos, aplicación coordina alta transaccional y adapters
  encapsulan SQLite/archivos/runtime. Mantenimiento concentra coordinación de archivos y
  transacciones; gate evita acceso concurrente durante restore y espera scheduler al cerrar.
- E2E comprueba flujo ADMIN/EMPLOYEE, teclado/foco, axe, contraste y movimiento reducido,
  ancho móvil y cero solicitudes externas. Capturas nuevas reales escritorio/móvil en
  docs/screenshots/f6: vista previa CSV y respaldos. Revisión visual de los PNG realizada;
  selector de archivo y pluralización ajustados a español. Contraseña de restore no aparece
  en capturas. Permanece Manrope local y amarillo/negro de identidad visual.
- SQLite conserva una caja local/una instancia. Importación acotada, timeout de snapshot
  y validación, límites de cuerpos HTTP y bundle lazy contienen costo; no es una garantía
  de escalabilidad horizontal ni de restauración de archivos de origen no confiable.

### Incidencias reales y resolución

1. Primera parametrización de CSV de 1 MiB generó ID pytest mayor al nombre de archivo
   permitido: error de setup, no fallo de producto. Se fijaron IDs cortos explícitos.
2. Primer test de runtime falló por puerto en TIME_WAIT tras cerrar. POSIX usa
   SO_REUSEADDR y Windows SO_EXCLUSIVEADDRUSE; posterior conjunto pasó 28 pruebas.
3. Restricción del sandbox dejó TestClient esperando sin completar. Se terminaron solo
   los procesos de prueba identificados y se ejecutaron con permiso de sockets; no se
   interpreta esa espera como prueba aprobada ni se altera seguridad del producto.
4. Se corrigió advertencia Pydantic por campo schema usando alias schema_revision.
   Persisten avisos previos Starlette/httpx y alias Pydantic en una prueba concurrente;
   no produjeron fallos ni justifican actualizar dependencias fuera de alcance.
5. Revisión de portabilidad detectó conexiones SQLite no cerradas al salir de `with` y
   fsync de archivo read-only: ahora closing y descriptor writable. Linux pasa; Windows
   necesita su propia evidencia. Journal usa publicación durable por SO.

Resultados finales sin fallos de suites ejecutadas. Los intentos iniciales fallidos quedan
registrados arriba. Evidencia Windows y publicación se agregan a continuación cuando
existan; no confundir configuración del workflow con ejecución aprobada.

### Pendientes que impiden cerrar F6

PC/VM Windows 11 limpia no disponible en este entorno Linux. Falta demostrar instalación,
actualización compatible, ACL, recuperación/interrupción y uso sin herramientas de desarrollo
según docs/WINDOWS_VALIDATION.md. Una CI Windows Server puede aportar build/smoke nativo,
pero no reemplaza esa lista. Se conserva producto 0.5.0 candidato; no se declara 0.6.0
validada, F6 completa, piloto, producción ni impresión física aprobados. PR #6 de ayuda
sigue separado. No se autoriza merge, release ni F7.

## Aclaración del propietario durante la entrega — 2026-10-22

Actualización siempre voluntaria: nunca bloquear arranque por versión nueva disponible,
antigüedad ni falta de conexión. El propietario podrá usar un programa separado para
actualizar manualmente si lo decide. La implementación no contiene consulta remota,
caducidad ni requisito de actualización. Se documenta en ADR-015 y AGENTS; los controles
locales de integridad/esquema permanecen para proteger datos. No se agrega un actualizador
externo sin un alcance posterior explícito.

## Primera construcción y ejecución Windows reales

El workflow 39769757105 (848dc3a) pasó en Windows Server 2025/26100, Python 3.12.10,
PyInstaller 6.16.0, Inno Setup 6.7.1: generó setup Windows .exe y completó 8 pasos del
smoke de instalador con PATH System32. ZIP descargado y checksum contrastado con GitHub.
Esto ya es evidencia Windows nativa; no transforma la prueba pendiente en Windows 11
limpio en una aprobación. Detalle y ejecuciones posteriores: docs/WINDOWS_VALIDATION.md.

## Cierre de evidencia y publicación candidata

- Rama publicada feat/f6-backup-import-distribution; commits 848dc3a y b0297dc.
  [PR #7](https://github.com/NicolasAriel32/gestion-inteligente-pos/pull/7) abierto en borrador
  hacia main fb85521. No se fusionó; PR #6 de ayuda permanece separado.
- Windows ampliado aprobado en workflow 39834898033/commit b0297dc: 8 pasos smoke,
  ventas/anulación/reportes restaurados y hashes DB/backups/config conservados después
  de reinstalación/desinstalación. Se descargó artefacto y verificaron hash ZIP y setup.
  Build Windows produjo setup 19.395.208 bytes; evidencia JSON y SHA-256 en
  docs/validation/f6 y docs/WINDOWS_VALIDATION.md. No se publica release.
- Código de aplicación final conserva pruebas Linux 171+49+1 aprobadas. Cambios posteriores
  al conjunto completo: refinamientos de journal/handles cubiertos por 23 focalizadas,
  E2E y paquetes; selector en español cubierto por frontend build/E2E; ampliación del
  harness Windows cubierta por ejecución CI real. No se suman repeticiones al total.
- Estado implementado: backups/restore/CSV/runtime/instalador/actualización manual.
  Probado: Linux y Windows Server nativo, con alcance descrito. Fallos iniciales corregidos
  y preservados en este documento; sin fallos finales de suites/build/smoke ejecutados.
  Bloqueado el cierre de F6 por falta de PC/VM Windows 11 limpia y validación humana del
  checklist objetivo. Impresora física 58 mm continúa pendiente. Versión final 0.6.0
  diferida por esa validación; siete fuentes mantienen 0.5.0 candidato. F7 no iniciada.

## Integración de ayuda aprobada y preparación de instalación — 2026-10-22

El propietario autorizó PR #6 y pidió instalar para una prueba offline. Se fusionó #6
en main 4b40e3f; esto no autoriza fusionar #7 ni iniciar F7. Se incorpora el nuevo main
a la rama candidata para que el instalador incluya ayuda. Resolver conflictos conservando
ambos módulos y evidencia histórica; baseline producto pasa a 0.5.1 de main, sin declarar
0.6.0/F6 validada. Revalidar frontend/E2E/health y build/smoke Windows; datos temporales.
Esta sesión continúa en Linux remoto sin acceso al escritorio Windows del propietario;
preparar artefacto descargable y procedimiento de ejecución local, sin afirmar instalación
en esa PC ni desconectar redes del equipo remoto.

Resultado de integración autorizado: 54 Vitest aprobadas (3.14 s), lint/build correctos;
24 pruebas focalizadas backend health/operaciones aprobadas (23.94 s), Ruff/pip check
correctos; E2E completo ayuda + F1–F6 aprobado (40.2 s), cero solicitudes externas.
Metadata editable reinstalada sin dependencias nuevas; siete fuentes coinciden 0.5.1,
lockfile idéntico a main con ayuda y documentos históricos F1–F5/ayuda intactos.
Se incluye PRIMER_INICIO.txt dentro del instalador y un acceso al documento. Build y
smoke Windows nuevos deben ejecutarse antes de entregar el artefacto combinado.
No se ejecutó una instalación en la PC Windows del propietario desde este entorno.

Build/smoke del candidato combinado 0.5.1 aprobados: workflow 39837508411, código 3808bd1,
8 pasos Windows nativos. Artefacto 12450694251 descargado, hash ZIP y setup contrastados.
Incluye ayuda PR #6 aprobada y primeros pasos locales. Resultados JSON Windows conservados
sin reemplazar evidencia previa. Instalación en la PC del propietario bloqueada por
ausencia de endpoint Windows en esta sesión; no es un fallo del instalador ni se declara
realizada. Se entrega artefacto para continuar en Codex con ejecución local Windows.
