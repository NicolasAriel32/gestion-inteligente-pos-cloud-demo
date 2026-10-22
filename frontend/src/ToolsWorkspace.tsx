import { useEffect, useId, useRef, useState } from 'react'
import type { InputHTMLAttributes } from 'react'
import { ApiError } from './identity'
import type { Session } from './identity'
import { formatMoney } from './catalog'
import { Button, ConfirmDialog, Field, Notice, Panel } from './ui'
import * as api from './operations'
import type { Backup, ImportAttempt, Preview, Status } from './operations'

const kind = (value: string) => ({ manual: 'Manual', automatic: 'Automático', uploaded: 'Incorporado', pre_restore: 'Previo a restauración', pre_upgrade: 'Previo a actualización', invalid: 'No válido' }[value] ?? value)
const when = (value: string | number) => value ? new Date(typeof value === 'number' ? value * 1000 : value).toLocaleString('es-AR', { timeZone: 'America/Argentina/Buenos_Aires' }) : 'Todavía no se realizó'
function FileField({ label, onChange, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const id = useId()
  const [name, setName] = useState('Ningún archivo elegido')
  return <div className="file-field"><label htmlFor={id}>{label}</label><div className="file-picker"><span aria-hidden="true">Elegir archivo</span><input {...props} id={id} type="file" onChange={event => { setName(event.target.files?.[0]?.name ?? 'Ningún archivo elegido'); onChange?.(event) }} /></div><span className="file-name">{name}</span></div>
}
export default function ToolsWorkspace({ session, onBusyChange, onExpired }: { session: Session; onBusyChange: (busy: boolean) => void; onExpired: () => void }) {
  const [data, setData] = useState<Status | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [revision, setRevision] = useState(0)
  const [csv, setCsv] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState<ImportAttempt | null>(null)
  const [storageError, setStorageError] = useState('')
  const [restoreTarget, setRestoreTarget] = useState<Backup | null>(null)
  const [password, setPassword] = useState('')
  const [literal, setLiteral] = useState('')
  const [confirm, setConfirm] = useState<'import' | 'restore' | 'shutdown' | null>(null)
  const running = useRef(false)
  const expired = useRef(onExpired)
  useEffect(() => { expired.current = onExpired }, [onExpired])
  useEffect(() => {
    try { setPending(api.loadImport(session.user.id)) } catch (e) { setStorageError((e as Error).message) }
  }, [session.user.id])
  useEffect(() => {
    let active = true
    setLoading(true)
    api.status(session.csrf_token).then(value => { if (active) setData(value) }).catch(e => {
      if (!active) return
      if (e instanceof ApiError && e.status === 401) expired.current()
      setError(e instanceof Error ? e.message : 'No pudimos consultar las herramientas.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [session.csrf_token, revision])
  async function run(action: () => Promise<void>) {
    if (running.current) return
    running.current = true; setBusy(true); onBusyChange(true); setError(''); setNotice('')
    try { await action(); setRevision(n => n + 1) }
    catch (e) { if (e instanceof ApiError && e.status === 401) onExpired(); setError(e instanceof Error ? e.message : 'No se pudo completar. Volvé a intentar.') }
    finally { setConfirm(null); running.current = false; setBusy(false); onBusyChange(false) }
  }
  async function importProducts() {
    const attempt = pending ?? { content: csv, source_hash: preview!.source_hash, reason: reason.trim(), idempotency_key: crypto.randomUUID() }
    api.saveImport(session.user.id, attempt); setPending(attempt)
    try {
      const ids = await api.confirmImport(session.csrf_token, attempt)
      api.clearImport(session.user.id); setPending(null); setCsv(''); setPreview(null); setReason('')
      setNotice(`Importación recuperada o completada: ${ids.length} ${ids.length === 1 ? 'producto' : 'productos'}. Consultá Catálogo para verlos.`)
    } catch (e) {
      if (e instanceof ApiError && e.status >= 400 && e.status < 500 && e.status !== 401 && !e.message.includes('clave de importación')) { api.clearImport(session.user.id); setPending(null); setPreview(null) }
      throw e
    }
  }
  return <div className="tools-workspace">
    {error && <Notice tone="error" focus>{error}</Notice>}{notice && <Notice focus>{notice}</Notice>}
    {loading && !data && <p role="status">Consultando herramientas locales…</p>}
    {!data && error && <Button onClick={() => { setError(''); setRevision(n => n + 1) }}>Reintentar herramientas</Button>}
    <Panel className="tools-panel"><h2>Importar productos</h2><p>Altas nuevas desde CSV UTF-8, hasta 500 productos y 1 MiB. Separador punto y coma. Los códigos conservan ceros iniciales.</p><p className="csv-format">nombre;codigo;precio;stock_inicial;stock_minimo</p><p>Precio en pesos, sin miles y con hasta dos decimales. Stock en unidades enteras. No modifica productos existentes.</p>
      {storageError ? <Notice tone="error">{storageError}</Notice> : pending ? <><Notice>Hay una importación con respuesta pendiente. Recuperá el mismo intento antes de importar otro archivo.</Notice><Button busy={busy} onClick={() => void run(importProducts)}>Reintentar la misma importación</Button></> : <>
        <FileField label="Archivo CSV" accept=".csv,text/csv" disabled={busy} onChange={event => { const file = event.target.files?.[0]; setPreview(null); setCsv(''); if (file) void run(async () => { if (file.size > 1048576) throw new Error('El CSV supera 1 MiB.'); const content = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer()); setCsv(content); setPreview(await api.preview(session.csrf_token, content)) }) }} />
        {preview && <div className="csv-preview"><h3>Vista previa: {preview.rows.length} {preview.rows.length === 1 ? 'producto válido' : 'productos válidos'}</h3>{preview.errors.length > 0 && <Notice tone="error">Corregí los errores antes de importar.<ul>{preview.errors.map(e => <li key={e.row}>Fila {e.row}: {e.message}</li>)}</ul></Notice>}
          <div className="tools-table"><table><caption>Primeros 20 productos de la vista previa</caption><thead><tr><th>Producto</th><th>Código</th><th>Precio</th><th>Stock</th></tr></thead><tbody>{preview.rows.slice(0, 20).map(row => <tr key={row.row}><td>{row.name}</td><td>{row.code ?? 'Sin código'}</td><td>{formatMoney(row.price_cents)}</td><td>{row.initial_stock}</td></tr>)}</tbody></table></div>
          <form onSubmit={e => { e.preventDefault(); setConfirm('import') }}><Field label="Motivo de la carga" hint="Se registra con el stock inicial (3–240 caracteres)." value={reason} minLength={3} maxLength={240} required disabled={busy} onChange={e => setReason(e.target.value)} /><Button type="submit" disabled={busy || preview.errors.length > 0 || preview.rows.length === 0}>Revisar importación</Button></form>
        </div>}
      </>}
    </Panel>
    <Panel className="tools-panel"><h2>Respaldos de tu negocio</h2><p>Guardá una copia antes de actualizar o restaurar. Descargala y conservala en un medio externo seguro; una copia en este disco no protege ante su pérdida.</p><Button busy={busy} onClick={() => void run(async () => { await api.createBackup(session.csrf_token); setNotice('Respaldo creado y verificado. Ya podés descargarlo.') })}>Crear respaldo ahora</Button>
      {data && <><form className="backup-settings" key={`${data.settings.enabled}-${data.settings.interval_hours}-${data.settings.retention}`} onSubmit={e => { e.preventDefault(); const fields = new FormData(e.currentTarget); void run(async () => { await api.settings(session.csrf_token, fields.get('enabled') === 'on', Number(fields.get('hours')), Number(fields.get('retention'))); setNotice('Configuración de respaldos guardada.') }) }}><fieldset disabled={busy}><legend>Respaldo automático</legend><label className="check-label"><input name="enabled" type="checkbox" defaultChecked={Boolean(data.settings.enabled)} />Activar mientras la aplicación esté abierta</label><Field label="Cada cuántas horas" hint="De 1 a 168. Al reabrir se comprueba si quedó pendiente." name="hours" type="number" min={1} max={168} required defaultValue={data.settings.interval_hours} /><Field label="Copias automáticas a conservar" hint="De 1 a 30. No borra copias manuales ni previas a restauración." name="retention" type="number" min={1} max={30} required defaultValue={data.settings.retention} /><Button type="submit">Guardar respaldos automáticos</Button></fieldset></form><p>Último respaldo automático: {when(data.settings.last_success)}</p>{data.settings.last_error && <Notice tone="error">{data.settings.last_error}</Notice>}
        <ul className="backup-list">{data.backups.map(backup => <li key={backup.id}><div><strong>{kind(backup.kind)}</strong><span>{when(backup.created_at_utc)} · {Math.ceil(backup.size_bytes / 1024)} KiB</span></div><div className="backup-actions"><Button variant="secondary" disabled={busy || backup.kind === 'invalid'} onClick={() => void run(() => api.downloadBackup(backup))}>Descargar</Button><Button variant="quiet" disabled={busy || backup.kind === 'invalid' || backup.kind === 'pre_upgrade'} onClick={() => { setRestoreTarget(backup); setPassword(''); setLiteral(''); setNotice(''); setError('') }}>Preparar restauración</Button></div></li>)}</ul>{data.backups.length === 0 && <p>No hay respaldos guardados todavía.</p>}</>}
      <FileField label="Incorporar respaldo externo (solo archivos de confianza)" accept=".posbackup" disabled={busy} onChange={e => { const file = e.target.files?.[0]; if (file) void run(async () => { await api.uploadBackup(session.csrf_token, file); setNotice('Respaldo externo validado. Incorporarlo no reemplaza tus datos; requiere restauración confirmada.') }) }} />
    </Panel>
    {restoreTarget && <Panel className="tools-panel restore-panel"><h2>Restaurar un respaldo</h2><p>Vas a reemplazar los datos por la copia del {when(restoreTarget.created_at_utc)}. Se perderán los cambios posteriores en la base activa. Primero se guardará una copia del estado actual.</p><p>Terminá y comprobá todas las ventas e importaciones pendientes antes de continuar. Se cerrarán todas las sesiones; los intentos anteriores deberán revisarse en Historial.</p><form onSubmit={e => { e.preventDefault(); setConfirm('restore') }}><Field label="Contraseña ADMIN para restaurar" hint="Debe ser válida también en el respaldo de esta misma cuenta." type="password" autoComplete="current-password" minLength={12} maxLength={128} required value={password} disabled={busy} onChange={e => setPassword(e.target.value)} /><Field label="Escribí RESTAURAR" hint="Confirma que revisaste la fecha y las operaciones pendientes." required pattern="RESTAURAR" value={literal} disabled={busy} onChange={e => setLiteral(e.target.value)} /><Button type="submit" disabled={busy || literal !== 'RESTAURAR'}>Revisar restauración</Button><Button type="button" variant="secondary" disabled={busy} onClick={() => { setRestoreTarget(null); setPassword(''); setLiteral('') }}>Cancelar restauración</Button></form></Panel>}
    {data?.shutdown_available && <Panel className="tools-panel"><h2>Cerrar la aplicación local</h2><p>Terminá tus operaciones antes de cerrar. El servidor se detendrá de forma controlada; cerrar solo la pestaña lo deja funcionando.</p><Button variant="secondary" disabled={busy} onClick={() => setConfirm('shutdown')}>Cerrar aplicación</Button></Panel>}
    {confirm && <ConfirmDialog title={confirm === 'import' ? '¿Importar estos productos?' : confirm === 'restore' ? '¿Reemplazar los datos con el respaldo?' : '¿Cerrar la aplicación local?'} description={confirm === 'import' ? `Se crearán ${preview?.rows.length ?? 0} productos con su stock inicial. No se modificarán productos existentes.` : confirm === 'restore' ? 'Esta acción retrocede ventas, stock y cuentas a la fecha elegida. Se guarda una copia previa y se cierran las sesiones.' : 'Se esperará el cierre de operaciones del servidor. Podés volver a abrir desde el acceso directo.'} confirmLabel={confirm === 'import' ? 'Confirmar importación' : confirm === 'restore' ? 'Confirmar restauración' : 'Confirmar cierre'} busy={busy} onCancel={() => setConfirm(null)} onConfirm={() => void run(async () => { if (confirm === 'import') await importProducts(); else if (confirm === 'restore' && restoreTarget) { const secret = password; setPassword(''); await api.restore(session.csrf_token, restoreTarget.id, secret); onExpired() } else { await api.shutdown(session.csrf_token); setNotice('Cierre solicitado. Ya podés cerrar esta pestaña.') } })} />}
  </div>
}
