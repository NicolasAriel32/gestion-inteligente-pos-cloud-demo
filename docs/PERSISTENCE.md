# PERSISTENCE — base de datos, transacciones y respaldos

- Versión de referencia: 0.5.1 (2026-10-22)
- Implementado: SQLite + SQLAlchemy + Alembic en una sola PC, esquema candidato 0006_local_operations.
  Respaldo y restauración siguen como diseño F6, sin implementación validada.

## Ubicación
En MVP con una misma cuenta de Windows:
%LOCALAPPDATA%\\GestionInteligentePOS\\data\\pos.db
%LOCALAPPDATA%\\GestionInteligentePOS\\backups\\
%LOCALAPPDATA%\\GestionInteligentePOS\\logs\\
%LOCALAPPDATA%\\GestionInteligentePOS\\config\\

No guardar DB en Program Files ni en el binario. Si una instalación debe funcionar entre distintas cuentas Windows, rediseñar permisos/ruta antes de prometer soporte.

## Integridad
- Habilitar PRAGMA foreign_keys=ON en **cada conexión**.
- WAL para operación normal y busy_timeout razonable.
- Transacciones breves y una política explícita de reintentos ante bloqueos.
- No compartir SQLite por unidades de red; un único escritor a la vez.
- Restricciones CHECK: stock >= 0, precios >= 0, cantidad de ítem > 0.
- Idempotency_key de venta UNIQUE; código de producto UNIQUE cuando no sea NULL.
- Claves foráneas e índices para fecha, código, usuario y relaciones.
- Moneda en centavos enteros; cantidades de inventario solo unidades enteras MVP.
- Guardar fecha/hora en UTC con zona explícita para reportes de Buenos Aires.

## Modelo lógico
Entidades y relaciones detalladas en DOMAIN_MODEL.md: users, categories, products, sales, sale_items, payments, stock_movements, audit_log. No borrado físico de registros históricos.
En F3, audit_events es el registro general y audit_log queda como compatibilidad de
identidad. F4 agrega sales, sale_items y payments sin reconstruir tablas anteriores.

## Registrar venta (una transacción)
1. Autenticar/autorizar empleado; validar solicitud y clave idempotente.
2. Abrir transacción que obtenga bloqueo de escritura antes de leer stock para decidir.
3. Si ya se usó la clave idempotente, devolver operación previa sin duplicarla.
4. Leer productos/precios actuales, validar activos y stock suficiente.
5. Calcular total en servidor en enteros y crear cabecera, ítems, pago registrado.
6. Reducir stock y crear movimientos de salida con referencia.
7. Confirmar; si algo falla: rollback completo.

No usar SELECT FOR UPDATE de PostgreSQL como si existiera en SQLite. Probar múltiples solicitudes simultáneas y doble clic.

## Anular venta (una transacción)
- ADMIN autenticado, motivo obligatorio.
- Si ya anulada: no repetir movimientos; devolver estado adecuado e idempotente.
- Registrar marca de anulación, responsable y fecha.
- Reponer exactamente lo vendido y registrar movimientos compensatorios.
- Confirmar todo o revertir todo.
- La venta permanece visible en histórico, excluida de agregados comerciales.

## Ajustar stock
ADMIN, motivo obligatorio, stock resultante >= 0, movimiento antes/después y auditoría. Usar la misma protección transaccional.

## Respaldos
- Implementar backup consistente mediante **SQLite Backup API** o equivalente probado; no copiar solamente pos.db activo en WAL.
- Respaldo manual y automático configurable, metadatos de fecha/esquema, integridad y política de retención documentada.
- Restauración con aprobación ADMIN, aplicación detenida para escritura, respaldo del estado previo y verificación de integridad al finalizar.
- Probar restauración de verdad antes del piloto.
- Un backup solo en el mismo disco NO protege contra rotura/robo: recomendar copia externa segura y documentar cómo hacerla.

## Migraciones
- Alembic versionado; respaldo previo obligatorio para despliegue cliente.
- Migrar cuando no existan ventas activas; fallos deben impedir uso con esquema incompatible.
- Distinguir reversión de **binarios** de reversión de **esquema/datos**.
- Nunca ejecutar migraciones destructivas sin plan de recuperación y aprobación humana.

## Pruebas prioritarias
Invariantes de stock, dos ventas simultáneas, idempotencia, anulación repetida, excepción en mitad de transacción, persistencia al reiniciar, FK, migración, respaldo/restauración, base corrupta, acceso denegado.

## Verificación F2 (2026-10-22)

Migración aditiva 0002_identity: users, sessions, bootstrap y audit_log. Inicialización,
altas y desactivación con auditoría se confirman o revierten juntas en BEGIN IMMEDIATE.
La desactivación elimina sesiones y se revalida antes de confirmar un login concurrente.
Los bloqueos tienen timeout de 5 segundos; si no se obtiene acceso, 503 y reintento explícito,
sin reintentar escrituras automáticamente. No se ejecuta downgrade destructivo.
Datos de prueba aislados; no se migraron ni eliminaron datos preexistentes.
En POSIX, la aplicación y Alembic protegen carpetas propias con 0700 y SQLite con 0600.
Windows usa ACL del perfil privado: su comprobación en PC objetivo queda para F6.

## Garantías comprobadas después de revisar F2

DDL y marcador de revisión se ejecutan en una misma transacción SQLite física
(BEGIN IMMEDIATE). Un fallo intermedio se revierte y permite reintentar. El proceso
rechaza iniciar si revisión, tablas o columnas requeridas no corresponden a su versión;
no se habilita health antes de validar. No hay reparación automática de instalaciones
parcialmente migradas. La autogeneración de Alembic queda bloqueada hasta disponer de
metadatos completos; continuar con migraciones manuales revisadas.
Evidencia: [ENGINEERING_FINDINGS.md](ENGINEERING_FINDINGS.md).

## Verificación F3 — 2026-10-22

0003_catalog_inventory agrega categorías, productos, movimientos y auditoría general.
No reconstruye ni elimina tablas anteriores. Upgrade desde F2 conserva exactamente
usuarios, hashes, bootstrap, sesiones y eventos existentes; una interrupción revierte
todo el DDL y permite reintentar. El arranque exige 0003 y sus tablas/columnas.

Los ajustes validan actor, existencia, estado y resultado bajo BEGIN IMMEDIATE. Producto,
movimiento y auditoría se confirman juntos. UUID único: mismo actor/datos devuelve el
movimiento previo, datos diferentes con la misma clave producen 409. La UI conserva la
clave al fallar una respuesta; no hay reintento automático. No borrar ni migrar una base
comercial para probar: todas las verificaciones de esta fase usan SQLite temporal.

CHECK valida enteros, stock no negativo, importes seguros y coherencia antes+delta=después;
FK protege categoría/producto/actor y código no nulo es UNIQUE. Concurrencia real cubre
dos ajustes de la última unidad y dos envíos de la misma clave. No prueba aún ventas,
backups/restauración ni instalación Windows. Resultados en F3_DEVELOPMENT.md.

## Caja e historial F4

0004_checkout_history es aditiva y exige arranque compatible. Pruebas de upgrade desde
F3 preservan exactamente usuarios/sesiones, catálogo, stock, movimientos y auditoría.
Interrumpir el DDL revierte el dump completo y permite reintentar; no se modifican
migraciones publicadas ni se ejecutan downgrades. Toda validación usa bases nuevas.

Confirmar venta obtiene bloqueo antes de leer sesión/productos, recalcula precios,
valida stock, crea cabecera/instantáneas/pago, descuenta stock y registra movimientos y
auditoría juntos. La clave UUID y hash del pedido evitan duplicados y reutilización con
otros datos/actor. Recuperar una venta existente ocurre antes de revalidar catálogo.
Al anular se restaura la cantidad histórica exactamente una vez; overflow o fallo parcial
revierte estado, stock, movimientos y auditoría. BEGIN IMMEDIATE serializa con ajustes F3.

CHECK limita tipo/rango de cantidades e importes y valida subtotal. El pago valida suma
antes de sellar ítems; FK y triggers preservan historia. Campos de anulación incluyen
IS NOT NULL explícito: un CHECK que evalúa NULL no rechaza por sí solo en SQLite.
No hay edición/borrado comercial de historia. Impresión es posterior al commit y solo lee;
cancelar el diálogo o reimprimir no cambia datos. Evidencia y límites: F4_DEVELOPMENT.md.

## Reporting F5

0005 solo crea sales_report_date(status,created_at_utc,id,total_cents); no reconstruye
ni edita tablas, filas o migraciones previas. Arranque exige revisión y columnas de ese
índice. Upgrade desde F4 conserva todas las filas y sesión; interrupción del CREATE INDEX
revierte índice/revisión y permite reintento sin reparar datos manualmente.
BEGIN explícito de lectura antes de autorizar fija snapshot WAL. Prueba concurrente anula
una venta entre KPIs y rankings y conserva una vista consistente; siguiente reporte ya
excluye la anulada. Índice cubriente por estado/fecha y UNIQUE(sale_id,product_id) existente.
Agregación Python exacta dentro de SQLite mediante pos_sum; salida decimal textual evita
overflow int64 y transporte JS inseguro. Sin caches ni tablas resumen que puedan divergir.

## Candidato F6

0006_local_operations agrega dos tablas, sin reconstruir ni editar migraciones previas.
CSV conserva transacción BEGIN IMMEDIATE de catálogo con movimiento/auditoría; UUID/hash
se confirma junto con todas las altas. Backup API produce snapshot consistente con WAL
activo; nunca copia pos.db a mano. Validación integrity_check/FK/esquema canónico/hash.
Restore drena solicitudes, copia previa, journal durable y Backup API al destino, sin
renombrar sobre WAL. Revalida, cambia generación, cierra sesiones y audita. Fallo ordinario
recupera previo; journal pendiente rechaza arranque hasta recuperación ADMIN explícita.
Pruebas/limitaciones de interrupción y Windows en F6_DEVELOPMENT.md y F6_OPERATIONS.md.
