# Demo funcional por enlace — Cloudflare + Render

Fecha: 2026-10-23. Base: POS 0.5.1, esquema `0005_reporting_indexes`.
Destino: `NicolasAriel32/gestion-inteligente-pos-cloud-demo`, rama `main`.
Fuente: `NicolasAriel32/gestion-inteligente-pos`, commit
`4b40e3f8fd6b0ac0a239135906ccbfe7fb2c2a6d`. El repositorio original no cambia.

## Alcance

Probar los módulos implementados desde el navegador de una PC sin instalar programas:
administrador, empleados, catálogo, inventario, caja, historial, anulaciones, reportes
y ayuda. El ticket usa el diálogo de impresión del navegador; una impresora física
requiere controlador instalado. No incluye funciones futuras F6/F7, instalador,
backup/restauración ni facturación fiscal.

Cloudflare sirve React y reenvía `/api/*` a Python en Render. El backend ejecuta los
mismos casos de uso, permisos, transacciones SQLAlchemy/SQLite y migraciones del POS.
No hay ventas simuladas ni un backend falso. Solo se modifica la base de esta demo.
No hay que descargar ZIP ni instalar Python/Node en la PC desde la que se prueba.

Esta excepción remota se limita al entrypoint `app.cloud_demo`, con opt-in explícito,
origen/Host exactos y cookies Secure. El comando local `python -m app` sigue en loopback.

## Datos y costo

La configuración elige **Free** de Render, sin disco pago. Su filesystem es efímero:
los datos se pierden al reiniciar, republicar o suspenderse la instancia. Render
puede suspenderla tras 15 minutos sin tráfico; el siguiente arranque puede demorar
aproximadamente un minuto. La aplicación muestra un aviso permanente de demo.
Usar datos ficticios y contraseñas exclusivas. No es una caja de producción.
No activar planes pagos ni añadir una tarjeta para realizar esta prueba.

La persistencia en el mismo directorio se comprueba en tests, pero no elimina la
pérdida de datos propia del hosting gratuito. Solo se aprovisiona una base nueva,
aislada e inexistente. Una existente incompatible se rechaza sin migrarla ni borrarla.

## 1. Crear el Worker desde GitHub

En Cloudflare, crear un Worker conectado a este repositorio con:

| Campo | Valor |
| --- | --- |
| Repositorio | `NicolasAriel32/gestion-inteligente-pos-cloud-demo` |
| Rama | `main` |
| Nombre | `gestion-inteligente-pos-cloud-demo` |
| Root directory | Raíz del repositorio (`/`), no `frontend` |
| Build command | Vacío: Wrangler ejecuta la compilación definida en el repo |
| Deploy command | `npm run deploy` |
| Node | 22 o superior |

Workers Builds instala las dependencias npm de raíz con su lockfile. Si esa instalación
automática fue deshabilitada, poner `npm ci` como Build command. Wrangler instala y
compila el frontend con `--mode cloud-demo` antes de publicar solo `frontend/dist`.
Nunca publicar `.` ni `frontend` como assets.

Copiar la URL HTTPS real que Cloudflare muestre tras crear el Worker. No adivinarla.
En este primer paso es normal ver un error de API porque falta `BACKEND_URL`.

## 2. Crear el servidor en Render

Crear un Blueprint de Render desde este mismo repositorio y rama `main`, usando
`render.yaml`. Revisar que sea **Free**, sin disco pago. En `POS_PUBLIC_ORIGIN`, poner
la URL real del Worker del paso anterior, sin ruta ni barra final. La configuración
versionada contiene:

- Python 3.12.14, directorio `backend` y dependencias fijadas para esta prueba.
- Build: `pip install -r requirements-cloud-demo.txt .`
- Start: `python -m app.cloud_demo`; un solo proceso; puerto `$PORT`.
- Health check: `/api/health`.
- `POS_CLOUD_DEMO=1`, para habilitar solo este entrypoint remoto.
- `LOCALAPPDATA=/tmp/gestion-inteligente-pos-cloud-demo`, separado de datos comerciales.
- `POS_DEMO_SETUP_TOKEN`, generado como secreto privado por Render.
- `RENDER_EXTERNAL_HOSTNAME`, provisto por Render para la allowlist de Host.

El secreto no debe aparecer en GitHub, chats, capturas, variables públicas de Vite
ni logs. No se incluye un usuario/contraseña universal ni datos comerciales.

## 3. Conectar servidor y Worker

En Settings → Variables and Secrets del Worker, agregar `BACKEND_URL` con el origen
HTTPS real del servicio Render (el que termine en `.onrender.com`), sin rutas.
Es una URL pública, no una contraseña. Volver a desplegar si el panel lo solicita.
`keep_vars: true` conserva esa variable entre publicaciones.

El navegador usa solo el origen de Cloudflare; el proxy conserva Origin, cookie y
CSRF. No habilitar CORS con `*`. El backend acepta solo el origen exacto configurado,
con cookies `Secure`, `HttpOnly` y `SameSite=Strict`. Si cambia la URL del Worker,
actualizar `POS_PUBLIC_ORIGIN` en Render.

**Son necesarios los dos servicios.** Subir solo el repo a Cloudflare no inicia Python.

## 4. Primer acceso

1. Abrir el enlace del Worker y esperar el arranque del servidor si estaba suspendido.
2. Leer `POS_DEMO_SETUP_TOKEN` en el panel privado de Render e introducirlo en el campo
   “Secreto de inicialización”. Crear tu administrador con contraseña de prueba.
   El secreto vence a los 30 minutos del arranque; si vence antes de crear ADMIN,
   reiniciar el servicio. Un ADMIN existente no se reinicializa.
3. Iniciar sesión, crear empleado y productos con stock ficticio.
4. Vender, revisar historial, reimprimir ticket, consultar reportes y anular como ADMIN.
5. Verificar reposición de stock y restricciones de permisos del empleado.

Si Render pierde la base efímera, la siguiente instancia es una demo nueva que deberá
inicializarse otra vez. No usar la demo para conservar información real.

## Diagnóstico

| Síntoma | Acción |
| --- | --- |
| Página en blanco / `/src/main.tsx` | Revisar raíz y deploy command; publicar `frontend/dist` compilado |
| Falta conectar servidor / HTTP 503 | Configurar `BACKEND_URL` real de Render |
| Servidor iniciándose | Esperar alrededor de un minuto y pulsar Volver a intentar |
| HTTP 403 al escribir | Verificar que `POS_PUBLIC_ORIGIN` coincida exactamente con la URL del Worker |
| Host no permitido | Comprobar `RENDER_EXTERNAL_HOSTNAME` provisto por Render |
| Base incompatible | Investigar la versión; no borrar ni migrar datos para ocultar el problema |
| Respuesta perdida al confirmar | Recuperar el mismo intento, no iniciar otra venta |
| HTTP 429 al ingresar | Esperar un minuto; límite global de 20 intentos/minuto en esta demo |

El proxy no reintenta escrituras ni sigue redirecciones. Las respuestas HTML de
arranque de Render se convierten en un error JSON claro.

## Comprobaciones

Desde la raíz:

```sh
npm ci
npm run test:workers
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
npm run check:workers
```

`check:workers` compila y empaqueta con `--dry-run`, sin publicar ni crear servicios.
En `backend`, con el entorno virtual y dependencias de desarrollo instaladas:

```sh
python -m pytest -q
python -m ruff check .
```

No iniciar el entrypoint público en la PC del trabajo. Solo Render usa `app.cloud_demo`.
Se conservan los comandos de desarrollo local del README histórico.

## Validación de esta intervención

- Backend: 154 pruebas aprobadas, incluidas 12 nuevas de configuración remota,
  cookies Secure, Origin/Host, CSRF, límite de intentos, esquema incompatible y flujo
  real de administrador/empleado, catálogo, venta, recuperación idempotente, stock,
  reportes, anulación y reinicio sobre el mismo directorio de prueba.
- Frontend: 51 pruebas aprobadas; incluye prueba DOM que confirma que el modo remoto
  carga los formularios operativos y llama a la API, sin reemplazarla por una vista estática.
- Proxy Worker: 8 pruebas aprobadas; cookie/CSRF/cuerpo conservados, escritura única,
  errores de conexión, origen rechazado, redirecciones, HTML de cold start y assets.
- Ruff backend, ESLint frontend, TypeScript y compilación local normal: aprobados.
- `npm run check:workers`: compilación `cloud-demo` y dry-run Wrangler aprobados;
  11 assets y binding ASSETS. `pip check`, `git diff --check` y sintaxis JS: aprobados.

Total: 213 pruebas aprobadas. Las pruebas locales y el paquete no equivalen a una
publicación remota verificada. No se ejecutó E2E visual en Chromium en esta intervención:
la descarga del navegador había fallado y el runtime local de Wrangler informó una
restricción del entorno (`uv_interface_addresses`). No se certifican impresora física
ni permisos de la red corporativa. El despliegue real requiere crear ambos servicios.

Al cerrar la preparación, la creación del nuevo repositorio quedó bloqueada porque
GitHub rechazó el login del navegador; el conector existente permite editar repositorios
pero no crearlos. El código se conserva en la rama `test/cloudflare-full-demo` del
repositorio fuente, sin cambiar `main`, hasta importarlo en el repositorio independiente.

## Referencias oficiales

- https://render.com/docs/free
- https://render.com/docs/blueprint-spec
- https://developers.cloudflare.com/workers/static-assets/binding/
- https://developers.cloudflare.com/workers/wrangler/configuration/
