import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRight, ArrowUpRight, Check, CircleHelp, LogOut, Menu, Plus, Search, Trash2, Users, X } from 'lucide-react'
import { keycloak } from './main'
import { ApiError, request, type Employee, type EmployeeInput } from './api'
import { createSlugSuggestion } from './slugSuggestion'

type AuthState = 'loading' | 'guest' | 'hr' | 'forbidden' | 'error'
type FormState = { first_name: string; last_name: string; middle_name: string; email: string; position: string; department: string; start_date: string; slug: string }
const blank: FormState = { first_name: '', last_name: '', middle_name: '', email: '', position: '', department: '', start_date: '', slug: '' }

function Logo({ light = false }: { light?: boolean }) {
  return <div className={`brand ${light ? 'brand-light' : ''}`} aria-label="AccessFlow">
    <span className="brand-symbol" aria-hidden="true"><i /><i /><i /></span>
    <span>access<span className="brand-thin">flow</span></span>
  </div>
}

function Login() {
  const [busy, setBusy] = useState(false)
  return <main className="login-page">
    <section className="login-story">
      <Logo light />
      <div className="login-story-content">
        <div className="eyebrow light-eyebrow"><span className="eyebrow-line" /> РАБОЧЕЕ ПРОСТРАНСТВО HR</div>
        <h1>Люди в центре.<br /><em>Процессы</em> рядом.</h1>
        <p>Единое место для данных сотрудников и будущих процессов адаптации. Начните с первой карточки.</p>
      </div>
      <div className="login-story-bottom"><span>ACCESSFLOW / HR</span><span>01 — СОТРУДНИКИ</span></div>
    </section>
    <section className="login-action">
      <div className="login-action-inner">
        <div className="login-number">01 / ВХОД В СИСТЕМУ</div>
        <h2>Добро пожаловать<br />в AccessFlow</h2>
        <p>Войдите с рабочей учётной записью, чтобы открыть список сотрудников и добавить нового коллегу.</p>
        <button className="primary-button login-button" disabled={busy} onClick={() => { setBusy(true); void keycloak.login({ redirectUri: `${window.location.origin}/hr`, locale: 'ru' }) }}>
          {busy ? 'Переходим к входу…' : 'Войти как HR'} <ArrowUpRight size={20} aria-hidden="true" />
        </button>
        <div className="login-note"><span className="note-icon"><Check size={15} aria-hidden="true" /></span><span>Учётные данные вводятся на странице Keycloak. Локальный запуск использует HTTP.</span></div>
      </div>
      <div className="login-action-bottom">Управление доступом — через Keycloak</div>
    </section>
  </main>
}

function formatDate(date: string) {
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(`${date}T00:00:00`))
}

function initials(employee: Employee) { return `${employee.first_name[0]}${employee.last_name[0]}`.toUpperCase() }

function EmployeeForm({ onClose, onCreated }: { onClose: () => void; onCreated: (employee: Employee) => void }) {
  const [form, setForm] = useState<FormState>(blank)
  const [saving, setSaving] = useState(false)
  const [suggesting, setSuggesting] = useState(false)
  const [error, setError] = useState('')
  const firstRef = useRef<HTMLInputElement>(null)
  const dialogRef = useRef<HTMLElement>(null)
  const previousFocus = useRef<HTMLElement | null>(document.activeElement as HTMLElement | null)
  const slugSuggestion = useRef<ReturnType<typeof createSlugSuggestion> | null>(null)
  slugSuggestion.current ??= createSlugSuggestion(
    async names => (await request<{ slug: string }>('/employees/slug-suggestion', { method: 'POST', body: JSON.stringify(names) })).slug,
    (names, slug) => setForm(current => current.first_name === names.first_name && current.last_name === names.last_name ? { ...current, slug } : current),
    cause => setError(cause instanceof Error ? cause.message : 'Не удалось подобрать slug'),
    () => setSuggesting(false),
  )
  useEffect(() => { firstRef.current?.focus() }, [])
  useEffect(() => {
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key !== 'Tab' || !dialogRef.current) return
      const controls = Array.from(dialogRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)'))
      if (!controls.length) return
      if (event.shiftKey && document.activeElement === controls[0]) { event.preventDefault(); controls.at(-1)?.focus() }
      else if (!event.shiftKey && document.activeElement === controls.at(-1)) { event.preventDefault(); controls[0].focus() }
    }
    window.addEventListener('keydown', onKey)
    return () => { document.body.style.overflow = previous; window.removeEventListener('keydown', onKey); previousFocus.current?.focus() }
  }, [onClose])
  const update = (field: keyof FormState, value: string) => {
    if (field === 'first_name' || field === 'last_name' || field === 'slug') {
      slugSuggestion.current?.invalidate()
      setSuggesting(false)
    }
    setForm(current => ({ ...current, [field]: value, ...(field === 'first_name' || field === 'last_name' ? { slug: '' } : {}) }))
  }
  function generateSlug() {
    setError('')
    setSuggesting(true)
    void slugSuggestion.current?.suggest({ first_name: form.first_name, last_name: form.last_name })
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    if (!form.slug) { setError('Сначала укажите slug для сотрудника.'); return }
    setSaving(true)
    try {
      const payload: EmployeeInput = { ...form, middle_name: form.middle_name.trim() || null }
      const employee = await request<Employee>('/employees', { method: 'POST', body: JSON.stringify(payload) })
      onCreated(employee)
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === 'slug_conflict') {
        try {
          const result = await request<{ slug: string }>('/employees/slug-suggestion', { method: 'POST', body: JSON.stringify({ first_name: form.first_name, last_name: form.last_name }) })
          setForm(current => current.first_name === form.first_name && current.last_name === form.last_name && current.slug === form.slug ? { ...current, slug: result.slug } : current)
          setError(`Slug уже занят. Предложен «${result.slug}». Проверьте данные и сохраните ещё раз.`)
        } catch {
          setError('Slug уже занят. Данные сохранены в форме; подберите новый slug и повторите попытку.')
        }
      } else setError(cause instanceof Error ? cause.message : 'Не удалось сохранить сотрудника')
    }
    finally { setSaving(false) }
  }
  return <div className="drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
    <section ref={dialogRef} className="drawer" role="dialog" aria-modal="true" aria-labelledby="form-title">
      <div className="drawer-top"><span className="drawer-kicker">НОВАЯ КАРТОЧКА · 01</span><button className="icon-button" type="button" aria-label="Закрыть форму" onClick={onClose}><X size={22} /></button></div>
      <div className="drawer-scroll">
        <h2 id="form-title">Добавить<br /><em>сотрудника</em></h2>
        <p className="drawer-intro">Заполните основные данные. Карточка появится в общем списке сразу после сохранения.</p>
        <form id="employee-form" onSubmit={submit}>
          <div className="form-section"><span className="form-section-number">01</span><span>ЛИЧНЫЕ ДАННЫЕ</span></div>
          <div className="form-grid">
            <label>Имя <span aria-hidden="true">*</span><input ref={firstRef} required maxLength={80} autoComplete="given-name" value={form.first_name} onChange={event => update('first_name', event.target.value)} placeholder="Анна" /></label>
            <label>Фамилия <span aria-hidden="true">*</span><input required maxLength={80} autoComplete="family-name" value={form.last_name} onChange={event => update('last_name', event.target.value)} placeholder="Петрова" /></label>
            <label className="full-field">Отчество <small>необязательно</small><input maxLength={80} autoComplete="additional-name" value={form.middle_name} onChange={event => update('middle_name', event.target.value)} placeholder="Сергеевна" /></label>
            <label className="full-field">Рабочий email <span aria-hidden="true">*</span><input type="email" required maxLength={320} autoComplete="email" value={form.email} onChange={event => update('email', event.target.value)} placeholder="anna@company.ru" /></label>
          </div>
          <div className="form-section"><span className="form-section-number">02</span><span>РАБОТА И ВЫХОД</span></div>
          <div className="form-grid">
            <label>Должность <span aria-hidden="true">*</span><input required maxLength={120} value={form.position} onChange={event => update('position', event.target.value)} placeholder="Frontend-разработчик" /></label>
            <label>Подразделение <span aria-hidden="true">*</span><input required maxLength={120} value={form.department} onChange={event => update('department', event.target.value)} placeholder="Разработка" /></label>
            <label className="full-field">Дата выхода <span aria-hidden="true">*</span><input type="date" required value={form.start_date} onChange={event => update('start_date', event.target.value)} /></label>
          </div>
          <div className="form-section"><span className="form-section-number">03</span><span>АДРЕС КАРТОЧКИ</span></div>
          <div className="slug-row"><label>Slug <span aria-hidden="true">*</span><input required pattern="[a-z0-9]+([-.][a-z0-9]+)*" value={form.slug} onChange={event => update('slug', event.target.value.toLowerCase())} placeholder="anna.petrova" /></label><button className="text-button" type="button" disabled={suggesting || !form.first_name.trim() || !form.last_name.trim()} onClick={() => void generateSlug()}>{suggesting ? 'Подбираем…' : 'Сгенерировать slug'} <ArrowRight size={16} /></button></div>
          <p className="field-help">Короткий уникальный адрес из латинских букв. Совпадения получат номер.</p>
          {error && <div className="form-error" role="alert">{error}</div>}
        </form>
      </div>
      <div className="drawer-footer"><button type="button" className="secondary-button" onClick={onClose}>Отмена</button><button className="primary-button" type="submit" form="employee-form" disabled={saving}>{saving ? 'Сохраняем…' : 'Сохранить сотрудника'} <ArrowRight size={19} /></button></div>
    </section>
  </div>
}

function DeleteEmployeeDialog({ employee, onClose, onDeleted }: { employee: Employee; onClose: () => void; onDeleted: (id: number) => void }) {
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  const dialogRef = useRef<HTMLElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const previousFocus = useRef<HTMLElement | null>(document.activeElement as HTMLElement | null)

  useEffect(() => {
    cancelRef.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
      previousFocus.current?.focus()
    }
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleting) onClose()
      if (event.key !== 'Tab' || !dialogRef.current) return
      const controls = Array.from(dialogRef.current.querySelectorAll<HTMLElement>('button:not(:disabled)'))
      if (!controls.length) return
      if (event.shiftKey && document.activeElement === controls[0]) { event.preventDefault(); controls.at(-1)?.focus() }
      else if (!event.shiftKey && document.activeElement === controls.at(-1)) { event.preventDefault(); controls[0].focus() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [deleting, onClose])

  async function remove() {
    setDeleting(true)
    setError('')
    try {
      await request<void>(`/employees/${employee.id}`, { method: 'DELETE' })
      onDeleted(employee.id)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось удалить карточку. Повторите попытку.')
      setDeleting(false)
    }
  }

  const fullName = `${employee.last_name} ${employee.first_name} ${employee.middle_name || ''}`.trim()
  return <div className="delete-backdrop" onMouseDown={event => { if (!deleting && event.target === event.currentTarget) onClose() }}>
    <section ref={dialogRef} className="delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-title" aria-describedby="delete-description">
      <div className="delete-kicker">ПОДТВЕРЖДЕНИЕ</div>
      <h2 id="delete-title">Удалить карточку?</h2>
      <p id="delete-description">{fullName}<br /><span>{employee.email}</span></p>
      <p className="delete-warning">Карточка и данные сотрудника будут удалены из списка без возможности восстановления. Учётная запись Keycloak, если она существует, не изменится.</p>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="delete-actions"><button ref={cancelRef} className="secondary-button" type="button" disabled={deleting} onClick={onClose}>Отмена</button><button className="danger-button" type="button" disabled={deleting} onClick={() => void remove()}>{deleting ? 'Удаляем…' : 'Удалить карточку'}</button></div>
    </section>
  </div>
}

function Dashboard() {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [name, setName] = useState('HR')
  const [employeeToDelete, setEmployeeToDelete] = useState<Employee | null>(null)
  const [notice, setNotice] = useState('')
  const directoryTitle = useRef<HTMLHeadingElement>(null)
  const menuTrigger = useRef<HTMLButtonElement>(null)
  const menuClose = useRef<HTMLButtonElement>(null)
  const menuPanel = useRef<HTMLElement>(null)
  function closeMenu() { setMenuOpen(false); menuTrigger.current?.focus() }
  useEffect(() => {
    if (!menuOpen) return
    menuClose.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { closeMenu(); return }
      if (event.key !== 'Tab' || !menuPanel.current) return
      const controls = Array.from(menuPanel.current.querySelectorAll<HTMLElement>('button:not(:disabled), a[href]'))
      if (!controls.length) return
      if (event.shiftKey && document.activeElement === controls[0]) { event.preventDefault(); controls.at(-1)?.focus() }
      else if (!event.shiftKey && document.activeElement === controls.at(-1)) { event.preventDefault(); controls[0].focus() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])
  async function load() {
    setLoading(true)
    setError('')
    try {
      const [people, profile] = await Promise.all([request<Employee[]>('/employees'), request<{ name: string }>('/me')])
      setEmployees(people)
      setName(profile.name)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось загрузить список') }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])
  const shown = useMemo(() => employees.filter(employee => `${employee.first_name} ${employee.last_name} ${employee.middle_name || ''} ${employee.email} ${employee.position} ${employee.department}`.toLocaleLowerCase('ru').includes(query.trim().toLocaleLowerCase('ru'))), [employees, query])
  const departments = new Set(employees.map(employee => employee.department)).size
  function created(employee: Employee) { setEmployees(current => [employee, ...current]); setOpen(false); setQuery('') }
  function deleted(id: number) {
    setEmployees(current => current.filter(employee => employee.id !== id))
    setEmployeeToDelete(null)
    setNotice('Карточка сотрудника удалена.')
    requestAnimationFrame(() => directoryTitle.current?.focus())
  }
  return <div className="app-shell">
    <aside id="mobile-navigation" ref={menuPanel} className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
      <div className="sidebar-top"><Logo light /><button ref={menuClose} className="mobile-close icon-button" aria-label="Закрыть меню" onClick={closeMenu}><X size={22} /></button></div>
      <div className="sidebar-workspace"><span className="sidebar-line" /> РАБОЧЕЕ ПРОСТРАНСТВО</div>
      <nav aria-label="Основная навигация"><a className="nav-link active" href="/hr" aria-current="page"><Users size={19} /> Сотрудники <span>01</span></a></nav>
      <div className="sidebar-grow" />
      <div className="sidebar-stage"><span>ТЕКУЩИЙ ЭТАП</span><strong>Основа команды</strong><p>Добавляйте сотрудников и храните их данные в одном месте.</p><div className="stage-line"><i /></div><small>01 / 04</small></div>
      <div className="sidebar-user"><span className="user-avatar">HR</span><span><strong>{name}</strong><small>Роль HR</small></span><button className="logout-button" aria-label="Выйти" title="Выйти" onClick={() => void keycloak.logout({ redirectUri: `${window.location.origin}/login` })}><LogOut size={18} /></button></div>
    </aside>
    <div className="main-area">
      <header className="topbar"><button ref={menuTrigger} className="menu-button icon-button" aria-label="Открыть меню" aria-controls="mobile-navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}><Menu size={23} /></button><span className="topbar-path">РАБОЧЕЕ ПРОСТРАНСТВО <span>/</span> СОТРУДНИКИ</span><span className="mobile-page-title">Сотрудники</span><span className="topbar-right"><span className="topbar-status" /> РОЛЬ HR</span></header>
      <main className="dashboard-main">
        <section className="page-intro"><div><div className="eyebrow"><span className="eyebrow-line" /> КОМАНДА / ОБЗОР</div><h1>Сотрудники<span className="title-dot">.</span></h1><p>Люди, с которых начинается каждый процесс.</p></div><button className="primary-button add-main" onClick={() => setOpen(true)}><Plus size={20} /> Добавить сотрудника</button></section>
        <section className="summary-strip" aria-label="Сводка"><div><span>ВСЕГО СОТРУДНИКОВ</span><strong>{loading ? '—' : employees.length.toString().padStart(2, '0')}</strong></div><div><span>ПОДРАЗДЕЛЕНИЙ</span><strong>{loading ? '—' : departments.toString().padStart(2, '0')}</strong></div><div className="summary-message"><span>ПЕРВЫЙ ЭТАП</span><p>Карточки сотрудников — основа будущих процессов адаптации. <ArrowUpRight size={17} aria-hidden="true" /></p></div></section>
        <section className="directory" aria-labelledby="directory-title"><div className="directory-head"><div><span className="section-index">01 / СПИСОК</span><h2 ref={directoryTitle} tabIndex={-1} id="directory-title">Ваша команда</h2></div><span className="directory-count">{shown.length} {shown.length === 1 ? 'человек' : 'чел.'}</span></div>
          <div className="toolbar"><label className="search-box"><Search size={19} aria-hidden="true" /><span className="sr-only">Поиск сотрудников</span><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Поиск по имени, должности, отделу…" /></label><span className="toolbar-note">ДАННЫЕ ОБНОВЛЯЮТСЯ ПОСЛЕ СОХРАНЕНИЯ</span></div>
          {notice && <div className="directory-notice" role="status">{notice}</div>}
          {loading ? <div className="list-state" role="status"><span className="loading-line" />Загружаем сотрудников…</div> : error ? <div className="list-state error-state" role="alert"><strong>Не удалось открыть список</strong><p>{error}</p><button className="secondary-button" onClick={() => void load()}>Повторить</button></div> : employees.length === 0 ? <div className="list-state empty-state"><span className="empty-symbol"><Users size={32} /></span><h3>Команда начинается здесь</h3><p>Добавьте первого сотрудника — его карточка появится в этом списке.</p><button className="secondary-button" onClick={() => setOpen(true)}><Plus size={18} /> Добавить сотрудника</button></div> : shown.length === 0 ? <div className="list-state empty-state"><Search size={28} /><h3>Ничего не найдено</h3><p>Попробуйте другое имя, должность или подразделение.</p><button className="text-button" onClick={() => setQuery('')}>Сбросить поиск <ArrowRight size={16} /></button></div> : <div className="employee-list"><div className="list-header"><span>СОТРУДНИК</span><span>ДОЛЖНОСТЬ / ОТДЕЛ</span><span>ДАТА ВЫХОДА</span><span>SLUG</span><span>ДЕЙСТВИЕ</span></div>{shown.map(employee => <div className="employee-row" key={employee.id}><div className="employee-person"><span className="employee-avatar">{initials(employee)}</span><span><strong>{employee.last_name} {employee.first_name} {employee.middle_name || ''}</strong><small>{employee.email}</small></span></div><div className="employee-job"><strong>{employee.position}</strong><small>{employee.department}</small></div><div className="employee-date"><span className="mobile-label">Дата выхода</span>{formatDate(employee.start_date)}</div><div className="employee-slug">{employee.slug}</div><button className="employee-delete" type="button" aria-label={`Удалить карточку ${employee.last_name} ${employee.first_name}`} onClick={() => setEmployeeToDelete(employee)}><Trash2 size={16} aria-hidden="true" /><span>Удалить</span></button></div>)}</div>}
        </section>
        <footer className="main-footer"><span>ACCESSFLOW / УПРАВЛЕНИЕ СОТРУДНИКАМИ</span><span><CircleHelp size={16} /> Первый рабочий этап</span></footer>
      </main>
    </div>
    {menuOpen && <button className="mobile-scrim" aria-label="Закрыть меню" onClick={closeMenu} />}
    {open && <EmployeeForm onClose={() => setOpen(false)} onCreated={created} />}
    {employeeToDelete && <DeleteEmployeeDialog employee={employeeToDelete} onClose={() => setEmployeeToDelete(null)} onDeleted={deleted} />}
  </div>
}

export default function App() {
  const [auth, setAuth] = useState<AuthState>('loading')
  const path = window.location.pathname
  useEffect(() => {
    if (path !== '/login' && path !== '/hr') { window.location.replace('/login'); return }
    keycloak.init({ onLoad: 'check-sso', pkceMethod: 'S256', checkLoginIframe: false })
      .then(authenticated => {
        if (!authenticated) { setAuth('guest'); if (path === '/hr') window.location.replace('/login'); return }
        const roles = keycloak.realmAccess?.roles || []
        setAuth(roles.includes('HR') ? 'hr' : 'forbidden')
        if (path === '/login' && roles.includes('HR')) window.location.replace('/hr')
      })
      .catch(() => setAuth('error'))
  }, [path])
  if (auth === 'loading') return <div className="boot-screen" role="status"><Logo /><p>Проверяем доступ…</p></div>
  if (auth === 'error') return <div className="access-state"><Logo /><h1>Не удалось проверить вход</h1><p>Проверьте, запущен ли Keycloak, и обновите страницу.</p><button className="primary-button" onClick={() => window.location.reload()}>Повторить</button></div>
  if (auth === 'forbidden') return <div className="access-state"><Logo /><h1>Доступ только для HR</h1><p>Этой учётной записи не назначена роль HR.</p><button className="secondary-button" onClick={() => void keycloak.logout({ redirectUri: `${window.location.origin}/login` })}>Выйти</button></div>
  if (auth === 'guest' || path === '/login') return <Login />
  return <Dashboard />
}
