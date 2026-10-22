import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'
import type { ChildProcess } from 'node:child_process'
import { spawn, spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const frontend = resolve(import.meta.dirname, '..')
const backend = resolve(frontend, '../backend')
const captures = process.env.POS_CAPTURE_DIR
const python = process.env.POS_TEST_PYTHON ?? join(backend, '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')

async function assertFree(port: number) {
  await new Promise<void>((resolve, reject) => {
    const server = createServer()
    server.once('error', reject)
    server.listen(port, '127.0.0.1', () => server.close(error => error ? reject(error) : resolve()))
  })
}
async function ready(url: string, process: ChildProcess) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (process.exitCode !== null) throw new Error('El servicio local terminó antes de iniciar')
    if (await fetch(url).then(response => response.ok).catch(() => false)) return
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('El servicio local no inició a tiempo')
}
async function stop(child?: ChildProcess) {
  if (!child || child.exitCode !== null) return
  const exited = new Promise<void>(resolve => child.once('exit', () => resolve()))
  child.kill('SIGTERM')
  await exited
}

async function screenshot(page: Page, name: string) {
  const inventoryScreen = name.startsWith('catalog-') || name.startsWith('inventory-')
  const salesScreen = ['checkout-', 'receipt-', 'history-', 'void-'].some(prefix => name.startsWith(prefix))
  const destination = name.startsWith('help-') ? process.env.POS_HELP_CAPTURE_DIR : name.startsWith('tools-') ? process.env.POS_F6_CAPTURE_DIR : name.startsWith('reports-') ? process.env.POS_F5_CAPTURE_DIR : salesScreen ? process.env.POS_F4_CAPTURE_DIR ?? captures : inventoryScreen ? process.env.POS_F3_CAPTURE_DIR ?? captures : captures
  if (!destination) return
  mkdirSync(destination, { recursive: true })
  // Las capturas solo se toman con campos secretos vacíos.
  expect(await page.locator('input[type="password"]').evaluateAll(inputs => inputs.every(input => !(input as HTMLInputElement).value))).toBe(true)
  // Estabilizar la posición tras enfocar avisos y cambiar el ancho del viewport.
  await page.evaluate(() => window.scrollTo(0, 0))
  if (inventoryScreen) {
    await expect(page.locator('.skip-link')).not.toBeFocused()
    expect(await page.locator('.skip-link').evaluate(element => element.getBoundingClientRect().bottom)).toBeLessThanOrEqual(0)
  }
  await page.screenshot({ path: join(destination, `${name}.png`), fullPage: !name.startsWith('help-') })
}
async function accessible(page: Page) {
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  if (await page.locator('.help-dialog').isVisible()) expect(await page.locator('.help-dialog__body').evaluate(e => e.scrollWidth <= e.clientWidth)).toBe(true)
}
async function screens(page: Page, name: string) {
  await page.setViewportSize({ width: 1366, height: 768 })
  await accessible(page)
  await screenshot(page, `${name}-desktop`)
  await page.setViewportSize({ width: 390, height: 844 })
  await accessible(page)
  await screenshot(page, `${name}-mobile`)
  await page.setViewportSize({ width: 320, height: 740 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.setViewportSize({ width: 1366, height: 768 })
}

async function ticketPdf(page: Page, name: string) {
  await page.emulateMedia({ media: 'print' })
  const paper = page.locator('.receipt-paper')
  await expect(paper).toContainText('COMPROBANTE NO FISCAL')
  await expect(page.locator('.topbar')).toBeHidden()
  await expect(page.locator('.workspace-nav')).toBeHidden()
  expect(await paper.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
  expect(await paper.evaluate(element => getComputedStyle(element).color)).toBe('rgb(0, 0, 0)')
  const printClient = await page.context().newCDPSession(page)
  const pdf = await printClient.send('Page.printToPDF', { paperWidth: 58 / 25.4, paperHeight: 200 / 25.4, marginTop: 3 / 25.4, marginBottom: 3 / 25.4, marginLeft: 3 / 25.4, marginRight: 3 / 25.4, printBackground: false, displayHeaderFooter: false })
  const pdfBytes = Buffer.from(pdf.data, 'base64')
  expect(pdfBytes.subarray(0, 4).toString()).toBe('%PDF')
  const mediaBox = pdfBytes.toString('latin1').match(/\/MediaBox\s*\[\s*0\s+0\s+([\d.]+)/)
  expect(Number(mediaBox?.[1]) / 72 * 25.4).toBeCloseTo(58, 0)
  if (process.env.POS_F4_CAPTURE_DIR) {
    mkdirSync(process.env.POS_F4_CAPTURE_DIR, { recursive: true })
    writeFileSync(join(process.env.POS_F4_CAPTURE_DIR, `${name}.pdf`), pdfBytes)
    await paper.screenshot({ path: join(process.env.POS_F4_CAPTURE_DIR, `${name}.png`) })
  }
  await printClient.detach()
  await page.emulateMedia({ media: 'screen' })
}

test('identidad, inventario y caja locales, permisos, reintentos, impresión y reinicio sin red externa', async ({ browser }) => {
  await assertFree(8765)
  await assertFree(5173)
  const root = mkdtempSync(join(tmpdir(), 'pos-f4-e2e-'))
  const env = { ...process.env, LOCALAPPDATA: root }
  let api: ChildProcess | undefined
  let vite: ChildProcess | undefined
  const external: string[] = []
  const errors: string[] = []
  const context = await browser.newContext()
  const workerContext = await browser.newContext()
  for (const current of [context, workerContext]) {
    await current.route('**/*', route => {
      const hostname = new URL(route.request().url()).hostname
      if (!['127.0.0.1', 'localhost'].includes(hostname)) {
        external.push(hostname)
        return route.abort()
      }
      return route.continue()
    })
  }
  try {
    for (const args of [['-m', 'alembic', '-c', 'alembic.ini', 'upgrade', 'head'], ['-m', 'app.bootstrap']]) {
      const result = spawnSync(python, args, { cwd: backend, env, encoding: 'utf8' })
      if (result.status !== 0) throw new Error('Falló la preparación aislada de SQLite')
    }
    const setup = readFileSync(join(root, 'GestionInteligentePOS/config/setup-token.txt'), 'utf8')
    const startApi = () => spawn(python, ['-m', 'app'], { cwd: backend, env, stdio: 'ignore' })
    api = startApi()
    vite = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--strictPort'], {
      cwd: frontend, env, stdio: 'ignore',
    })
    await Promise.all([ready('http://127.0.0.1:8765/api/health', api), ready('http://127.0.0.1:5173', vite)])
    const page = await context.newPage()
    page.on('pageerror', error => errors.push(error.message))
    await page.setViewportSize({ width: 1366, height: 768 })
    const fonts: string[] = []
    page.on('response', response => { if (response.url().endsWith('.woff2') && response.status() === 200) fonts.push(response.url()) })
    await page.goto('http://127.0.0.1:5173')
    await expect(page.getByRole('status')).toHaveText('Servidor local conectado')
    await page.getByLabel('Secreto de inicialización').waitFor()
    await page.evaluate(() => document.fonts.ready)
    expect(fonts).toHaveLength(1)
    expect(new URL(fonts[0]).origin).toBe('http://127.0.0.1:5173')
    const cdp = await context.newCDPSession(page)
    await cdp.send('DOM.enable'); await cdp.send('CSS.enable')
    const { root: documentNode } = await cdp.send('DOM.getDocument')
    const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: documentNode.nodeId, selector: 'h1' })
    const renderedFonts = await cdp.send('CSS.getPlatformFontsForNode', { nodeId })
    // La fuente variable conserva el nombre interno de su instancia base 200.
    // CSS selecciona el peso 800 del título; no es una fuente de sistema.
    expect(await page.locator('h1').evaluate(element => getComputedStyle(element).fontWeight)).toBe('800')
    expect(renderedFonts.fonts.some(font => font.familyName === 'Manrope ExtraLight' && font.isCustomFont && font.glyphCount > 0)).toBe(true)
    await cdp.detach()
    // Ayuda local disponible sin sesión y sin tocar datos ni mostrar guías ADMIN.
    await page.getByRole('button', { name: 'Abrir ayuda', exact: true }).press('Enter')
    const guestHelp = page.getByRole('dialog')
    await expect(guestHelp.getByLabel('Buscar en la ayuda', { exact: true })).toBeFocused()
    await expect(guestHelp.locator('summary').filter({ hasText: '¿Cómo cargar un producto?' })).toHaveCount(0)
    await expect(guestHelp.locator('summary').filter({ hasText: '¿Qué hago si no puedo ingresar?' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: 'Abrir ayuda', exact: true })).toBeFocused()
    await screens(page, 'setup')
    await page.getByRole('link', { name: 'Ir al contenido' }).focus()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('main')).toBeFocused()
    await page.getByLabel('Secreto de inicialización').fill(setup)
    await page.getByLabel('Usuario', { exact: true }).fill('owner')
    await page.getByLabel('Contraseña', { exact: true }).fill('E2e-password-owner-42')
    await page.getByRole('button', { name: 'Crear administrador', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Ingresar', exact: true })).toBeVisible()
    await screens(page, 'login')
    // Comprobar error real de credenciales y foco en el mensaje.
    await page.getByLabel('Usuario', { exact: true }).fill('owner')
    await page.getByLabel('Contraseña', { exact: true }).fill('Wrong-test-password-42')
    await page.getByRole('button', { name: 'Ingresar', exact: true }).click()
    await expect(page.getByRole('alert')).toHaveText('Usuario o contraseña incorrectos')
    await expect(page.getByRole('alert')).toBeFocused()
    await page.getByLabel('Usuario', { exact: true }).clear()
    await page.getByLabel('Contraseña', { exact: true }).clear()
    await accessible(page)
    await screenshot(page, 'login-error-desktop')
    // Orden de teclado y foco visible en controles.
    await page.getByRole('heading', { level: 1 }).focus()
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('Usuario', { exact: true })).toBeFocused()
    expect(await page.getByLabel('Usuario', { exact: true }).evaluate(element => getComputedStyle(element).outlineWidth)).toBe('3px')
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('Contraseña', { exact: true })).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'Ingresar', exact: true })).toBeFocused()
    await page.getByLabel('Usuario', { exact: true }).fill('owner')
    await page.getByLabel('Contraseña', { exact: true }).fill('E2e-password-owner-42')
    let releaseLogin!: () => void
    const loginGate = new Promise<void>(resolve => { releaseLogin = resolve })
    let submissions = 0
    await page.route('**/api/auth/login', async route => { submissions++; await loginGate; await route.continue() })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.getByRole('button', { name: 'Ingresar', exact: true }).press('Enter')
    try {
      await expect(page.getByRole('button', { name: 'Procesando…' })).toBeDisabled()
      await expect(page.getByLabel('Usuario', { exact: true })).toBeDisabled()
      expect(await page.locator('.spinner').evaluate(element => getComputedStyle(element).animationName)).toBe('none')
      expect(await page.locator('button[type="submit"]').evaluate(element => getComputedStyle(element).transitionDuration)).toBe('0s')
      await page.locator('form').evaluate(form => form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
      expect(submissions).toBe(1)
    } finally { releaseLogin() }
    await page.emulateMedia({ reducedMotion: 'no-preference' })

    await expect(page.getByRole('heading', { name: 'Sesión de owner' })).toBeVisible()
    await page.getByLabel('Usuario', { exact: true }).fill('worker')
    await page.getByLabel('Contraseña', { exact: true }).fill('E2e-password-worker-42')
    await page.getByRole('button', { name: 'Crear empleado', exact: true }).click()
    await expect(page.getByRole('listitem').filter({ has: page.getByText('worker', { exact: true }) }).getByText('Activo', { exact: true })).toBeVisible()
    await expect(page.getByLabel('Usuario', { exact: true })).toBeFocused()
    await screens(page, 'employees')
    const worker = await workerContext.newPage()
    worker.on('pageerror', error => errors.push(error.message))
    await worker.goto('http://127.0.0.1:5173')
    await worker.getByLabel('Usuario', { exact: true }).fill('worker')
    await worker.getByLabel('Contraseña', { exact: true }).fill('E2e-password-worker-42')
    await worker.getByRole('button', { name: 'Ingresar', exact: true }).click()
    await expect(worker.getByRole('heading', { name: 'Sesión de worker' })).toBeVisible()
    await expect(worker.getByRole('button', { name: 'Crear empleado', exact: true })).toHaveCount(0)
    expect(await worker.evaluate(async () => (await fetch('/api/employees')).status)).toBe(403)
    // Ayuda del empleado explica su rol y no ofrece guías administrativas.
    await worker.getByRole('button', { name: 'Abrir ayuda', exact: true }).click()
    await expect(worker.getByRole('dialog')).toContainText('Guías para tu cuenta de empleado')
    await expect(worker.getByRole('dialog').locator('summary').filter({ hasText: '¿Cómo cambiar el precio de un producto?' })).toHaveCount(0)
    await worker.getByRole('dialog').getByLabel('Buscar en la ayuda', { exact: true }).fill('venta pendiente')
    await expect(worker.getByRole('dialog').locator('summary').filter({ hasText: '¿Qué hago si una venta queda pendiente' })).toBeVisible()
    await worker.getByRole('button', { name: 'Cerrar ayuda', exact: true }).press('Enter')
    // Catálogo e inventario: operaciones reales de F3, sin ventas ni datos precargados.
    await page.getByRole('button', { name: 'Catálogo', exact: true }).click()
    await expect(page.getByText('La cuenta de worker ya está creada.', { exact: true })).toHaveCount(0)
    // Consultar ayuda conserva el borrador y no envía escrituras a la API.
    await page.getByLabel('Nombre del producto', { exact: true }).fill('Borrador conservado')
    const helpWrites: string[] = []
    const observeHelpWrites = (request: import('@playwright/test').Request) => {
      if (new URL(request.url()).pathname.startsWith('/api/') && !['GET', 'HEAD'].includes(request.method())) helpWrites.push(request.method())
    }
    page.on('request', observeHelpWrites)
    await page.getByRole('button', { name: 'Abrir ayuda', exact: true }).press('Enter')
    const help = page.getByRole('dialog')
    await expect(help.getByLabel('Buscar en la ayuda', { exact: true })).toBeFocused()
    await help.getByLabel('Buscar en la ayuda', { exact: true }).fill('CARGAR PRODUCTO')
    await help.locator('summary').filter({ hasText: '¿Cómo cargar un producto?' }).press('Enter')
    await expect(help).toContainText('Motivo de carga inicial')
    await screens(page, 'help-product')
    await help.getByLabel('Buscar en la ayuda', { exact: true }).fill('cambiar precio')
    await help.locator('summary').filter({ hasText: '¿Cómo cambiar el precio de un producto?' }).click()
    await expect(help).toContainText('Guardar producto')
    await screens(page, 'help-price')
    await help.getByLabel('Buscar en la ayuda', { exact: true }).fill('mercaderia')
    await expect(help.locator('summary').filter({ hasText: '¿Cómo ingreso mercadería' })).toBeVisible()
    await help.getByRole('combobox', { name: 'Tema de ayuda', exact: true }).selectOption('Reportes')
    await expect(help.getByRole('heading', { name: 'No encontramos una respuesta.', exact: true })).toBeVisible()
    await help.getByRole('button', { name: 'Ver todas las guías', exact: true }).click()
    await expect(help.getByLabel('Buscar en la ayuda', { exact: true })).toBeFocused()
    await help.getByRole('button', { name: 'Cerrar ayuda', exact: true }).focus()
    await page.keyboard.press('Shift+Tab')
    await expect(help.locator('summary').last()).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(help.getByRole('button', { name: 'Cerrar ayuda', exact: true })).toBeFocused()
    await page.emulateMedia({ reducedMotion: 'reduce' })
    expect(await help.getByRole('button', { name: 'Cerrar ayuda', exact: true }).evaluate(e => getComputedStyle(e).transitionDuration)).toBe('0s')
    await page.keyboard.press('Escape')
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await expect(page.getByRole('button', { name: 'Abrir ayuda', exact: true })).toBeFocused()
    await expect(page.getByLabel('Nombre del producto', { exact: true })).toHaveValue('Borrador conservado')
    page.off('request', observeHelpWrites)
    expect(helpWrites).toEqual([])
    await page.getByLabel('Nombre del producto', { exact: true }).clear()
    await page.getByLabel('Nombre de categoría', { exact: true }).fill('Bebidas')
    await page.getByRole('button', { name: 'Crear categoría', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Editar categoría Bebidas', exact: true })).toBeVisible()
    const productForm = page.getByRole('form', { name: 'Crear producto', exact: true })
    await productForm.getByLabel('Nombre del producto', { exact: true }).fill('Agua mineral')
    await productForm.getByLabel('Código', { exact: true }).fill('00042')
    await productForm.getByRole('combobox').selectOption({ label: 'Bebidas' })
    await productForm.getByLabel('Precio de venta (ARS)', { exact: true }).fill('125,50')
    await productForm.getByLabel('Costo (ARS)', { exact: true }).fill('100,00')
    await productForm.getByLabel('Stock mínimo', { exact: true }).fill('1')
    await productForm.getByLabel('Stock inicial', { exact: true }).fill('2')
    await productForm.getByLabel('Motivo de carga inicial', { exact: true }).fill('Carga inicial')
    await productForm.getByRole('button', { name: 'Crear producto', exact: true }).click()
    const productRow = page.getByRole('listitem').filter({ has: page.getByRole('heading', { name: 'Agua mineral', exact: true }) })
    await expect(productRow).toContainText('00042')
    await expect(productRow).toContainText('$ 125,50')
    await page.getByRole('button', { name: 'Editar producto Agua mineral', exact: true }).click()
    await page.getByRole('form', { name: 'Editar producto', exact: true }).getByLabel('Precio de venta (ARS)', { exact: true }).fill('130,25')
    await page.getByRole('button', { name: 'Guardar producto', exact: true }).click()
    await expect(productRow).toContainText('$ 130,25')
    await screens(page, 'catalog')
    await worker.getByRole('button', { name: 'Catálogo', exact: true }).click()
    await expect(worker.getByRole('heading', { name: 'Agua mineral', exact: true })).toBeVisible()
    await expect(worker.getByRole('button', { name: 'Crear producto', exact: true })).toHaveCount(0)
    await expect(worker.getByRole('button', { name: 'Inventario', exact: true })).toHaveCount(0)
    await expect(worker.getByText('Costo:', { exact: false })).toHaveCount(0)
    expect(await worker.evaluate(async () => {
      const session = await fetch('/api/auth/me').then(response => response.json())
      return (await fetch('/api/products', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token }, body: JSON.stringify({ name: 'No permitido', price_cents: 1 }) })).status
    })).toBe(403)
    await page.getByRole('button', { name: 'Inventario', exact: true }).click()
    await page.getByRole('button', { name: 'Ajustar stock de Agua mineral', exact: true }).click()
    await expect(page.getByText('Stock consultado: 2 unidades.', { exact: false })).toBeVisible()
    await page.getByLabel('Cambio de unidades', { exact: true }).fill('3')
    await page.getByLabel('Motivo del ajuste', { exact: true }).fill('Ingreso de mercadería')
    await page.getByRole('button', { name: 'Confirmar ajuste', exact: true }).click()
    await expect(page.getByText('Stock consultado: 5 unidades.', { exact: false })).toBeVisible()
    await page.getByLabel('Cambio de unidades', { exact: true }).fill('-6')
    await page.getByLabel('Motivo del ajuste', { exact: true }).fill('Conteo físico')
    await page.getByRole('button', { name: 'Confirmar ajuste', exact: true }).click()
    await expect(page.getByRole('alert')).toHaveText('Stock insuficiente para este ajuste')
    await page.getByLabel('Cambio de unidades', { exact: true }).fill('-1')
    await page.getByRole('button', { name: 'Confirmar ajuste', exact: true }).click()
    await expect(page.getByText('Stock consultado: 4 unidades.', { exact: false })).toBeVisible()
    await expect(page.getByText('3 movimientos registrados.', { exact: true })).toBeVisible()
    // Volver a elegir el mismo producto debe recargar, sin vaciar su historial.
    await page.getByRole('button', { name: 'Ajustar stock de Agua mineral', exact: true }).click()
    await expect(page.getByText('3 movimientos registrados.', { exact: true })).toBeVisible()
    await expect(page.locator('.movement-list > li')).toHaveCount(3)
    await screens(page, 'inventory')
    // Reinicio real del proceso Python manteniendo DB y cookies del navegador.
    await stop(api)
    api = startApi()
    await ready('http://127.0.0.1:8765/api/health', api)
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Sesión de owner' })).toBeVisible()
    await expect(page.getByRole('listitem').filter({ has: page.getByText('worker', { exact: true }) }).getByText('Activo', { exact: true })).toBeVisible()
    await worker.reload()
    await expect(worker.getByRole('heading', { name: 'Sesión de worker' })).toBeVisible()
    await page.getByRole('button', { name: 'Inventario', exact: true }).click()
    await page.getByRole('button', { name: 'Ajustar stock de Agua mineral', exact: true }).click()
    await expect(page.getByText('Stock consultado: 4 unidades.', { exact: false })).toBeVisible()
    await expect(page.getByText('3 movimientos registrados.', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Catálogo', exact: true }).click()
    await page.getByRole('button', { name: 'Desactivar producto Agua mineral', exact: true }).click()
    await page.getByRole('button', { name: 'Desactivar producto', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Agua mineral', exact: true })).toHaveCount(0)
    await page.getByLabel('Incluir inactivos', { exact: true }).check()
    await expect(page.getByRole('button', { name: 'Reactivar producto Agua mineral', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Reactivar producto Agua mineral', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Desactivar producto Agua mineral', exact: true })).toBeVisible()
    // Caja F4: revisión del servidor, precio cambiado y respuesta perdida tras commit real.
    await page.getByRole('button', { name: 'Caja', exact: true }).click()
    await page.getByRole('button', { name: 'Agregar Agua mineral al carrito', exact: true }).click()
    await page.getByLabel('Cantidad de Agua mineral', { exact: true }).fill('2')
    await page.getByRole('combobox', { name: 'Medio de pago declarado', exact: true }).selectOption('TRANSFER')
    await page.getByRole('button', { name: 'Revisar importe', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Revisá antes de confirmar', exact: true })).toBeFocused()
    await expect(page.locator('.quote-total')).toContainText('$ 260,50')
    await screens(page, 'checkout')
    expect(await page.evaluate(async () => {
      const me = await fetch('/api/auth/me').then(response => response.json())
      return (await fetch('/api/products/1', { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token }, body: JSON.stringify({ price_cents: 14025 }) })).status
    })).toBe(200)
    await page.getByRole('button', { name: 'Confirmar venta y registrar cobro', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('El catálogo cambió')
    expect(await page.evaluate(() => sessionStorage.getItem('pos.checkout.pending.v1.1'))).toBeNull()
    await page.getByRole('button', { name: 'Revisar importe', exact: true }).click()
    await expect(page.locator('.quote-total')).toContainText('$ 280,50')
    const saleRequests: unknown[] = []
    await page.route('**/api/sales', async route => {
      if (route.request().method() !== 'POST') return route.continue()
      saleRequests.push(route.request().postDataJSON())
      if (saleRequests.length === 1) {
        const committed = await route.fetch()
        expect(committed.status()).toBe(201)
        return route.abort('failed')
      }
      return route.continue()
    })
    await page.getByRole('button', { name: 'Confirmar venta y registrar cobro', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Comprobar una venta pendiente', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Reintentar la misma venta', exact: true })).toBeEnabled()
    await page.getByRole('button', { name: 'Abrir ayuda', exact: true }).click()
    await page.getByRole('dialog').getByLabel('Buscar en la ayuda', { exact: true }).fill('respuesta')
    await page.getByRole('dialog').locator('summary').filter({ hasText: '¿Qué hago si una venta queda pendiente' }).click()
    await expect(page.getByRole('dialog')).toContainText('Reintentar la misma venta')
    await page.keyboard.press('Escape')
    await expect(page.getByRole('heading', { name: 'Comprobar una venta pendiente', exact: true })).toBeVisible()
    expect(saleRequests).toHaveLength(1)
    await screens(page, 'checkout-pending')
    await page.reload()
    await page.getByRole('button', { name: 'Caja', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Comprobar una venta pendiente', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Agregar Agua mineral al carrito', exact: true })).toHaveCount(0)
    // Desmontar Caja y reautenticar no descarta una respuesta comercial incierta.
    // La sección activa no es un contrato de sesión: volver a Caja explícitamente.
    await page.getByRole('button', { name: 'Equipo', exact: true }).click()
    await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click()
    await page.getByLabel('Usuario', { exact: true }).fill('owner')
    await page.getByLabel('Contraseña', { exact: true }).fill('E2e-password-owner-42')
    await page.getByRole('button', { name: 'Ingresar', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Caja', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Caja', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Comprobar una venta pendiente', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Reintentar la misma venta', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Venta #1 · Registrada', exact: true })).toBeVisible()
    expect(saleRequests).toHaveLength(2)
    expect(saleRequests[0]).toEqual(saleRequests[1])
    expect(await page.evaluate(async () => (await fetch('/api/sales').then(response => response.json())).total)).toBe(1)
    await screens(page, 'receipt')
    await page.evaluate(() => { window.print = () => { document.body.dataset.printCount = String(Number(document.body.dataset.printCount ?? 0) + 1) } })
    await page.getByRole('button', { name: 'Imprimir ticket de 58 mm', exact: true }).click()
    expect(await page.evaluate(() => document.body.dataset.printCount)).toBe('1')
    expect(saleRequests).toHaveLength(2)
    // PDF real de Chromium a papel 58 mm; no equivale a prueba física de impresora.
    await expect(page.locator('.receipt-paper')).toContainText('Transferencia')
    await ticketPdf(page, 'ticket-58mm')
    const longName = 'Alfajor con chocolate y baño de azúcar '.repeat(4).slice(0, 160).trim()
    expect(await page.evaluate(async ({ name }) => {
      const me = await fetch('/api/auth/me').then(response => response.json())
      return (await fetch('/api/products', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token }, body: JSON.stringify({ name, code: '0'.repeat(63) + '1', price_cents: 19999, initial_stock: 1, initial_reason: 'Carga para prueba de ticket' }) })).status
    }, { name: longName })).toBe(201)
    // El empleado vende y ve únicamente su historial; la API rechaza venta ajena/anulación.
    await worker.getByRole('button', { name: 'Caja', exact: true }).click()
    await worker.getByRole('button', { name: `Agregar ${longName} al carrito`, exact: true }).click()
    await worker.getByRole('button', { name: 'Revisar importe', exact: true }).click()
    await worker.getByRole('button', { name: 'Confirmar venta y registrar cobro', exact: true }).click()
    await expect(worker.getByRole('heading', { name: 'Venta #2 · Registrada', exact: true })).toBeVisible()
    await ticketPdf(worker, 'ticket-58mm-long')
    await worker.getByRole('button', { name: 'Historial', exact: true }).click()
    await expect(worker.locator('.history-list > li')).toHaveCount(1)
    await expect(worker.getByRole('button', { name: 'Ver venta 1', exact: true })).toHaveCount(0)
    expect(await worker.evaluate(async () => (await fetch('/api/sales/1')).status)).toBe(403)
    expect(await worker.evaluate(async () => {
      const me = await fetch('/api/auth/me').then(response => response.json())
      return (await fetch('/api/sales/2/void', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token }, body: JSON.stringify({ reason: 'No autorizado' }) })).status
    })).toBe(403)
    await worker.getByRole('button', { name: 'Ver venta 2', exact: true }).click()
    await expect(worker.getByRole('form', { name: 'Anular venta', exact: true })).toHaveCount(0)
    await screens(worker, 'history-employee')
    await page.getByRole('button', { name: 'Historial', exact: true }).click()
    await page.getByRole('combobox', { name: 'Filtrar por persona', exact: true }).selectOption({ label: 'worker' })
    await expect(page.locator('.history-list > li')).toHaveCount(1)
    await page.getByRole('button', { name: 'Ver venta 2', exact: true }).click()
    await page.getByLabel('Motivo de anulación', { exact: true }).fill('Error de carga')
    await page.getByRole('button', { name: 'Revisar anulación', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Cancelar', exact: true })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: 'Revisar anulación', exact: true })).toBeFocused()
    await page.getByRole('button', { name: 'Revisar anulación', exact: true }).press('Enter')
    await accessible(page)
    await screenshot(page, 'void-confirmation-desktop')
    await page.getByRole('button', { name: 'Confirmar anulación de venta', exact: true }).press('Enter')
    await expect(page.getByRole('heading', { name: 'Venta #2 · Anulada', exact: true })).toBeVisible()
    await page.getByRole('combobox', { name: 'Estado de venta', exact: true }).selectOption('VOIDED')
    await page.getByRole('button', { name: 'Ver venta 2', exact: true }).click()
    await ticketPdf(page, 'ticket-58mm-voided')
    await screens(page, 'history')
    // Segundo reinicio: persisten ventas, pagos, estado de anulación y stock.
    await stop(api)
    api = startApi()
    await ready('http://127.0.0.1:8765/api/health', api)
    await page.reload()
    await page.getByRole('button', { name: 'Historial', exact: true }).click()
    await expect(page.locator('.history-list > li')).toHaveCount(2)
    await page.getByRole('button', { name: 'Ver venta 2', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Venta #2 · Anulada', exact: true })).toBeVisible()
    expect(await page.evaluate(async () => (await fetch('/api/products/1').then(response => response.json())).stock_quantity)).toBe(2)
    // F5: misma SQLite y ventas reales, después de anular y reiniciar.
    await expect(worker.getByRole('button', { name: 'Reportes', exact: true })).toHaveCount(0)
    expect(await worker.evaluate(async () => (await fetch('/api/reports/summary')).status)).toBe(403)
    let releaseReport!: () => void
    const reportGate = new Promise<void>(resolve => { releaseReport = resolve })
    // StrictMode puede montar/cancelar/repetir la lectura inicial: retener todas.
    const holdReports = async (route: import('@playwright/test').Route) => {
      await reportGate
      return route.continue()
    }
    await page.route('**/api/reports/summary?*', holdReports)
    await page.getByRole('button', { name: 'Reportes', exact: true }).press('Enter')
    await expect(page.getByText('Cargando reporte…', { exact: true })).toBeVisible()
    await screens(page, 'reports-loading')
    await expect(page.getByText('Cargando reporte…', { exact: true })).toBeVisible()
    releaseReport()
    await expect(page.getByRole('heading', { name: 'Resumen del período', exact: true })).toBeFocused()
    await expect(page.locator('.report-kpi').filter({ has: page.getByRole('heading', { name: 'Ventas', exact: true }) }).locator('.report-value')).toHaveText('1')
    await page.unroute('**/api/reports/summary?*', holdReports)
    const realReport = await page.evaluate(async () => fetch('/api/reports/summary').then(r => r.json()))
    expect(realReport.current.sales).toBe('1')
    // La expectativa del importe se comprueba contra la venta histórica real.
    const historicalTotal = await page.evaluate(async () => (await fetch('/api/sales/1').then(r => r.json())).total_cents)
    expect(realReport.current.revenue_cents).toBe(String(historicalTotal))
    expect(realReport.top_units[0].name).toBe('Agua mineral')
    await screens(page, 'reports-summary')
    await page.getByRole('combobox', { name: 'Ordenar por', exact: true }).selectOption('revenue')
    await page.getByRole('combobox', { name: 'Mostrar por hora', exact: true }).selectOption('revenue_cents')
    await expect(page.getByRole('table')).toContainText('Facturación en ARS por hora local')
    for (const period of ['yesterday', '7d', '30d', 'today']) {
      await page.getByRole('combobox', { name: 'Período', exact: true }).selectOption(period)
      await page.getByRole('button', { name: 'Consultar', exact: true }).press('Enter')
      await expect(page.getByRole('heading', { name: 'Resumen del período', exact: true })).toBeFocused()
    }
    await page.getByRole('combobox', { name: 'Período', exact: true }).selectOption('custom')
    await page.getByLabel('Desde', { exact: true }).fill('2000-01-01')
    await page.getByLabel('Hasta', { exact: true }).fill('2000-01-02')
    await page.getByRole('button', { name: 'Consultar', exact: true }).press('Enter')
    await expect(page.getByText('No hay ventas completadas en este período. Probá otras fechas.', { exact: true })).toBeVisible()
    await screens(page, 'reports-empty')
    await page.getByLabel('Desde', { exact: true }).fill('2000-01-03')
    await page.getByRole('button', { name: 'Consultar', exact: true }).press('Enter')
    await expect(page.getByRole('alert')).toBeFocused()
    await expect(page.getByRole('alert')).toContainText('Elegí un rango')
    await page.route('**/api/reports/summary?*', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Base local no disponible; reintentá el reporte' }) }), { times: 1 })
    await page.getByRole('combobox', { name: 'Período', exact: true }).selectOption('today')
    await page.getByRole('button', { name: 'Consultar', exact: true }).press('Enter')
    await expect(page.getByRole('alert')).toContainText('Base local no disponible')
    await screens(page, 'reports-error')
    await page.getByRole('button', { name: 'Reintentar reporte', exact: true }).press('Enter')
    await expect(page.getByRole('heading', { name: 'Resumen del período', exact: true })).toBeFocused()
    await page.emulateMedia({ reducedMotion: 'reduce' })
    expect(await page.locator('.reports .button').first().evaluate(e => getComputedStyle(e).transitionDuration)).toBe('0s')
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    // Repetir navegación y selección no dispara bucles ni conserva errores de otra vista.
    await page.getByRole('button', { name: 'Reportes', exact: true }).click()
    await expect(page.getByRole('alert')).toHaveCount(0)
    await page.getByRole('button', { name: 'Equipo', exact: true }).click()
    await page.getByRole('button', { name: 'Desactivar worker', exact: true }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Cancelar', exact: true })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Desactivar worker', exact: true })).toBeFocused()
    await page.getByRole('button', { name: 'Desactivar worker', exact: true }).press('Enter')
    await accessible(page)
    await screenshot(page, 'deactivate-desktop')
    await page.getByRole('button', { name: 'Cancelar', exact: true }).press('Tab')
    await expect(page.getByRole('button', { name: 'Confirmar desactivación', exact: true })).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'Cancelar', exact: true })).toBeFocused()
    await page.keyboard.press('Shift+Tab')
    await page.keyboard.press('Enter')
    await expect(page.getByRole('listitem').filter({ has: page.getByText('worker', { exact: true }) }).getByText('Inactivo', { exact: true })).toBeVisible()
    await worker.reload()
    await expect(worker.getByRole('heading', { name: 'Ingresar', exact: true })).toBeVisible()
    await worker.getByLabel('Usuario', { exact: true }).fill('worker')
    await worker.getByLabel('Contraseña', { exact: true }).fill('E2e-password-worker-42')
    await worker.getByRole('button', { name: 'Ingresar', exact: true }).click()
    await expect(worker.getByRole('alert')).toHaveText('Usuario o contraseña incorrectos')
    // F6: importación confirmada/recuperada, respaldo real y restauración con reautenticación.
    await page.getByRole('button', { name: 'Herramientas', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Respaldos de tu negocio', exact: true })).toBeVisible()
    const csv = 'nombre;codigo;precio;stock_inicial;stock_minimo\nProducto CSV;00991;1,25;3;1\n'
    await page.getByLabel('Archivo CSV', { exact: true }).setInputFiles({ name: 'productos.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) })
    await expect(page.getByRole('heading', { name: 'Vista previa: 1 producto válido', exact: true })).toBeVisible()
    await page.getByLabel('Motivo de la carga', { exact: true }).fill('Carga de prueba CSV')
    await screens(page, 'tools-preview')
    const importRequests: unknown[] = []
    await page.route('**/api/imports/products/confirm', async route => {
      importRequests.push(route.request().postDataJSON())
      if (importRequests.length === 1) {
        const committed = await route.fetch()
        expect(committed.status()).toBe(200)
        return route.abort('failed')
      }
      return route.continue()
    })
    await page.getByRole('button', { name: 'Revisar importación', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Cancelar', exact: true })).toBeFocused()
    await page.getByRole('button', { name: 'Confirmar importación', exact: true }).press('Enter')
    await expect(page.getByRole('button', { name: 'Reintentar la misma importación', exact: true })).toBeVisible()
    await page.reload()
    await page.getByRole('button', { name: 'Herramientas', exact: true }).click()
    await page.getByRole('button', { name: 'Reintentar la misma importación', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Importación recuperada o completada: 1 producto.' })).toBeVisible()
    expect(importRequests).toHaveLength(2)
    expect(importRequests[0]).toEqual(importRequests[1])
    expect(await page.evaluate(async () => (await fetch('/api/products?search=00991').then(r => r.json())).total)).toBe(1)
    await page.getByRole('button', { name: 'Crear respaldo ahora', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Respaldo creado y verificado.' })).toBeVisible()
    await screens(page, 'tools-backups')
    // Descargar para guardar externamente y volver a incorporar sin reemplazar datos.
    const downloadEvent = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Descargar', exact: true }).first().click()
    const downloaded = await downloadEvent
    const localBackup = await downloaded.path()
    expect(localBackup).not.toBeNull()
    await page.getByLabel('Incorporar respaldo externo (solo archivos de confianza)', { exact: true }).setInputFiles(localBackup!)
    await expect(page.getByRole('status').filter({ hasText: 'Respaldo externo validado.' })).toBeVisible()
    // Dato posterior que debe desaparecer al restaurar la copia elegida.
    expect(await page.evaluate(async () => {
      const me = await fetch('/api/auth/me').then(r => r.json())
      return (await fetch('/api/products', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token }, body: JSON.stringify({ name: 'Posterior a respaldo', price_cents: 100 }) })).status
    })).toBe(201)
    await page.getByRole('button', { name: 'Preparar restauración', exact: true }).first().click()
    await page.getByLabel('Contraseña ADMIN para restaurar', { exact: true }).fill('E2e-password-owner-42')
    await page.getByLabel('Escribí RESTAURAR', { exact: true }).fill('RESTAURAR')
    await page.getByRole('button', { name: 'Revisar restauración', exact: true }).click()
    // No capturar campos secretos poblados; la confirmación se prueba por teclado.
    await page.getByRole('button', { name: 'Confirmar restauración', exact: true }).press('Enter')
    await expect(page.getByRole('heading', { name: 'Ingresar', exact: true })).toBeVisible()
    await page.getByLabel('Usuario', { exact: true }).fill('owner')
    await page.getByLabel('Contraseña', { exact: true }).fill('E2e-password-owner-42')
    await page.getByRole('button', { name: 'Ingresar', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Herramientas', exact: true })).toBeVisible()
    expect(await page.evaluate(async () => (await fetch('/api/products?search=Posterior').then(r => r.json())).total)).toBe(0)
    expect(await page.evaluate(async () => (await fetch('/api/products?search=00991').then(r => r.json())).items[0].stock_quantity)).toBe(3)
    expect(await page.evaluate(async () => (await fetch('/api/reports/summary').then(r => r.json())).current.sales)).toBe('1')
    await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Ingresar', exact: true })).toBeVisible()
    expect(external).toEqual([])
    expect(errors).toEqual([])
  } finally {
    await context.close()
    await workerContext.close()
    await stop(vite)
    await stop(api)
    // Solo se elimina el directorio temporal creado por esta prueba.
    rmSync(root, { recursive: true, force: true })
  }
})
