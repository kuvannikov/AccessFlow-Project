import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, CircleHelp, LogOut, Menu, Plus, Users, X } from 'lucide-react'
import { keycloak } from '../keycloak'
import { ApiError, request, type Employee } from '../api'
import Logo from '../components/Logo'
import { keepTabInside } from '../components/keepTabInside'
import EmployeeForm from '../features/employees/EmployeeForm'
import DeleteEmployeeDialog from '../features/employees/DeleteEmployeeDialog'
import EmployeeDirectory from '../features/employees/EmployeeDirectory'

export default function Dashboard() {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [errorStatus, setErrorStatus] = useState(0)
  const [open, setOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [name, setName] = useState('HR')
  const [employeeToDelete, setEmployeeToDelete] = useState<Employee | null>(null)
  const [notice, setNotice] = useState('')
  const directoryTitle = useRef<HTMLHeadingElement>(null)
  const menuTrigger = useRef<HTMLButtonElement>(null)
  const menuClose = useRef<HTMLButtonElement>(null)
  const menuPanel = useRef<HTMLElement>(null)
  const loadController = useRef<AbortController | null>(null)
  const focusDirectoryAfterDelete = useRef(false)
  function closeMenu() {
    setMenuOpen(false)
    requestAnimationFrame(() => menuTrigger.current?.focus())
  }

  useEffect(() => {
    if (!menuOpen) return
    menuClose.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const mobile = window.matchMedia('(max-width: 760px)')
    const onResize = () => {
      if (!mobile.matches) {
        setMenuOpen(false)
        requestAnimationFrame(() => menuPanel.current?.querySelector<HTMLAnchorElement>('a[href]')?.focus())
      }
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeMenu()
        return
      }
      keepTabInside(event, menuPanel.current, 'button:not(:disabled), a[href]')
    }
    window.addEventListener('keydown', onKey)
    mobile.addEventListener('change', onResize)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', onKey)
      mobile.removeEventListener('change', onResize)
    }
  }, [menuOpen])
  async function load() {
    loadController.current?.abort()
    const controller = new AbortController()
    loadController.current = controller
    setLoading(true)
    setError('')
    setErrorStatus(0)
    try {
      const [people, profile] = await Promise.all([
        request<Employee[]>('/employees', { signal: controller.signal }),
        request<{ name: string }>('/me', { signal: controller.signal }),
      ])
      if (loadController.current !== controller) return
      setEmployees(people)
      setName(profile.name)
    } catch (cause) {
      if (loadController.current !== controller) return
      controller.abort()
      setError(cause instanceof Error ? cause.message : 'Не удалось загрузить список')
      setErrorStatus(cause instanceof ApiError ? cause.status : 0)
    } finally {
      if (loadController.current === controller) setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    return () => {
      loadController.current?.abort()
      loadController.current = null
    }
  }, [])

  useEffect(() => {
    if (employeeToDelete !== null || !focusDirectoryAfterDelete.current) return
    focusDirectoryAfterDelete.current = false
    directoryTitle.current?.focus()
  }, [employeeToDelete])

  const departments = new Set(employees.map(employee => employee.department)).size

  function created(employee: Employee) {
    setEmployees(current => [employee, ...current])
    setOpen(false)
    setQuery('')
  }

  function deleted(id: number) {
    focusDirectoryAfterDelete.current = true
    setEmployees(current => current.filter(employee => employee.id !== id))
    setEmployeeToDelete(null)
    setNotice('Карточка сотрудника удалена.')
  }

  return <div className="app-shell">
    <aside id="mobile-navigation" ref={menuPanel} className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`} inert={open || employeeToDelete !== null} role={menuOpen ? 'dialog' : undefined} aria-modal={menuOpen || undefined} aria-label="Основная навигация">
      <div className="sidebar-top">
        <Logo light />
        <button ref={menuClose} className="mobile-close icon-button" aria-label="Закрыть меню" onClick={closeMenu}><X size={22} /></button>
      </div>
      <div className="sidebar-workspace"><span className="sidebar-line" /> РАБОЧЕЕ ПРОСТРАНСТВО</div>
      <nav aria-label="Основная навигация"><a className="nav-link active" href="/hr" aria-current="page"><Users size={19} /> Сотрудники <span>01</span></a></nav>
      <div className="sidebar-grow" />
      <div className="sidebar-stage">
        <span>ТЕКУЩИЙ ЭТАП</span>
        <strong>Основа команды</strong>
        <p>Добавляйте сотрудников и храните их данные в одном месте.</p>
        <div className="stage-line"><i /></div><small>01 / 04</small>
      </div>
      <div className="sidebar-user">
        <span className="user-avatar">HR</span>
        <span><strong>{name}</strong><small>Роль HR</small></span>
        <button className="logout-button" aria-label="Выйти" title="Выйти" onClick={() => void keycloak.logout({ redirectUri: `${window.location.origin}/login` })}><LogOut size={18} /></button>
      </div>
    </aside>
    <div className="main-area" inert={menuOpen || open || employeeToDelete !== null}>
      <header className="topbar">
        <button ref={menuTrigger} className="menu-button icon-button" aria-label="Открыть меню" aria-controls="mobile-navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}><Menu size={23} /></button>
        <span className="topbar-path">РАБОЧЕЕ ПРОСТРАНСТВО <span>/</span> СОТРУДНИКИ</span>
        <span className="mobile-page-title">Сотрудники</span>
        <span className="topbar-right"><span className="topbar-status" /> РОЛЬ HR</span>
      </header>
      <main className="dashboard-main">
        <section className="page-intro">
          <div><div className="eyebrow"><span className="eyebrow-line" /> КОМАНДА / ОБЗОР</div><h1>Сотрудники<span className="title-dot">.</span></h1><p>Люди, с которых начинается каждый процесс.</p></div>
          <button className="primary-button add-main" disabled={loading || Boolean(error)} onClick={() => setOpen(true)}><Plus size={20} /> Добавить сотрудника</button>
        </section>
        <section className="summary-strip" aria-label="Сводка">
          <div><span>ВСЕГО СОТРУДНИКОВ</span><strong>{loading || error ? '—' : employees.length.toString().padStart(2, '0')}</strong></div>
          <div><span>ПОДРАЗДЕЛЕНИЙ</span><strong>{loading || error ? '—' : departments.toString().padStart(2, '0')}</strong></div>
          <div className="summary-message"><span>ПЕРВЫЙ ЭТАП</span><p>Карточки сотрудников — основа будущих процессов адаптации. <ArrowUpRight size={17} aria-hidden="true" /></p></div>
        </section>
        <EmployeeDirectory
          employees={employees} query={query} onQueryChange={setQuery}
          loading={loading} error={error} errorStatus={errorStatus} notice={notice} onReload={load}
          onAdd={() => setOpen(true)} onDelete={setEmployeeToDelete} directoryTitle={directoryTitle}
        />
        <footer className="main-footer">
          <span>ACCESSFLOW / УПРАВЛЕНИЕ СОТРУДНИКАМИ</span>
          <span><CircleHelp size={16} /> Первый рабочий этап</span>
        </footer>
      </main>
    </div>
    {menuOpen && <button className="mobile-scrim" aria-label="Закрыть меню" onClick={closeMenu} />}
    {open && <EmployeeForm onClose={() => setOpen(false)} onCreated={created} />}
    {employeeToDelete && <DeleteEmployeeDialog employee={employeeToDelete} onClose={() => setEmployeeToDelete(null)} onDeleted={deleted} />}
  </div>
}
