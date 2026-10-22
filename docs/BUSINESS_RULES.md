# BUSINESS_RULES — reglas verificables del POS

Versión de referencia 0.5.1 (2026-10-22). Cada regla tiene ID estable; toda modificación
debe actualizar pruebas y registro de decisiones. Las reglas de reportes están implementadas en F5;
la matriz de aceptación diferencia evidencia ejecutada y objetivos.

| ID | Regla | Garantía |
| --- | --- | --- |
| BR-001 | Sin stock suficiente no se vende | Rechazar venta sin cambios en DB |
| BR-002 | Stock siempre no negativo | CHECK en DB + validación transaccional |
| BR-003 | Empleado no gestiona catálogo ni stock | Autorización backend deniega |
| BR-004 | Solo ADMIN anula ventas | Permisos verificados en servidor |
| BR-005 | Cada venta se registra una vez | Idempotency_key UNIQUE y respuesta estable |
| BR-006 | Precios y totales los define servidor | Ignorar montos manipulados en UI |
| BR-007 | Venta atómica | Venta, ítems, pago, stock, movimientos todo-o-nada |
| BR-008 | Anulación idempotente | Una reversión de stock por venta |
| BR-009 | Historial inmutable | No borrar ventas ni alterar precios históricos |
| BR-010 | Reportes solo de ventas COMPLETED | VOIDED excluidas de KPIs |
| BR-011 | Productos usados se desactivan | No borrado físico que rompa historial |
| BR-012 | Acciones sensibles auditadas | Usuario, acción, fecha y motivo cuando aplica |
| BR-013 | No hay autorregistro público | Solo inicialización protegida y ADMIN crea empleados |
| BR-014 | No sobreventa concurrente | Una sola validación-escritura serializable por SQLite |
| BR-015 | Operación esencial sin internet | Ningún servicio remoto es dependencia del POS |
| BR-016 | Pago declarado no equivale a pago verificado | Sin integración financiera automática |

## Política de cantidades y dinero
- Unidades: enteros positivos en venta; producto no fraccionable en MVP.
- ARS: enteros de centavos, cálculo exacto. No usar float binario para importes.
- Precio no negativo; total igual a suma de ítems; un medio de pago por venta.
- Códigos como strings (preservar ceros a la izquierda).
- Concreción F3: cantidades e importes de catálogo en 0..2^53−1 para intercambio exacto
  con JavaScript; delta de ajuste entero no cero dentro del mismo rango con signo.
  La UI convierte texto decimal mediante aritmética entera, sin multiplicación de floats.

## Condiciones críticas
- Producto inactivo no se puede añadir a nuevas ventas.
- Producto activo debe tener precio actual válido.
- Stock manual se modifica solo con motivo, usuario y movimiento.
- Venta vacía no se acepta.
- Fallo a mitad de transacción no deja operación parcial.
- Cuando dos operadores/sesiones intentan consumir el último producto, solo las solicitudes compatibles con el stock disponible se confirman.

## Reportes
- Calendario en zona America/Argentina/Buenos_Aires.
- “Hoy” considera fecha local; no fecha UTC directa.
- Anulaciones excluidas de todas las métricas comerciales y ranking.
- Ticket promedio = ingresos de ventas válidas / cantidad de ventas válidas; si no hay ventas, mostrar 0 o “sin ventas” con claridad.
- Horario pico por número de tickets; permitir visualizar facturación por franja sin confundir ambas métricas.

## Criterio humano
Solo ADMIN valida anulaciones y restauraciones. Ningún agente de IA tiene permiso de ejecutar operaciones comerciales críticas en MVP. Excepciones de negocio nuevas requieren cambiar primero esta spec y sus pruebas.

## Concreción de caja F4

Cotización no reserva stock. Confirmar recalcula precio en servidor, exige revisar si
cambió y registra un único pago por el total. Reintentar el mismo UUID/pedido recupera
la venta existente; no crea otra ni valida de nuevo el catálogo histórico.
Una anulación total conserva instantáneas y repone cantidades una sola vez, incluso
si el producto está inactivo. Otro motivo en una anulación repetida no cambia el original.
Imprimir/reimprimir es lectura posterior: cancelar el diálogo no anula ni duplica la venta.

## Concreción F5

Períodos locales semiabiertos, corte en ahora si incluyen hoy; anterior desplazado la
misma cantidad de días calendario y con el mismo corte local. Fechas de 2000..2099,
1..366 días sin futuros. Agregados enteros exactos sin cota JS/int64; JSON decimal como
texto. Ticket promedio al centavo y porcentajes a centésimas, mitad alejándose de cero;
comparar promedios usa fracciones sin redondeo previo. Base cero: sin porcentaje salvo
ambos valores cero (0 %). Detalle/contratos en F5_DEVELOPMENT.md y ADR-012.

## Concreción candidata F6

Solo ADMIN importa, respalda y restaura. Importación todo-o-nada/idempotente por UUID,
actor, contenido/generación y motivo; stock inicial con movimiento y auditoría. CSV no
actualiza existentes. Restauración requiere contraseña vigente en ambas copias y texto
RESTAURAR, drena solicitudes y guarda estado previo; interrumpida falla cerrada y necesita
recuperación explícita autenticada. No cambia reglas de venta/anulación ni autoriza F7.
