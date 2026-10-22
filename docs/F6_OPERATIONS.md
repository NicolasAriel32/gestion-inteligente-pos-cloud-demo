# Operaciones locales F6 — candidato en desarrollo

F6 no se declara completa: consultar F6_DEVELOPMENT.md y la validación Windows pendiente.
PR #6 es ayuda, no esta fase. Estos procedimientos no autorizan restaurar datos reales
sin aprobación del ADMIN. Usar primero una instalación y datos ficticios aislados.

## Respaldar

ADMIN → Herramientas → Crear respaldo ahora. La copia usa SQLite Backup API y verifica
integridad, FK, revisión, estructura y hash. Luego Descargar permite guardar el archivo
.posbackup en un medio externo privado. Contiene datos del comercio y hashes de acceso;
no lo publiques ni lo envíes a servicios públicos. El hash detecta daño, no certifica
la procedencia: usá solo copias de confianza.

Automáticos: desactivados inicialmente. Se pueden activar, elegir 1..168 horas y retener
1..30 copias (valores iniciales 24 h/7). Solo funcionan con la aplicación abierta; el
servicio comprueba vencimiento cada 30 s, también después de reabrir. Un fallo no borra
la última copia válida ni se presenta como éxito. Revisá Último respaldo automático y
el mensaje de error. Manuales, incorporados y previos a restauración/upgrade no se
borran por esa retención. Listado muestra los últimos 100; no es un backup de la PC.

Límite actual: snapshot SQLite de hasta 32 MiB; CSV hasta 1 MiB. La aplicación debe
informar rechazo al superar el límite. Revisar volumen/retención antes del piloto:
no se promete almacenamiento ilimitado ni tiempos medidos en una PC aún no probada.

## Restaurar

1. Terminá y comprobá ventas/importaciones pendientes de todas las personas/pestañas.
2. Cerrá el trabajo que use la instalación. No ejecutes otros programas que abran la DB.
3. En Herramientas elegí Preparar restauración en la copia correcta. Un respaldo externo
   primero se incorpora como archivo .posbackup; incorporarlo no cambia la base.
4. Revisá fecha: se reemplazan usuarios, productos, stock e historia por ese estado.
5. Escribí la contraseña ADMIN y RESTAURAR; revisá el diálogo y confirmá.
6. Se bloquean solicitudes DB nuevas, se terminan las activas y se crea una copia previa.
   Se restaura con SQLite Backup API, se verifica y se cierran todas las sesiones.
7. Ingresá de nuevo y comprobá catálogo, stock, ventas/anulaciones y reportes.

La cuenta ADMIN y su contraseña deben ser válidas tanto en la base actual como en la
copia; no se admite otra cuenta/comercio ni un esquema distinto. No sustituye recuperación
de contraseña. Una restauración cambia la generación de cotizaciones/importaciones:
un intento posterior al respaldo ausente en su historia exige revisión nueva, no se cobra
por reenvío automático. Consultá Historial y conciliá cobros físicos antes de confirmar.

Si ocurre un fallo ordinario, se intenta recuperar la copia previa y se exige reingreso.
Si queda journal de interrupción, no se habilita el servidor. Cerrá la aplicación y usá
el acceso Recuperar restauración interrumpida o:

```powershell
& "$env:LOCALAPPDATA\Programs\GestionInteligentePOS\GestionInteligentePOS.exe" --recover-restore
```

Exige RECUPERAR y credenciales ADMIN del estado previo. Vuelve explícitamente a la copia
previa a la restauración interrumpida, verifica y revoca sesiones. No borres el journal,
WAL, tablas ni archivos para forzar arranque. Si la copia previa está dañada/inexistente,
conservá todos los archivos y pedí asistencia; no hay reparación silenciosa.

## CSV de productos nuevos

UTF-8, BOM opcional, punto y coma, cabecera exacta y máximo 500 filas:

```csv
nombre;codigo;precio;stock_inicial;stock_minimo
Alfajor;0000123;1250,50;12;2
Agua;;900.25;6;1
```

Nombre requerido 1..160, código opcional hasta 64; conserva ceros. Precio ARS sin miles,
coma o punto y hasta dos decimales. Cantidades enteras no negativas, importes/cantidades
hasta 2^53−1. No se aceptan códigos existentes/repetidos. No actualiza productos,
precios ni categorías existentes: gestionar después desde Catálogo. Costo/categoría
quedan vacíos; stock inicial genera movimiento INITIAL con motivo, actor y auditoría.

Elegí Archivo CSV, revisá vista previa/errores y Motivo de la carga (3..240). Revisar
importación y confirmar crea todo junto o nada. Backend vuelve a validar dentro de
BEGIN IMMEDIATE. Si se pierde la respuesta, conservá la pestaña; Reintentar la misma
importación recupera su UUID después de recargar/reingresar con la misma cuenta.
No elijas otro archivo para resolver una respuesta incierta. Si cerraste definitivamente
la pestaña o borraste su almacenamiento, consultá Catálogo antes de volver a importar.

## Preparación y actualización manual

En desarrollo se conservan README y Vite separados. Usar LOCALAPPDATA temporal en pruebas:

```powershell
python -m app.runtime --prepare
python -m app.runtime --no-browser
```

En instalación empaquetada no se necesitan esos runtimes externos: usar los accesos
del menú Inicio o GestionInteligentePOS.exe. El programa --prepare pide PREPARAR antes
de crear/actualizar. Si ya hay ADMIN, pide su contraseña y crea respaldo previo antes
de migrar. No corre mientras el proceso oficial mantiene el bloqueo de instalación.
En una instalación nueva indica el archivo local del secreto inicial (no lo imprime).
Abrilo privadamente, creá ADMIN en el navegador y eliminá ese archivo al terminar.
Si el secreto pendiente venció, --renew-setup lo renueva solo antes de inicializar ADMIN.

Actualización: descargar paquete de origen confiable, verificar SHA-256 publicado,
crear/guardar respaldo, Cerrar aplicación desde Herramientas, instalar sobre el mismo
directorio, usar Preparar o actualizar base local y comprobar salud/datos al iniciar.
Si no se puede respaldar/migrar/verificar, detener actualización y conservar instalación
anterior/copia. Las migraciones son explícitas y transaccionales; no forzar revisión.
No reemplazar ejecutables con el servidor abierto. El instalador rechaza la instancia
activa; no termina procesos ajenos.

Volver a un binario anterior no revierte esquema. Una copia pre_upgrade puede tener
otra revisión y no se restaura con el binario nuevo: requiere un procedimiento compatible
revisado. No se promete rollback de versiones no probado. No hay actualizador silencioso.

Desinstalar elimina binarios/accesos, conserva data/backups/config del perfil privado.
Reinstalar no recrea ADMIN ni borra datos. Cerrar solo el navegador no detiene el proceso;
ADMIN usa Cerrar aplicación. En desarrollo usar Ctrl+C en el servidor.

## La actualización es opcional

La versión instalada y compatible sigue funcionando aunque haya una más reciente.
El arranque no exige comprobar internet, descargar paquetes ni actualizar por antigüedad.
Solo el propietario decide cuándo reemplazarla, manualmente o con una herramienta externa
separada si lo desea. F6 no incluye ese programa actualizador ni actualización silenciosa.
Si decide cambiar los binarios, el procedimiento previo con respaldo y preparación
explícita de la base sigue siendo obligatorio para proteger sus datos.
