import { ApiError } from './identity'
export type CsvRow = { row: number; name: string; code: string | null; price_cents: number; initial_stock: number; minimum_stock: number }
export type Preview = { source_hash: string; rows: CsvRow[]; errors: { row: number; message: string }[] }
export type ImportAttempt = { content: string; source_hash: string; reason: string; idempotency_key: string }
export type Backup = { id: string; kind: string; created_at_utc: string; schema_revision: string; size_bytes: number }
export type Settings = { enabled: number; interval_hours: number; retention: number; last_attempt: number; last_success: number; last_error: string | null }
export type Status = { settings: Settings; backups: Backup[]; shutdown_available: boolean }
async function request<T>(path: string, csrf: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, { method, credentials: 'same-origin', headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(method !== 'GET' ? { 'X-CSRF-Token': csrf } : {}) }, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) })
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null)
    throw new ApiError(response.status, typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string' ? data.detail : 'No pudimos completar la operación local.')
  }
  return response.json() as Promise<T>
}
export const status = (csrf: string) => request<Status>('/backups', csrf)
export const createBackup = (csrf: string) => request<Backup>('/backups', csrf, 'POST', {})
export const settings = (csrf: string, enabled: boolean, interval_hours: number, retention: number) => request<Settings>('/backups/settings', csrf, 'PUT', { enabled, interval_hours, retention })
export const preview = (csrf: string, content: string) => request<Preview>('/imports/products/preview', csrf, 'POST', { content })
export async function confirmImport(csrf: string, attempt: ImportAttempt): Promise<number[]> {
  const result = await request<{ product_ids: number[]; replayed: boolean }>('/imports/products/confirm', csrf, 'POST', attempt)
  if (!Array.isArray(result.product_ids) || result.product_ids.length < 1 || result.product_ids.length > 500 || !result.product_ids.every(id => Number.isSafeInteger(id) && id > 0) || typeof result.replayed !== 'boolean') throw new Error('No pudimos verificar la importación. Conservamos el intento para recuperarlo.')
  return result.product_ids
}
export const restore = (csrf: string, backup_id: string, password: string) => request<{ restored: boolean; previous_backup_id: string }>('/backups/restore', csrf, 'POST', { backup_id, password, confirmation: 'RESTAURAR' })
export const shutdown = (csrf: string) => request('/runtime/shutdown', csrf, 'POST', {})
export async function uploadBackup(csrf: string, file: File): Promise<Backup> {
  if (file.size > 32 * 1024 * 1024 + 65536) throw new Error('El respaldo supera 32 MiB.')
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ''
  for (let offset = 0; offset < bytes.length; offset += 32768) binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768))
  return request('/backups/upload', csrf, 'POST', { content_base64: btoa(binary) })
}
export async function downloadBackup(backup: Backup): Promise<void> {
  const response = await fetch(`/api/backups/${backup.id}/download`, { credentials: 'same-origin' })
  if (!response.ok) throw new ApiError(response.status, 'No pudimos descargar el respaldo. Reintentá.')
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a'); link.href = url; link.download = `pos-${backup.id}.posbackup`; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
const key = (user: number) => `pos.import.pending.v1.${user}`
export function loadImport(user: number): ImportAttempt | null {
  const raw = sessionStorage.getItem(key(user))
  if (raw === null) return null
  const data: unknown = JSON.parse(raw)
  if (typeof data !== 'object' || data === null || !('content' in data) || typeof data.content !== 'string' || data.content.length > 1048576 || !('source_hash' in data) || typeof data.source_hash !== 'string' || !/^[0-9a-f]{64}$/.test(data.source_hash) || !('reason' in data) || typeof data.reason !== 'string' || data.reason.length < 3 || data.reason.length > 240 || !('idempotency_key' in data) || typeof data.idempotency_key !== 'string' || !/^[0-9a-f-]{36}$/.test(data.idempotency_key)) throw new Error('El intento de importación guardado no pudo verificarse. Consultá Catálogo antes de volver a importar.')
  return data as ImportAttempt
}
export function saveImport(user: number, attempt: ImportAttempt) { sessionStorage.setItem(key(user), JSON.stringify(attempt)) }
export function clearImport(user: number) { sessionStorage.removeItem(key(user)) }
