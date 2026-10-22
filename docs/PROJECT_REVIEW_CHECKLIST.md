# Checklist reutilizable de revisión técnica

Plantilla para adaptar al inicio del próximo proyecto y antes de cerrar una fase.
No marcar una comprobación como realizada sin registrar comando, entorno y resultado.

## Persistencia y migraciones

- [ ] Confirmar el comportamiento transaccional real del driver y la base objetivo.
- [ ] Probar instalación nueva, upgrade desde la revisión anterior y reaplicación.
- [ ] Inyectar un fallo a mitad del DDL; verificar esquema y revisión desde otra conexión.
- [ ] Demostrar rollback y reintento sin borrar datos ni editar marcadores de versión.
- [ ] Asegurar que metadatos y esquema real coincidan; si no hay modelo completo,
  bloquear autogeneración y comprobar que no escriba archivos ni altere la DB.
- [ ] Revisar manualmente cualquier propuesta DROP/DELETE y mantener política de respaldos.

## Arranque y disponibilidad

- [ ] Declarar la revisión y estructura mínimas que acepta cada versión de la aplicación.
- [ ] Probar rechazo de base vacía, anterior, futura e incompleta antes de habilitar endpoints.
- [ ] Comprobar que el rechazo conserva datos, libera recursos y muestra un error sin secretos.
- [ ] Evitar reparaciones o migraciones implícitas que el usuario no pueda revisar.

## Cierre verificable

- [ ] Mantener pruebas de permisos, concurrencia y rollback cuando dependen de la DB real.
- [ ] Ejecutar tests, lint, build y comunicación real local requeridos por la fase.
- [ ] Revisar escenarios negativos: que pase el flujo habitual no basta para cerrar la fase.
- [ ] Registrar hallazgos con causa, reproducción, fix, regresión y limitaciones comprobadas.
- [ ] Verificar rama, diff, commits remotos y conservación de ramas fuera del alcance.
- [ ] Comparar versiones backend/API/frontend/raíces del lockfile y metadata instalada;
  actualizar specs vigentes sin reescribir evidencia histórica ni validar pendientes por fusión.

## Dinero, inventario y ampliación de módulos

- [ ] Probar decimales representativos y límites JSON/JavaScript/DB sin aritmética float.
- [ ] Verificar CHECK/FK con SQL directo además de DTO, incluyendo históricos antes/después.
- [ ] Comprobar permiso dentro de la transacción que modifica stock y registra auditoría.
- [ ] Probar última unidad concurrente, mismo UUID concurrente, clave reutilizada con otros
  datos y rollback por fallo al registrar auditoría, usando SQLite real y bases aisladas.
- [ ] Revisar FKs de auditoría con actor y entidad de IDs distintos al ampliar dominios.
- [ ] Probar upgrade con datos de la fase anterior y conservar sus sesiones/eventos.

## Interfaz con navegación y consultas

- [ ] Probar selección repetida y recarga, sin bucles ni pérdida de historial visible.
- [ ] Comprobar que avisos, errores y foco pertenezcan a la sección actual.
- [ ] Esperar estados positivos en E2E y navegar explícitamente tras reautenticar;
  no inferir montaje por ausencia de controles ni exigir una sección no contratada.
- [ ] Revisar capturas reales de escritorio/móvil además de axe y desbordamiento.

## Confirmación comercial e impresión

- [ ] Cortar la respuesta después del commit y recuperar la misma operación tras recargar
  y reautenticar; bloquear otra venta mientras sea incierta, sin reintentos automáticos.
- [ ] Validar el comprobante recibido antes de liberar la identidad comercial del intento.
- [ ] Probar campos NULL en CHECK compuestos y precisar invariantes entre tablas.
- [ ] Verificar instantáneas e inmutabilidad mediante SQL directo y API, con fallos parciales.
- [ ] Separar venta registrada de impresión: cancelar/reimprimir no registra otro pago/stock.
- [ ] Probar nombre/código largos, ancho efectivo de PDF y controlador/dispositivo reales;
  no certificar hardware a partir de window.print o de una marca.
- [ ] Diagnosticar selectores de E2E con roles/snapshot y tiempos acotados, sin ampliar
  esperas para ocultar fallos ni suprimir errores de tipado/lint.

Origen: [hallazgos H-F2-001 a H-F2-003](ENGINEERING_FINDINGS.md). Adaptar a la arquitectura
real del nuevo proyecto; no trasladar comandos o garantías de SQLite a otro motor sin probarlos.
Ampliado con los hallazgos H-UI, H-F3 y H-F4 del mismo registro.

## Reporting y agregados (incorporado en F5)

- [ ] Probar sumas por encima de int64 y JS seguro además del límite por fila; evitar
  float/total de SQLite, truncamientos y conversiones a Number para dinero.
- [ ] Separar agregados de cabecera e ítems para impedir duplicación al unir tablas.
- [ ] Comparar fracciones exactas antes de redondear promedio/variaciones; definir base cero.
- [ ] Declarar intervalos semiabiertos, timezone y mismo corte en comparación de parciales;
  probar día/mes/año/bisiesto, vacíos y anuladas en ambos períodos.
- [ ] Fijar snapshot explícito y confirmar un escritor entre consultas para probar aislamiento.
- [ ] Usar instantáneas históricas sin depender de catálogo/personas activas.
- [ ] Revisar plan de búsqueda real e índices globales, no asumir útil un prefijo por usuario.
- [ ] Probar fallback IANA donde el SO no incluye zonas; no inferir validación Windows.
- [ ] Revisar padding/altura de paneles con pocos datos y capturas de carga/error/vacío/datos.

Aplicación concreta de esta plantilla a F5 y comandos/resultados: F5_DEVELOPMENT.md.


## Respaldo, importación y distribución (incorporado en F6)

- [ ] Probar SQLite Backup API con WAL activo/escritor concurrente; no copiar DB sola.
- [ ] Cerrar conexiones realmente y comprobar handles/replace/fsync en SO objetivo.
- [ ] Verificar checksum, integridad, FK, revisión y esquema, tamaños y miembros ZIP.
- [ ] Drenar escritores/scheduler, guardar estado previo y journal durable antes de restore.
- [ ] Fallar cerrado tras interrupción; recuperación explícita autenticada, sin bypass.
- [ ] Revocar sesiones/bootstrap e invalidar intenciones ausentes tras retroceder historia.
- [ ] CSV: preview sin escritura, backend revalida, dinero exacto/códigos texto, rollback
  completo e identidad estable tras respuesta perdida y recarga, incluso sin códigos.
- [ ] Retención solo automática; manuales/pre-restore/externos permanecen; fallo visible.
- [ ] Runtime loopback/una instancia, puerto ocupado sin matar ajenos, cierre sin huérfanos.
- [ ] Preparación/migración explícita y datos fuera de binarios; reinstalar/desinstalar
  conservan DB, configuración y backups, con pruebas nativas reales.
- [ ] Distinguir build Linux, CI Windows Server y PC Windows 11 limpia; no cerrar fase
  ni subir versión final por revisar scripts. Registrar dependencias/licencias/checksum.

Aplicación concreta y resultados F6: [F6_DEVELOPMENT.md](../F6_DEVELOPMENT.md).
Las casillas son plantilla reutilizable; el estado de entrega lo define ROADMAP.

## Ayuda y documentación integrada

- [ ] Mantener pasos y nombres de controles alineados con las pantallas disponibles.
- [ ] Distinguir guías por rol y explicación de permisos; no presentar funciones futuras disponibles.
- [ ] Comprobar que consultar ayuda no envía escrituras ni pierde formularios/intentos pendientes.
- [ ] Probar búsqueda/filtro/vacío, teclado/foco, scroll interno y capturas del viewport del diálogo.
