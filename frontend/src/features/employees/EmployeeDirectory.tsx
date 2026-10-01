import { useMemo, type RefObject } from 'react'
import { ArrowRight, Plus, Search, Trash2, Users } from 'lucide-react'
import type { Employee } from '../../api'
import { displayEmployeeName, matchesEmployeeQuery } from './employeeSearch'
import SessionRecovery from '../../components/SessionRecovery'

type Props = {
  employees: Employee[]
  query: string
  onQueryChange: (query: string) => void
  loading: boolean
  error: string
  errorStatus: number
  notice: string
  onReload: () => void
  onAdd: () => void
  onDelete: (employee: Employee) => void
  directoryTitle: RefObject<HTMLHeadingElement | null>
}

const dateFormatter = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })

function formatDate(date: string) {
  return dateFormatter.format(new Date(`${date}T00:00:00`))
}

function initials(employee: Employee) {
  return `${employee.first_name[0]}${employee.last_name[0]}`.toUpperCase()
}

function EmployeeRow({ employee, onDelete }: { employee: Employee; onDelete: (employee: Employee) => void }) {
  return <div className="employee-row" role="listitem">
    <div className="employee-person">
      <span className="employee-avatar">{initials(employee)}</span>
      <span><strong>{displayEmployeeName(employee)}</strong><small>{employee.email}</small></span>
    </div>
    <div className="employee-job"><strong>{employee.position}</strong><small>{employee.department}</small></div>
    <div className="employee-date"><span className="mobile-label">Дата выхода</span>{formatDate(employee.start_date)}</div>
    <div className="employee-slug">{employee.slug}</div>
    <button className="employee-delete" type="button" aria-label={`Удалить карточку ${employee.last_name} ${employee.first_name}`} onClick={() => onDelete(employee)}>
      <Trash2 size={16} aria-hidden="true" /><span>Удалить</span>
    </button>
  </div>
}

export default function EmployeeDirectory({ employees, query, onQueryChange, loading, error, errorStatus, notice, onReload, onAdd, onDelete, directoryTitle }: Props) {
  const shown = useMemo(() => {
    return employees.filter(employee => matchesEmployeeQuery(employee, query))
  }, [employees, query])

  let content: React.ReactNode
  if (loading) {
    content = <div className="list-state" role="status"><span className="loading-line" />Загружаем сотрудников…</div>
  } else if (error) {
    content = <div className="list-state error-state" role="alert">
      <strong>Не удалось открыть список</strong><p>{error}</p>
      <SessionRecovery status={errorStatus} />
      <button className="secondary-button" onClick={onReload}>Повторить</button>
    </div>
  } else if (employees.length === 0) {
    content = <div className="list-state">
      <span className="empty-symbol"><Users size={32} /></span>
      <h3>Команда начинается здесь</h3>
      <p>Добавьте первого сотрудника — его карточка появится в этом списке.</p>
      <button className="secondary-button" onClick={onAdd}><Plus size={18} /> Добавить сотрудника</button>
    </div>
  } else if (shown.length === 0) {
    content = <div className="list-state">
      <Search size={28} /><h3>Ничего не найдено</h3>
      <p>Попробуйте другое имя, должность или подразделение.</p>
      <button className="text-button" onClick={() => onQueryChange('')}>Сбросить поиск <ArrowRight size={16} /></button>
    </div>
  } else {
    content = <div className="employee-list" role="list" aria-label="Сотрудники">
      <div className="list-header" aria-hidden="true"><span>СОТРУДНИК</span><span>ДОЛЖНОСТЬ / ОТДЕЛ</span><span>ДАТА ВЫХОДА</span><span>SLUG</span><span>ДЕЙСТВИЕ</span></div>
      {shown.map(employee => <EmployeeRow key={employee.id} employee={employee} onDelete={onDelete} />)}
    </div>
  }

  return <section className="directory" aria-labelledby="directory-title">
    <div className="directory-head">
      <div><span className="section-index">01 / СПИСОК</span><h2 ref={directoryTitle} tabIndex={-1} id="directory-title">Ваша команда</h2></div>
      <span className="directory-count">{loading || error ? '—' : `${shown.length} ${shown.length === 1 ? 'человек' : 'чел.'}`}</span>
    </div>
    <div className="toolbar">
      <label className="search-box"><Search size={19} aria-hidden="true" /><span className="sr-only">Поиск сотрудников</span><input type="search" value={query} onChange={event => onQueryChange(event.target.value)} placeholder="Поиск по имени, должности, отделу…" /></label>
      <span className="toolbar-note">ДАННЫЕ ОБНОВЛЯЮТСЯ ПОСЛЕ СОХРАНЕНИЯ</span>
    </div>
    {notice && <div className="directory-notice" role="status">{notice}</div>}
    {content}
  </section>
}
