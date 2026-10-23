import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import type { Credentials } from './identity'
import { Button, Field, Icon, Notice } from './ui'

export function CredentialForm({ title, kind, submit, disabled = false, onBusyChange, remoteDemo = false }: {
  title: string; kind: 'setup' | 'login' | 'employee'; onBusyChange?: (value: boolean) => void;
  submit: (value: Credentials, token: string) => Promise<void>; disabled?: boolean; remoteDemo?: boolean
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(false)
  const formRef = useRef<HTMLFormElement>(null)
  const restoreFieldFocus = useRef(false)
  useEffect(() => {
    if (!busy && restoreFieldFocus.current) {
      restoreFieldFocus.current = false
      formRef.current?.querySelector<HTMLInputElement>('[name="username"]')?.focus()
    }
  }, [busy])
  const titleId = useId()
  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending.current || disabled) return
    pending.current = true
    const form = event.currentTarget
    const data = new FormData(form)
    setBusy(true); onBusyChange?.(true); setError('')
    try {
      await submit({ username: String(data.get('username')), password: String(data.get('password')) }, String(data.get('setup_token') ?? ''))
      form.reset()
      restoreFieldFocus.current = true
    } catch (error) { setError(error instanceof Error ? error.message : 'No pudimos conectar. Intentá nuevamente.') }
    finally { pending.current = false; setBusy(false); onBusyChange?.(false) }
  }
  return <form ref={formRef} onSubmit={onSubmit} aria-labelledby={titleId} className="credential-form" aria-busy={busy}>
    <div className="form-heading">
      <span className="eyebrow">{kind === 'setup' ? 'CONFIGURACIÓN INICIAL' : kind === 'login' ? 'ACCESO PERSONAL' : 'NUEVA CUENTA'}</span>
      <h2 id={titleId}>{title}</h2>
      <p>{kind === 'setup' ? remoteDemo ? 'Creá tu cuenta para administrar esta demo.' : 'Creá tu cuenta para administrar este equipo.' : kind === 'login' ? 'Usá tu cuenta para continuar.' : 'Un acceso propio para cada persona.'}</p>
    </div>
    {error && <Notice tone="error" focus>{error}</Notice>}
    <fieldset disabled={busy || disabled}>
      {kind === 'setup' && <Field label="Secreto de inicialización" hint={remoteDemo ? 'Usá el valor POS_DEMO_SETUP_TOKEN del panel de Render. No lo compartas.' : 'Usá el secreto del archivo generado en este equipo. No lo compartas.'} name="setup_token" type="password" autoComplete="off" required minLength={32} maxLength={128} />}
      <Field label="Usuario" hint={kind === 'login' ? 'El nombre con el que se creó tu cuenta.' : '3–32 letras, números, puntos, guiones o guiones bajos.'} name="username" placeholder={kind === 'login' ? 'Tu nombre de usuario' : 'Ej.: nombre.apellido'} required minLength={3} maxLength={32} pattern="[A-Za-z0-9_.\-]+" autoCapitalize="none" spellCheck={false} autoComplete={kind === 'login' ? 'username' : 'off'} />
      <Field label="Contraseña" hint={kind === 'login' ? 'Tu contraseña personal. Respetá mayúsculas y minúsculas.' : 'Entre 12 y 128 caracteres. Elegí una contraseña única.'} name="password" type="password" placeholder={kind === 'login' ? 'Tu contraseña' : 'Creá una contraseña segura'} required minLength={12} maxLength={128} autoComplete={kind === 'login' ? 'current-password' : 'new-password'} />
      <Button type="submit" className="button--full" busy={busy}>
        {busy ? 'Procesando…' : title}{!busy && <Icon name={kind === 'employee' ? 'plus' : 'arrow'} />}
      </Button>
    </fieldset>
    {kind !== 'employee' && <p className="form-footnote"><Icon name="lock" />{remoteDemo ? 'Demo remota. Usá una contraseña exclusiva para esta prueba.' : 'Tu acceso es personal. Tus datos quedan en este equipo.'}</p>}
  </form>
}
