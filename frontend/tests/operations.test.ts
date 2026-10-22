import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearImport, confirmImport, loadImport, saveImport } from '../src/operations'
const attempt = { content: 'CSV ficticio', source_hash: 'a'.repeat(64), reason: 'Carga inicial', idempotency_key: '00000000-0000-4000-8000-000000000001' }
beforeEach(() => { sessionStorage.clear(); vi.unstubAllGlobals() })
describe('importación recuperable', () => {
  it('conserva el intento por cuenta, sin compartirlo con otra', () => {
    saveImport(1, attempt)
    expect(loadImport(1)).toEqual(attempt)
    expect(loadImport(2)).toBeNull()
    clearImport(1); expect(loadImport(1)).toBeNull()
  })
  it('no descarta silenciosamente un intento corrupto', () => {
    sessionStorage.setItem('pos.import.pending.v1.1', '{}')
    expect(() => loadImport(1)).toThrow('no pudo verificarse')
    expect(sessionStorage.getItem('pos.import.pending.v1.1')).toBe('{}')
  })
  it('solo acepta confirmación con IDs válidos antes de liberar el intento', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ product_ids: [], replayed: false }) }))
    await expect(confirmImport('csrf', attempt)).rejects.toThrow('Conservamos el intento')
  })
  it('mantiene estado HTTP para decidir reautenticación/reintento', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ detail: 'Sesión vencida' }) }))
    await expect(confirmImport('csrf', attempt)).rejects.toMatchObject({ status: 401 })
  })
})
