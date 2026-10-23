import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { getHealth } from './api'
import * as identity from './identity'
import type { Session, User } from './identity'
import HelpCenter from './HelpCenter'
import { CredentialForm } from './CredentialForm'
import { Button, ConfirmDeactivation, Icon, Notice, Panel } from './ui'
import './style.css'

const CatalogWorkspace = lazy(() => import('./CatalogWorkspace'))
const ReportsWorkspace = lazy(() => import('./ReportsWorkspace'))
const SalesWorkspace = lazy(() => import('./SalesWorkspace'))
const cloudDemo = import.meta.env.MODE === 'cloud-demo'
const sectionCopy = {
  reports: ['REPORTES', 'Tu negocio, en números.', 'Ventas reales para acompañar tus decisiones.'],
  catalog: ['CATÁLOGO', 'Productos para tu negocio.', 'Precios claros y productos organizados.'],
  inventory: ['INVENTARIO', 'Cada unidad, en orden.', 'Consultá existencias y registrá cada cambio con su motivo.'],
  checkout: ['CAJA', 'Una venta, bien registrada.', 'Elegí productos, revisá el importe y registrá el pago informado.'],
  history: ['HISTORIAL', 'Cada venta tiene su historia.', 'Consultá comprobantes y seguí el estado de tus ventas.'],
} as const

type View = { initialized: boolean; session: Session | null; staff: User[] }
async function readView(): Promise<View> {
  const [initialized, session] = await Promise.all([identity.setupStatus(), identity.currentSession()])
  const staff = session?.user.role === 'ADMIN' ? await identity.employees() : []
  return { initialized, session, staff }
}

export default function App() {
  const [section, setSection] = useState<'team' | 'catalog' | 'inventory' | 'checkout' | 'history' | 'reports'>('team')
  const [view, setView] = useState<View | null>(null)
  const [health, setHealth] = useState(cloudDemo ? 'Conectando con la demo…' : 'Comprobando conexión local…')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [noticeFocus, setNoticeFocus] = useState(false)
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState<User | null>(null)
  const actionPending = useRef(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const staff = view?.staff ?? []
  const session = view?.session
  const stage = !view ? 'loading' : !view.initialized ? 'setup' : session ? 'session' : 'login'
  const copy = section === 'team' ? session?.user.role === 'ADMIN' ? ['PERSONAS Y ACCESOS', 'Un buen equipo empieza acá.', 'Gestioná quién puede ingresar. Cada persona, con su propia cuenta.'] : ['MI CUENTA', `Hola, ${session?.user.username ?? ''}.`, 'Tu sesión está iniciada y tu acceso está listo.'] : sectionCopy[section]
  useEffect(() => {
    let active = true
    getHealth().then(() => { if (active) setHealth(cloudDemo ? 'Demo conectada' : 'Servidor local conectado') })
      .catch(() => { if (active) setHealth(cloudDemo ? 'Demo todavía no disponible' : 'Servidor local no disponible') })
    readView().then(value => { if (active) setView(value) })
      .catch(() => { if (active) setError(cloudDemo ? 'No pudimos conectar con la demo. Si el servidor gratuito estaba suspendido, esperá un minuto y volvé a intentar.' : 'No pudimos cargar tus datos. Comprobá que la aplicación local esté iniciada y volvé a intentar.') })
    return () => { active = false }
  }, [])
  useEffect(() => { if (stage !== 'loading') heading.current?.focus() }, [stage, section])

  async function refresh() {
    setView(await readView())
    if (cloudDemo) setHealth('Demo conectada')
  }
  function navigate(next: typeof section) {
    if (next === section) return
    setError(''); setNotice(''); setNoticeFocus(false); setSection(next)
  }
  function expireSession() {
    setView(current => current ? { ...current, session: null, staff: [] } : current)
    setSection('team'); setNotice('Tu sesión terminó. Volvé a ingresar.')
  }
  async function authenticated(action: () => Promise<unknown>) {
    try { await action(); await refresh() }
    catch (error) {
      if (error instanceof identity.ApiError && error.status === 401) {
        setView(current => current ? { ...current, session: null, staff: [] } : current)
        setNotice('Tu sesión terminó. Volvé a ingresar para continuar.')
      }
      throw error
    }
  }
  async function buttonAction(action: () => Promise<unknown>, success = '') {
    if (actionPending.current) return
    actionPending.current = true; setBusy(true); setError(''); setNotice(''); setNoticeFocus(Boolean(success))
    try { await authenticated(action); setConfirm(null); setNotice(success) }
    catch (error) { setConfirm(null); setError(error instanceof Error ? error.message : 'No pudimos conectar. Intentá nuevamente.') }
    finally { actionPending.current = false; setBusy(false) }
  }
  return <div className="app-shell">
    <a className="skip-link" href="#main">Ir al contenido</a>
    <header className="topbar">
      <div className="brand">
        <span className="brand__mark" aria-hidden="true">gi<span>.</span></span>
        <span className="brand__name">Gestión Inteligente<span>Tu negocio, en buenas manos.</span></span>
      </div>
      <div className="topbar__right">
        <span className="connection" role="status"><span className="connection__dot" aria-hidden="true" />{health}</span>
        <div className="topbar__actions">{session && <Button variant="secondary" disabled={busy} onClick={() => void buttonAction(() => identity.logout(session.csrf_token))}><Icon name="exit" />Cerrar sesión</Button>}<HelpCenter key={`${stage}-${session?.user.id ?? 'guest'}`} role={session?.user.role ?? 'GUEST'} disabled={busy} /></div>
      </div>
    </header>
    {cloudDemo && <aside className="cloud-demo-banner" role="note"><strong>DEMO DE PRUEBA</strong> · Todas las funciones implementadas usan el servidor remoto. Usá datos ficticios: pueden perderse cuando el servidor gratuito se reinicie o suspenda. No es una caja de producción.</aside>}
    <main id="main" tabIndex={-1} className={session ? 'workspace' : 'welcome'}>
      {session ? <>
        <div className="workspace__heading">
          <div><span className="eyebrow">{copy[0]}</span>
            <h1 ref={heading} tabIndex={-1}>{copy[1]}</h1>
            <p>{copy[2]}</p></div>
          <div className="account"><span className="avatar" aria-hidden="true">{session.user.username.slice(0, 2).toUpperCase()}</span><div><h2>Sesión de {session.user.username}</h2><span>{session.user.role === 'ADMIN' ? 'Administrador' : 'Empleado'}</span></div></div>
        </div>
        <nav className="workspace-nav" aria-label="Secciones">
          <Button disabled={busy} variant={section === 'team' ? 'primary' : 'secondary'} aria-current={section === 'team' ? 'page' : undefined} onClick={() => navigate('team')}>{session.user.role === 'ADMIN' ? 'Equipo' : 'Mi cuenta'}</Button>
          <Button disabled={busy} variant={section === 'catalog' ? 'primary' : 'secondary'} aria-current={section === 'catalog' ? 'page' : undefined} onClick={() => navigate('catalog')}>Catálogo</Button>
          {session.user.role === 'ADMIN' && <Button disabled={busy} variant={section === 'inventory' ? 'primary' : 'secondary'} aria-current={section === 'inventory' ? 'page' : undefined} onClick={() => navigate('inventory')}>Inventario</Button>}
          <Button disabled={busy} variant={section === 'checkout' ? 'primary' : 'secondary'} aria-current={section === 'checkout' ? 'page' : undefined} onClick={() => navigate('checkout')}>Caja</Button>
          <Button disabled={busy} variant={section === 'history' ? 'primary' : 'secondary'} aria-current={section === 'history' ? 'page' : undefined} onClick={() => navigate('history')}>Historial</Button>
          {session.user.role === 'ADMIN' && <Button disabled={busy} variant={section === 'reports' ? 'primary' : 'secondary'} aria-current={section === 'reports' ? 'page' : undefined} onClick={() => navigate('reports')}>Reportes</Button>}
        </nav>
        {error && <Notice tone="error" focus>{error}</Notice>}{notice && <Notice focus={noticeFocus}>{notice}</Notice>}
        {section === 'reports' ? session.user.role === 'ADMIN' && <Suspense fallback={<Panel><p role="status">Cargando reportes…</p></Panel>}><ReportsWorkspace onExpired={expireSession} /></Suspense> : section === 'checkout' || section === 'history' ? <Suspense fallback={<Panel><p className="catalog-empty" role="status">Cargando herramientas…</p></Panel>}><SalesWorkspace key={session.user.id} mode={section} session={session} onBusyChange={setBusy} onExpired={expireSession} /></Suspense> : section !== 'team' ? <Suspense fallback={<Panel><p className="catalog-empty" role="status">Cargando herramientas…</p></Panel>}><CatalogWorkspace key={section} mode={section} session={session} onBusyChange={setBusy} onExpired={expireSession} /></Suspense> : session.user.role === 'ADMIN' ? <div className="team-layout">
          <Panel className="team-panel" aria-labelledby="team-title">
            <div className="panel-heading"><div className="section-icon"><Icon name="users" /></div><div><h2 id="team-title">Empleados</h2><p>Las cuentas de tu equipo.</p></div><span className="count" aria-label={`${staff.length} empleados`}>{staff.length}</span></div>
            {staff.length === 0 ? <div className="empty-state"><div className="empty-state__symbol"><Icon name="users" /></div><h3>Tu equipo empieza con una persona.</h3><p>Creá la primera cuenta desde el formulario.<br />Cada empleado tendrá su propio acceso.</p></div> : <ul className="employee-list">{staff.map(employee => <li key={employee.id}>
              <span className="avatar avatar--small" aria-hidden="true">{employee.username.slice(0, 2).toUpperCase()}</span>
              <div className="employee-info"><span className="employee-name">{employee.username}</span><span className={`badge ${employee.is_active ? '' : 'badge--inactive'}`}>{employee.is_active ? 'Activo' : 'Inactivo'}</span></div>
              {employee.is_active ? <Button variant="quiet" disabled={busy} aria-label={`Desactivar ${employee.username}`} onClick={() => setConfirm(employee)}>Desactivar</Button> : <span className="employee-disabled">Acceso desactivado</span>}
            </li>)}</ul>}
            <p className="panel-note"><Icon name="lock" />Solo vos, como administrador, podés gestionar estas cuentas.</p>
          </Panel>
          <Panel className="create-panel"><CredentialForm remoteDemo={cloudDemo} onBusyChange={setBusy} kind="employee" title="Crear empleado" disabled={busy} submit={async value => {
            setError(''); setNotice(''); setNoticeFocus(false)
            await authenticated(() => identity.createEmployee(value, session.csrf_token))
            setNotice(`La cuenta de ${value.username.toLowerCase()} ya está creada.`)
          }} /></Panel>
        </div> : <Panel className="employee-welcome"><div className="section-icon"><Icon name="check" /></div><h2>Ya estás adentro.</h2><p>Podés vender desde Caja, consultar tus ventas en Historial y ver productos en Catálogo. Los cambios de catálogo los realiza el administrador.</p></Panel>}
      </> : <>
        <div className="welcome__story">
          <span className="eyebrow">GESTIÓN SIMPLE. TODOS LOS DÍAS.</span>
          <h1 ref={heading} tabIndex={-1}>{stage === 'setup' ? <>El primer paso,<br /><span>bien acompañado.</span></> : <>Qué bueno verte.<br /><span>Sigamos.</span></>}</h1>
          <p className="welcome__intro">{stage === 'setup' ? 'Dejá listo el acceso a tu negocio. Empezamos por tu cuenta de administrador.' : 'Un lugar para vos y tu equipo. Ingresá con tu cuenta y continuá con tranquilidad.'}</p>
          <div className="welcome__benefits"><span><Icon name="users" />Una cuenta por persona</span><span><Icon name="lock" />{cloudDemo ? 'Datos ficticios en la demo' : 'Tus datos, en tu equipo'}</span><span><Icon name="check" />{cloudDemo ? 'Acceso desde el navegador' : 'Sin conexión obligatoria'}</span></div>
          <p className="welcome__signature">Cerca de tu negocio.<br /><strong>Listo para tu día.</strong></p>
        </div>
        <div className="welcome__form-area">
          {notice && <Notice focus={noticeFocus}>{notice}</Notice>}
          {error && <Notice tone="error" focus>{error}</Notice>}
          {!view ? <Panel><div className="loading">{error ? <Icon name="alert" /> : <span className="spinner" aria-hidden="true" />}<h2>{error ? 'No pudimos conectar' : 'Preparando tu acceso…'}</h2>{error && <Button onClick={() => { setError(''); void refresh().catch(() => setError(cloudDemo ? 'La demo sigue sin responder. Esperá un minuto y volvé a intentar.' : 'La aplicación local sigue sin responder. Volvé a intentar.')) }}>Volver a intentar</Button>}</div></Panel> : <Panel><CredentialForm remoteDemo={cloudDemo} key={stage} kind={stage === 'setup' ? 'setup' : 'login'} title={stage === 'setup' ? 'Crear administrador' : 'Ingresar'} submit={async (value, token) => {
            setError('')
            if (stage === 'setup') {
              await identity.initialize(value, token)
              setNotice(cloudDemo ? 'Tu cuenta de prueba está lista. Ingresá con tus datos.' : 'Tu cuenta está lista. Eliminá el archivo del secreto e ingresá con tus datos.')
            } else { await identity.login(value); setNotice('') }
            await refresh()
          }} /></Panel>}
          <p className="recovery-note">{stage === 'setup' ? 'Esta configuración se realiza una sola vez por instalación.' : '¿No recordás tu contraseña? La recuperación todavía no está disponible. Conservá los datos de este equipo.'}</p>
        </div>
      </>}
    </main>
    <footer className="footer"><span>Gestión Inteligente POS</span><span>Hecho para trabajar cerca.</span></footer>
    {confirm && session && <ConfirmDeactivation username={confirm.username} busy={busy} onCancel={() => setConfirm(null)} onConfirm={() => void buttonAction(() => identity.deactivateEmployee(confirm.id, session.csrf_token), `El acceso de ${confirm.username} quedó desactivado.`)} />}
  </div>
}
