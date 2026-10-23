import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { expect, test, vi } from 'vitest'

test('cloud demo loads the real setup UI and calls the API instead of replacing the software with a static preview', async () => {
  vi.stubEnv('MODE', 'cloud-demo')
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    if (input === '/api/health') return Response.json({ status: 'ok' })
    if (input === '/api/auth/setup') return Response.json({ initialized: false })
    if (input === '/api/auth/me') return Response.json({ detail: 'Sin sesión' }, { status: 401 })
    throw new Error(`Unexpected API request: ${String(input)}`)
  })
  vi.stubGlobal('fetch', fetcher)
  const container = document.createElement('div')
  document.body.append(container)
  const root = createRoot(container)
  try {
    const { default: App } = await import('../src/App')
    await act(async () => { root.render(createElement(App)) })
    expect(container.textContent).toContain('DEMO DE PRUEBA')
    expect(container.textContent).toContain('Demo conectada')
    expect(container.textContent).toContain('Crear administrador')
    expect(container.textContent).toContain('POS_DEMO_SETUP_TOKEN')
    expect(container.querySelectorAll('input')).toHaveLength(3)
    expect(fetcher).toHaveBeenCalledTimes(3)
    expect(container.textContent).not.toContain('Tus datos quedan en este equipo')
  } finally {
    await act(async () => { root.unmount() })
    container.remove()
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  }
})
