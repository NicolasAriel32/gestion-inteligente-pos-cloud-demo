# Versiones y estado de entrega

Actualizado: 2026-10-22. Versión de referencia del software: **0.5.1**.
F1–F5 implementadas y verificadas; F5 fusionada por autorización en fb85521.
Impresora física de 58 mm, Windows/instalador y piloto conservan sus pendientes.
F6 candidata implementada y validada en Linux; Windows 11 limpio pendiente.
La versión del software no certifica esas validaciones.

## Fuentes verificables

| Elemento | Versión / ubicación |
| --- | --- |
| Paquete backend | 0.5.1 en backend/pyproject.toml, project.version |
| API / OpenAPI | 0.5.1 en backend/app/main.py, FastAPI.version |
| Paquete frontend | 0.5.1 en frontend/package.json |
| Lockfile, raíz y packages[""] | 0.5.1 en frontend/package-lock.json |
| Esquema SQLite | main: 0005_reporting_indexes; candidato F6: 0006_local_operations |
| Specs funcionales vigentes | Referencia 0.5.1; las secciones futuras siguen identificadas |

lockfileVersion=3 es el formato de npm y no debe cambiarse a 0.5.1.
Las versiones de Python/Node/dependencias son distintas y se registran con comandos
reales en F5_DEVELOPMENT.md. F5 agrega tzdata y un índice (migración 0005).

## Política para próximas entregas

- Usar MAJOR.MINOR.PATCH. La entrega actual es 0.5.1; correcciones posteriores de F5
  pueden ser 0.5.x. F6 requiere autorización y validación independientes.
- Actualizar juntos paquete backend, API/OpenAPI, frontend y las dos raíces del lockfile.
  Para npm: npm version VERSION --no-git-tag-version --ignore-scripts --offline.
- Tras modificar metadata Python, reinstalar editable sin actualizar dependencias y
  comprobar importlib.metadata.version. No confundir el archivo fuente con la metadata
  aún instalada en un entorno anterior.
- Verificar estructura y dependencias del lockfile, build y comandos requeridos por el
  cambio antes de publicar. No crear tags/release GitHub como efecto secundario de npm.
- Solo crear una migración si cambia el esquema/índices, no por incrementar MINOR/PATCH.
  Actualizar el contrato de arranque y las pruebas de upgrade si cambia la revisión.
- Mantener las evidencias históricas F1/F2/F3/F4 con sus resultados originales; añadir
  actualizaciones fechadas. Una cabecera de referencia no convierte objetivos futuros
  en funciones disponibles ni pruebas pendientes en aprobadas.

## Corrección de metadatos F4

Se detectaron paquetes/lockfile en 0.1.0 y specs con cabecera 0.1, aunque OpenAPI y el
software implementado ya eran F4/0.4.0. Se alinean sin modificar contratos comerciales.
Hallazgo y prevención: H-REL-001 en ENGINEERING_FINDINGS.md.
Validación local ejecutada el 2026-10-22 en feat/f4-checkout-history, antes de fusionar
PR #4. No son checks de GitHub Actions. Entorno: Python 3.12.14, Node 24.19.0,
npm 11.9.0 y Chromium 154 del sistema. Sin dependencias nuevas ni actualización masiva.

| Comando / comprobación | Resultado |
| --- | --- |
| backend: .venv/bin/python -m pip install --no-index --no-deps --no-build-isolation -e . | Falló: setuptools.build_meta no disponible; H-REL-002 |
| backend: .venv/bin/python -m pip install --no-deps -e . | Correcto; build aislado y metadata instalada 0.4.0 |
| backend: .venv/bin/python -m pip check | No broken requirements found |
| backend: .venv/bin/python -m pytest -q | 119 aprobadas, 0 fallidas; 110.32 s |
| backend: .venv/bin/python -m ruff check . | All checks passed |
| Alembic upgrade head / current / upgrade head en TemporaryDirectory | Correcto; 0004_checkout_history (head), reaplicación sin cambios |
| frontend: npm version 0.4.0 --no-git-tag-version --ignore-scripts --offline | Correcto; solo versiones raíz, sin tags |
| frontend: npm run test | 34 aprobadas, 0 fallidas |
| frontend: npm run lint | Correcto |
| frontend: npm run build | Correcto; TypeScript/Vite, JS principal 76.42 kB gzip |
| Comparación de metadata y lockfile | 7 valores 0.4.0 coincidentes; dependencias idénticas al commit 98ede0d |

Comprobación de versiones: tomllib para project.version, importlib.metadata.version
para el paquete editable, create_app().version y create_app().openapi()['info']['version'],
más JSON de package.json y ambas raíces de package-lock.json. Todas coincidieron en
0.4.0. Se comparó el lockfile estructuralmente contra git show HEAD:frontend/package-lock.json
normalizando únicamente sus dos versiones raíz, y pyproject normalizando project.version:
sin cambios de dependencias. La migración CLI se ejecutó con LOCALAPPDATA apuntando a
un TemporaryDirectory nuevo, nunca contra datos comerciales.

Incidencia de E2E: la primera ejecución de npm run test:e2e falló por timeout del botón
de recuperación tras reautenticar. Una repetición diagnóstica pasó (28.7 s), con intento
conservado. Se fortaleció la sincronización/navegación del test (H-REL-003), sin cambiar
contratos ni código de aplicación; la sonda temporal se retiró. El resultado final se
registra abajo sin ocultar el primer fallo.

Advertencias: deprecación Starlette/TestClient con httpx en pytest; aviso npm de una
versión mayor disponible y FORCE_COLOR/NO_COLOR en Playwright, sin fallo. No se cambian
dependencias por esos avisos. Se requiere acceso a herramientas de build al reinstalar
con aislamiento; las operaciones del POS siguen siendo locales sin internet.

La publicación queda trazada por el commit de corrección de versiones/documentación
y el merge de PR #4; no se crea release/tag GitHub automáticamente.


Resultado E2E final: POS_TEST_CHROMIUM=/usr/bin/chromium npm run test:e2e -- --repeat-each=2,
**2 ejecuciones completas aprobadas, 0 fallidas** (29.0 y 28.1 s; total 58.8 s).
Ambas verificaron recuperación de venta pendiente tras desmontaje/logout/login, mismo
pedido y una sola venta; permisos ADMIN/EMPLOYEE, impresión/PDF, reinicio/persistencia,
Manrope local y cero solicitudes externas/errores JavaScript no controlados.
Conteo final de casos distintos: **119 + 34 + 1 = 154 aprobados, 0 fallidos finales**;
se conserva el fallo E2E inicial como incidencia, sin contarlo como prueba nunca ejecutada.
La repetición es evidencia de estabilidad, no un caso adicional. No prueba hardware real.


## Entrega F5 — 2026-10-22

Backend, metadata editable instalada, API/OpenAPI, frontend y dos raíces de lockfile
coinciden en **0.5.0** (siete valores verificados). Esquema **0005_reporting_indexes**,
índice aditivo; versiones transitivas npm idénticas a main. Única dependencia directa
nueva: tzdata>=2025.2,<2027 (instalada 2026.5) para datos horarios locales en Windows.
Las migraciones anteriores y sus contratos económicos permanecen sin editar.
Suite/regresión, comandos y build/capturas reales: [F5_DEVELOPMENT.md](../F5_DEVELOPMENT.md).
F5 en revisión humana, sin merge ni inicio de F6. La versión no certifica hardware/piloto.

## Candidato F6 — no entrega final

Main F5 fue fusionado en fb85521. F6 está autorizada y en desarrollo, con esquema candidato
0006_local_operations. Tras integrar la ayuda autorizada se mantiene 0.5.1 mientras falta
Windows 11 limpio; no se etiqueta 0.6.0 final ni se crea release. Al cerrar todos los
criterios se alinearán juntos producto/API/paquetes/lockfile/metadata a 0.6.0. Ayuda PR #6
incorporada tras autorización posterior. No hay dependencias de ejecución nuevas; herramientas de build separadas.


## Mejora 0.5.1 — ayuda local

Ayuda rápida por rol, sin nuevas dependencias ni migraciones; esquema permanece
0005_reporting_indexes. Versiones de paquetes/API/lockfile se alinean a 0.5.1. F5 conserva
sus resultados históricos y merge autorizado fb85521; F6 no se inicia. Evidencia real y
metadata instalada: USER_HELP_DEVELOPMENT.md.

Actualización posterior: PR #6 autorizado e integrado en main 4b40e3f. Candidato F6
incorpora esa ayuda, mantiene producto 0.5.1 y conserva pendiente Windows 11 limpio.
La evidencia anterior describe su ejecución original; PR #7 no se fusiona.
