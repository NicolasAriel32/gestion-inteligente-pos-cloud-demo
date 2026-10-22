# Identidad visual — Gestión Inteligente POS

Dirección C aprobada por el propietario: comercial y enérgica, profesional y cercana.
Aplicada a configuración inicial, ingreso y empleados; extendida en F3 a catálogo,
categorías y ajustes de inventario, y en F4 a Caja, Historial y comprobante no fiscal.
F5 extiende la identidad a Reportes con datos reales.

## Color y contraste

| Token | Color | Uso |
| --- | --- | --- |
| ink | #171714 | Texto, títulos, bordes principales y botones primarios |
| yellow | #FFD633 | Fondo e identidad; texto sobre botón negro |
| surface | #FFF3B0 | Paneles y listas para lectura prolongada |
| field | #FFF9DC | Campos y avisos de éxito |
| muted | #514924 | Texto de apoyo |
| border | #81723C | Bordes de campos y botones secundarios |
| line | #C6B35E | Separadores decorativos |
| error | #762317 | Texto de error; acompañado por icono y mensaje |

No comunicar un estado solo con color. Activo/inactivo se distingue con texto e indicador.
Comprobar contraste AA de texto (4.5:1 normal, 3:1 grande) y 3:1 para límites de controles.
Los separadores decorativos no representan el único límite de un control.
La validación automatizada de contraste se complementa con revisión visual; no constituye
una certificación integral de accesibilidad.

## Tipografía local

Manrope variable 200–800, normal, sin síntesis. Peso 800 en títulos, 750 en acciones,
650 en indicadores y 400–500 en lectura. Usar cifras tabulares en contadores.
Escala: título de bienvenida 38–64 px; título de equipo 28–40 px; títulos de panel 20–27 px;
texto principal 13–17 px; ayudas y metadatos 10–12 px. En móvil, inputs de 16 px.

Fuente versionada: frontend/src/assets/fonts/Manrope-latin-variable.woff2, 24 836 bytes.
Origen: @fontsource-variable/manrope 5.3.0, subconjunto latino (incluye español).
Licencia SIL OFL 1.1 en frontend/public/licenses/Manrope-OFL.txt (copiada a dist/licenses al compilar); autoría Manrope Project Authors.
SHA-256: a30ddcd349703aff7464c34bef3fffdff405ee50c113440d7c8693c02d210972.
Se importan archivos locales mediante @font-face y Vite los incluye con hash en el build.
No se carga Google Fonts, CDN ni recursos remotos durante la operación.
El nombre interno que Chromium informa es Manrope ExtraLight; corresponde a la instancia
base de la fuente variable. La familia CSS es Manrope y el título selecciona el eje de peso 800.

## Composición y espaciado

Fondo amarillo; encabezado con marca, conexión real y cierre de sesión cuando corresponde.
Inicio/configuración: dos columnas en escritorio, una en pantalla pequeña. Gestión:
lista y formulario en paralelo, apilados por debajo de 760 px. Sin tarjetas de métricas ficticias.
Espaciado base de 4 px; separaciones habituales 8/12/16/24/32/48. Paneles de 16 px de radio;
campos y botones de 8 px. Controles de al menos 44 px de alto; inputs y acción principal, 48 px.
El contador de empleados se calcula a partir de las cuentas reales devueltas por la API.
El monograma gi. es un recurso tipográfico local de interfaz; no implica registro de marca.

## Componentes y estados

- Button: variantes primary, secondary y quiet. Disabled y aria-busy durante operaciones.
- Field: etiqueta visible, ayuda vinculada por aria-describedby, autocomplete adecuado.
- Panel: superficie contenida; título y agrupación semántica.
- Notice: éxito mediante role=status, error mediante role=alert y foco al aparecer.
- ConfirmDeactivation: dialog nativo; explica el efecto, enfoca Cancelar, admite Escape
  mantiene el recorrido Tab/Shift+Tab entre sus acciones y devuelve foco al control que lo abrió. El backend sigue siendo responsable del permiso.
- CredentialForm: formulario reutilizable para configuración, ingreso y empleados;
  bloqueo de doble envío, errores claros y conservación del flujo de teclado.
- ConfirmDialog: base reutilizada por desactivación de empleados, categorías y productos.
- Catálogo: lista paginada y editor en paralelo; se apilan bajo 900 px. Filtros con etiquetas
  visibles, estado activo/stock bajo en texto, importes ARS y código conservado como texto.
- Inventario: selección de producto, ajuste con motivo e historial real de antes/después.
  EMPLOYEE consulta catálogo, sin costos ni controles administrativos. El backend lo verifica.
- La navegación limpia avisos de otra sección. Mientras una operación se está enviando
  se bloquean formularios, navegación y logout; errores y confirmaciones se anuncian
  y reciben foco. Una venta con respuesta incierta permite consultar historial o salir,
  conservando su intento por usuario en esa pestaña, pero bloquea otra venta.
- Caja: lista/buscador y carrito con cantidades; revisión del importe antes de confirmar.
  Cotización y comprobante reciben foco. Un intento de respuesta incierta queda visible,
  bloquea otra venta y permite reintentar exactamente la misma operación.
- Historial: filtros de persona para ADMIN, estado y paginación; detalle y anulación con
  motivo/confirmación. EMPLOYEE recibe solo las suyas por API.
- Ticket: vista de papel blanco, tinta negra y Manrope local; documento de 48 mm de
  contenido dentro de papel nominal de 58 mm. Print oculta navegación y acciones, permite
  saltos entre ítems y ajusta nombres/códigos largos. No se simula estado «impreso».

Username normalizado y roles siguen definidos por la API. El diseño no cambia los contratos,
la autorización ni el manejo de sesiones/CSRF. No se añade almacenamiento de credenciales
ni secretos en localStorage, capturas o documentación.

## Movimiento y teclado

Transiciones de fondo/borde de campos y transform de botones de 150 ms; pulsación de 1 px.
El texto y fondo de los botones cambian de forma instantánea al habilitar/deshabilitar:
interpolar ambos colores producía cuadros intermedios de contraste insuficiente.
Indicador de espera en CSS, sin biblioteca de animaciones. Con prefers-reduced-motion: reduce
se desactivan transiciones y animación del indicador, conservando el texto de espera.
Foco de controles: contorno negro de 3 px y separación de 4 px. Orden natural de tabulación,
link para saltar al contenido, títulos enfocados tras cambios de pantalla y diálogo nativo.

## Revisión

Capturas reales y resultados en [FRONTEND_DESIGN_VALIDATION.md](../FRONTEND_DESIGN_VALIDATION.md).
El propietario autorizó la fusión del diseño original el 2026-10-22: PR #2, merge 058a92f.
Las capturas adicionales de F3 están en docs/screenshots/f3 y su validación en
[F3_DEVELOPMENT.md](../F3_DEVELOPMENT.md).
F3 aprobada y fusionada (3848d55). Capturas/PDF adicionales y resultados de F4:
[F4_DEVELOPMENT.md](../F4_DEVELOPMENT.md); validación física de impresión pendiente.

## Reportes F5

KPIs en grilla adaptable, superficies amarillas con espaciado interno y cifras tabulares.
Ranking textual top 10, tabla semántica de 24 horas con barras decorativas; el valor
exacto siempre se lee como texto. Selector distingue transacciones y facturación;
los picos siempre usan tickets. Períodos comparados explícitos, estado vacío y errores
con reintento/foco. Solo ADMIN; carga local diferida. Controles y tipografía conservados.
Capturas reales/axe y revisión visual: [F5_DEVELOPMENT.md](../F5_DEVELOPMENT.md).

## Herramientas F6 candidatas

Vista ADMIN con CSV/vista previa y respaldos/configuración. Importación y restauración
usan confirmación nativa, avisos con foco, estados de espera y reintento recuperable.
Archivos tienen controles de 44 px y texto español independiente del navegador; tabla
acotada a primeros 20, scroll local en móvil. Contraseña solo en estado transitorio,
nunca en storage/capturas. Se conservan Manrope/amarillo, contraste y movimiento reducido.
Evidencia real en F6_DEVELOPMENT.md; ayuda PR #6 incorporada tras aprobación posterior.

## Ayuda integrada

Botón circular ? de 44 px al extremo derecho del encabezado, con nombre accesible Abrir
ayuda y tooltip. Diálogo con fondo inerte, encabezado/cierre siempre visibles y cuerpo
con scroll; en móvil búsqueda/tema se apilan. Preguntas en details/summary nativos con
pasos numerados. Al abrir enfoca búsqueda; Escape/cierre devuelve foco y Tab/Shift+Tab
permanece dentro. Conserva Manrope, paleta, contraste y movimiento reducido. Capturas y
verificación: [USER_HELP_DEVELOPMENT.md](../USER_HELP_DEVELOPMENT.md).

Actualización posterior: PR #6 autorizado e integrado en main 4b40e3f. Candidato F6
incorpora esa ayuda, mantiene producto 0.5.1 y conserva pendiente Windows 11 limpio.
La evidencia anterior describe su ejecución original; PR #7 no se fusiona.
