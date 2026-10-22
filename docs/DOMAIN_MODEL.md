# DOMAIN_MODEL — vocabulario, entidades y eventos

- Versión de referencia: 0.5.1 (2026-10-22); núcleo F1–F5 implementado.
  Reporting validado localmente; dominio/hardware y piloto conservan sus pendientes.

## Lenguaje compartido
**Producto**: ítem vendible por unidades enteras.
**Stock disponible**: unidades registradas que pueden venderse ahora.
**Ajuste**: movimiento manual autorizado, nunca una venta.
**Venta completada**: transacción validada, cobro declarado y existencias descontadas.
**Venta anulada**: operación histórica conservada cuya reversión repone stock.
**Pago**: medio e importe informado por usuario; no es confirmación bancaria.
**Caja**: único puesto comercial del MVP, sin arqueo ni cierre de caja.

## Entidades mínimas
- **users**: id, username UNIQUE, password_hash, role ENUM(ADMIN, EMPLOYEE), is_active, created_at. Sin credenciales en logs.
- **categories**: id, name, is_active.
- **products**: id, code TEXT nullable UNIQUE, name, category_id FK, price_cents integer, cost_cents nullable, stock_quantity integer, minimum_stock integer, is_active, created_at, updated_at.
- **sales**: id, idempotency_key UNIQUE, user_id FK, status COMPLETED/VOIDED, total_cents, created_at_utc, voided_at_utc nullable, voided_by FK nullable, void_reason nullable.
- **sale_items**: id, sale_id FK, product_id FK, product_name_snapshot, unit_price_cents, quantity integer > 0, subtotal_cents.
- **payments**: id, sale_id FK, method CASH/TRANSFER/DEBIT/CREDIT, amount_cents. MVP un pago por venta; múltiples pagos quedan fuera.
- **stock_movements**: id, product_id FK, movement_type INITIAL/IN/ADJUSTMENT/SALE/VOID, quantity_delta (con signo), stock_before, stock_after, reference_type, reference_id, performed_by FK, reason nullable según tipo, created_at_utc.
- **audit_log**: id, actor_id FK, action, entity_type, entity_id, event_data (sin secretos), created_at_utc.

## Invariantes
- Stock jamás negativo.
- Cada subtotal = precio histórico × cantidad; total = suma de subtotales y coincide con pago declarado.
- No cambiar ítems o precio de venta completada.
- No modificar producto ya vendido mediante borrado físico.
- El estado VOIDED no retorna a COMPLETED.
- Una venta completada tiene al menos un ítem y un pago.
- No registrar saldo a cobrar, descuentos, impuestos desglosados ni pagos mixtos en el MVP.

## Eventos de dominio (descriptivos; no requiere event sourcing)
PRODUCT_CREATED, PRODUCT_UPDATED, STOCK_ADJUSTED, SALE_COMPLETED, SALE_VOIDED, EMPLOYEE_CREATED, EMPLOYEE_DISABLED.

## Secuencia
Usuario autenticado → agrega productos → confirma venta → validación server-side → transacción de venta + ítems + pago + reducción de stock + movimientos → evento de auditoría.

ADMIN anula → transacción cambia estado y registra movimiento compensatorio exactamente una vez.

## Reporting
Ventas válidas = status COMPLETED. Agregación por fecha local Buenos Aires; conservar timestamps UTC. Para “productos más vendidos” ofrecer orden por unidades o ingresos. Horas pico significa máximo número de transacciones en intervalos horarios locales, con métrica alternativa de monto.

## Evolución
Separar dominio de infraestructura para incorporar MySQL/API remota/MCP después; no modelar varias empresas ni multi-caja como funcionalidad del MVP.

## Identidad implementada en F2

`users` implementa los campos indicados, con username ASCII normalizado en la API,
rol validado por CHECK e índice parcial que permite un solo ADMIN. No se crean ADMIN por API administrativa.
`sessions`: token_hash SHA-256, user_id FK y expires_at Unix UTC; nunca token en claro en DB.
`bootstrap`: singleton id=1, token_hash nullable, expires_at y completed. El hash se elimina al consumirlo.
`audit_log`: actor_id y entity_id FK a users, action, entity_type, event_data vacío por defecto
(sin contenido libre recibido del cliente), created_at_utc. En F2 solo audita identidad.
Las entidades comerciales implementadas se precisan a continuación para F3 y F4.

## Catálogo e inventario implementados en F3

- categories incorpora name_key normalizado con casefold y UNIQUE, además de nombre y estado.
- products implementa los campos del modelo; cantidades e importes entre 0 y 2^53−1,
  comprobados en API y SQLite. Código nullable único como texto, sin perder ceros iniciales.
- stock_movements registra carga INITIAL o ajuste ADJUSTMENT, motivo obligatorio,
  actor, UTC, referencia PRODUCT/id, delta y stock antes/después. request_key UUID UNIQUE
  identifica cada ajuste manual. Los valores SALE/VOID del CHECK se reservan para el
  modelo objetivo; no hay casos de uso de venta ni anulación en F3.
- audit_events es la auditoría general, con actor_id FK users y entity_id polimórfico.
  Se copiaron los eventos históricos manteniendo IDs y contenido. audit_log conserva su
  restricción original de identidad; las escrituras de identidad actualizan ambos registros
  atómicamente. Consultar audit_events sin sumar audit_log.
- Desactivar categoría no cambia el estado de productos. No se asignan categorías
  inactivas a productos nuevos; un producto existente puede conservar su categoría.
  No hay borrado físico ni ajustes de productos inactivos.

## Caja e historial implementados en F4

sales agrega request_hash del pedido normalizado y username_snapshot, además de los
campos previstos. idempotency_key UUID UNIQUE es una identidad comercial, no de sesión.
sale_items guarda también product_code_snapshot; nombre, código y precio históricos no
cambian al editar/desactivar catálogo. payments implementa un único medio declarado y
el importe total, sin confirmación bancaria ni saldo pendiente.

La inserción del pago comprueba ítems/suma y sella su composición. Triggers impiden
editar/borrar ítems/pagos, cambiar cabecera económica, borrar venta o reabrir una anulada.
Los casos de uso completan el conjunto en una transacción; la DB no sustituye esa unidad
de trabajo para una cabecera insertada por SQL directo sin pago/ítems.
Movimientos SALE/VOID referencian SALE/id; índice parcial único por venta/producto/tipo.
Anulación total por ADMIN, con motivo no nulo, responsable y UTC. Productos inactivos
recuperan stock conservando su estado. No hay devoluciones parciales ni reportes F5.

## Reporting implementado en F5

Lectura ADMIN de COMPLETED exclusivamente, sin joins a catálogo o personas activas.
Métricas de cabecera separadas de unidades/ítems; instantáneas de la última venta válida
por producto/fecha/ID para nombrar ranking. Dos top 10 con empate por ID y 24 horas
locales; todas las horas empatadas por tickets, vacío sin pico. Sin entidad comercial
nueva: 0005 agrega un índice. Agregados en texto decimal exacto, no modifican F4.

## Operaciones locales F6 candidatas

0006 agrega csv_imports con UUID/actor/hash/IDs/UTC y maintenance_state singleton con
programación, último estado y generación. Importación solo de productos nuevos, reutiliza
alta/INITIAL/auditoría F3 en una transacción. No guarda CSV crudo ni modifica historia.
Restaurar cambia la generación que participa de fingerprints de cotización/importación,
revoca sesiones y audita, evitando reenvío automático de intentos posteriores al snapshot.
