# Validación Windows F6 — CI aprobada; PC objetivo pendiente

No completar esta lista por construir en Linux o por revisar scripts. La CI Windows
Server y una PC Windows 11 limpia son evidencias diferentes; registrar cada resultado.
La prueba física de impresora de 58 mm mantiene su pendiente independiente.

## Construcción nativa

En Windows 11 x64 con Python 3.12, Node >=22 e Inno Setup 6.x:

```powershell
./packaging/build-windows.ps1
python packaging/smoke_installer.py
```

PyInstaller 6.16.0 fijado en requirements-build.txt. La PC que construye necesita esas
herramientas; la PC cliente no. El script genera onedir, inventario SHA-256/build-info y
setup candidato; incluye frontend, Manrope/OFL, licencias, IANA y migraciones.
No es release firmado: no afirmar firma de código ni desactivar SmartScreen/antivirus
para ocultar un fallo. Registrar advertencias reales. Artefactos no se versionan en Git.

Workflow windows-candidate.yml: build nativo en runner Windows, prueba silenciosa de
instalar/preparar/iniciar/importar/respaldar/restaurar/reinstalar/desinstalar con datos
temporales. PATH del ejecutable no contiene herramientas de desarrollo. Esto no prueba
una PC Windows 11 limpia ni su cuenta estándar; conservar esa diferencia en el informe.

## Prueba humana en Windows 11 limpio

Usar Windows Sandbox/VM de prueba si está disponible, sin datos del comercio ni Python,
Node, herramientas de build o servicios externos obligatorios. No instalar sobre la
PC comercial para probar. Registrar Windows/build/arquitectura, usuario estándar,
checksum del setup y capturas reales.

- [ ] Instalación por usuario sin exigir elevación innecesaria.
- [ ] Preparación explícita de DB, secreto inicial privado y alta ADMIN única.
- [ ] Arranque de acceso directo, health, navegador y una sola instancia.
- [ ] Login, empleado, producto/stock, venta, anulación y reportes sin internet.
- [ ] Importación CSV válida/incorrecta, ceros iniciales y reintento sin duplicados.
- [ ] Crear respaldo con WAL/ventas, descargar externamente e incorporar/restaurar.
- [ ] Cierre de sesiones y conservación de ventas/stock/instantáneas restaurados.
- [ ] Cierre controlado y reapertura sin servidor huérfano ni bloqueo residual.
- [ ] Puerto ocupado: no cerrar servicio ajeno ni abrir red pública.
- [ ] Permisos/espacio insuficientes y archivos corruptos: error claro sin pérdida.
- [ ] Interrupción de restore: rechazo de arranque y recuperación ADMIN explícita.
- [ ] Actualización desde instalación anterior compatible, respaldo y verificación.
- [ ] Reinstalación y desinstalación conservan datos/backups/configuración.
- [ ] ACL de carpetas privadas y escucha exclusiva en 127.0.0.1.
- [ ] Teclado/foco, contraste, texto legible, escala Windows y navegador objetivo.

F6 permanece pendiente hasta que los criterios obligatorios tengan evidencia real.
Las casillas no autorizan F7/piloto; el propietario debe aprobarlo por separado.

## Primera evidencia CI nativa — 2026-10-22

Workflow [39769757105](https://github.com/NicolasAriel32/gestion-inteligente-pos/actions/runs/39769757105),
commit 848dc3a, Windows Server 2025 build 26100, Python 3.12.10, PyInstaller 6.16.0,
Inno Setup 6.7.1. Build/instalador y 8 pasos smoke aprobados. Se descargó el ZIP y
comprobó su digest SHA-256; contiene setup .exe, build-info y windows-smoke.json.
La prueba usa perfil temporal, PATH System32 para el ejecutable, preparación explícita,
instancia única, CSV/backup/restore/reingreso, cierre, reinstalación y desinstalación.
Se amplió luego para comprobar ventas/anulación/reportes restaurados y hashes de
backups/configuración, además de DB. La ejecución ampliada se registra al terminar.

Esto demuestra ejecución Windows nativa con runtimes empaquetados, no PC Windows 11
limpia ni comportamiento con usuario/navegador/antivirus/ACL del equipo objetivo. Las
casillas humanas anteriores siguen pendientes. Artefactos CI caducan a los 7 días;
no hay release/tag/firma de código ni autorización para instalar en una PC comercial.

## Validación ampliada aprobada — 2026-10-22

Workflow [39834898033](https://github.com/NicolasAriel32/gestion-inteligente-pos/actions/runs/39834898033),
commit **b0297dc**, job 120020504265: build y 8 pasos smoke aprobados. Además de lo anterior,
registró dos ventas ficticias, anuló una, respaldó, alteró stock y restauró; comprobó
stock 2, venta por 125 centavos, anulación VOIDED e ingresos 125 centavos. Antes/después de
reinstalar/desinstalar comparó SHA-256 de DB, copia manual, copia pre-restore y archivo de
configuración. La prueba ampliada también corrió sin Python/Node en PATH del ejecutable.

Entorno: Windows Server 2025 build 26100; Python build 3.12.10, Node 22.23.3, npm 10.9.9,
PyInstaller 6.16.0 e Inno Setup 6.7.1. No son dependencias externas de la PC cliente.
Avisos de CI: acciones Node 20 ejecutadas por compatibilidad en Node 24 y deprecación
punycode; no fallaron build/smoke y no corresponden al runtime del POS.

Artefacto [F6-Windows-candidate](https://github.com/NicolasAriel32/gestion-inteligente-pos/actions/runs/39834898033/artifacts/12451205519),
setup candidato **GestionInteligentePOS-0.5.0-F6-candidate-setup.exe**, 19.395.208 bytes.
SHA-256 del setup: `cf8be1920bfd01eceea5237a2c73a500e7b7f3d70f01edcd1a64caf52714cef7`.
ZIP descargado y hash verificado; JSON de build/smoke conservados en docs/validation/f6.
Artefacto expira 2026-10-29. No se publicó release ni se declara instalación objetivo validada.

## Candidato con ayuda autorizada — instalación de prueba solicitada

PR #6 fusionado por autorización explícita en main **4b40e3f**. Incorporado a la rama
F6 candidata en **3808bd1**, producto **0.5.1**, con PRIMER_INICIO.txt y acceso a sus
instrucciones dentro del instalador. PR #7 no se fusiona ni F7 se inicia.

Build y 8 pasos smoke Windows aprobados en workflow
[39837508411](https://github.com/NicolasAriel32/gestion-inteligente-pos/actions/runs/39837508411).
[Artefacto para prueba](https://github.com/NicolasAriel32/gestion-inteligente-pos/actions/runs/39837508411/artifacts/12450694251),
setup **GestionInteligentePOS-0.5.1-F6-candidate-setup.exe**. ZIP y setup descargados y
verificados: SHA-256 setup
`9f252c195a3240e2fb57021d137d339806b1865e0a87c603b0695ebf52c8b9bf`.
Evidencia JSON windows-help-trial-* conserva versión/build, origen y resultado nativo.

El propietario tiene Codex local en Windows y realizará la prueba offline. Esta sesión
sigue conectada a Linux remoto sin PowerShell, unidad Windows ni endpoint de escritorio;
no se afirma que el POS esté instalado en su PC. Se entrega instalador descargable para
ejecutar desde una sesión local Windows. Nunca tocar datos comerciales para probar ni
desconectar redes remotamente; primera cuenta ADMIN queda a cargo de su titular.
F6 y el checklist Windows 11 limpio conservan su estado pendiente.
