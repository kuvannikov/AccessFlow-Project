import { useEffect, useRef, useState } from 'react'
import { ArrowRight, X } from 'lucide-react'
import { ApiError, request, type Employee, type EmployeeInput } from '../../api'
import { createSlugSuggestion, slugInputPattern } from '../../slugSuggestion'
import { keepTabInside } from '../../components/keepTabInside'
import SessionRecovery from '../../components/SessionRecovery'

type FormState = { first_name: string; last_name: string; middle_name: string; email: string; position: string; department: string; start_date: string; slug: string }
const blank: FormState = { first_name: '', last_name: '', middle_name: '', email: '', position: '', department: '', start_date: '', slug: '' }

export default function EmployeeForm({ onClose, onCreated }: { onClose: () => void; onCreated: (employee: Employee) => void }) {
  const [form, setForm] = useState<FormState>(blank)
  const [saving, setSaving] = useState(false)
  const [suggesting, setSuggesting] = useState(false)
  const [error, setError] = useState('')
  const [errorStatus, setErrorStatus] = useState(0)
  const savingRef = useRef(false)
  const firstRef = useRef<HTMLInputElement>(null)
  const dialogRef = useRef<HTMLElement>(null)
  const previousFocus = useRef<HTMLElement | null>(document.activeElement as HTMLElement | null)
  const slugSuggestion = useRef<ReturnType<typeof createSlugSuggestion> | null>(null)
  slugSuggestion.current ??= createSlugSuggestion(
    async names => (await request<{ slug: string }>('/employees/slug-suggestion', { method: 'POST', body: JSON.stringify(names) })).slug,
    (names, slug) => setForm(current => current.first_name === names.first_name && current.last_name === names.last_name ? { ...current, slug } : current),
    cause => {
      setError(cause instanceof Error ? cause.message : 'Не удалось подобрать slug')
      setErrorStatus(cause instanceof ApiError ? cause.status : 0)
    },
    () => setSuggesting(false),
  )
  function close() {
    if (!savingRef.current) onClose()
  }
  useEffect(() => {
    firstRef.current?.focus()
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      slugSuggestion.current?.invalidate()
      document.body.style.overflow = previous
      previousFocus.current?.focus()
    }
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !savingRef.current) onClose()
      keepTabInside(event, dialogRef.current, 'button:not(:disabled), input:not(:disabled)')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, saving])
  const update = (field: keyof FormState, value: string) => {
    if (field === 'first_name' || field === 'last_name' || field === 'slug') {
      slugSuggestion.current?.invalidate()
      setSuggesting(false)
    }
    setForm(current => ({ ...current, [field]: value, ...(field === 'first_name' || field === 'last_name' ? { slug: '' } : {}) }))
  }
  function generateSlug() {
    if (savingRef.current || suggesting) return
    setError('')
    setErrorStatus(0)
    setSuggesting(true)
    void slugSuggestion.current?.suggest({ first_name: form.first_name, last_name: form.last_name })
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (savingRef.current) return
    setError('')
    setErrorStatus(0)
    if (!form.slug) { setError('Сначала укажите slug для сотрудника.'); return }
    savingRef.current = true
    slugSuggestion.current?.invalidate()
    setSuggesting(false)
    setSaving(true)
    try {
      const payload: EmployeeInput = { ...form, middle_name: form.middle_name.trim() || null }
      const employee = await request<Employee>('/employees', { method: 'POST', body: JSON.stringify(payload) })
      onCreated(employee)
    } catch (cause) {
      setErrorStatus(cause instanceof ApiError ? cause.status : 0)
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
    finally { savingRef.current = false; setSaving(false) }
  }
  return <div className="drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) close() }}>
    <section ref={dialogRef} className="drawer" role="dialog" aria-modal="true" aria-labelledby="form-title" tabIndex={-1}>
      <div className="drawer-top"><span className="drawer-kicker">НОВАЯ КАРТОЧКА · 01</span><button className="icon-button" type="button" aria-label="Закрыть форму" disabled={saving} onClick={close}><X size={22} /></button></div>
      <div className="drawer-scroll">
        <h2 id="form-title">Добавить<br /><em>сотрудника</em></h2>
        <p className="drawer-intro">Заполните основные данные. Карточка появится в общем списке сразу после сохранения.</p>
        <form id="employee-form" onSubmit={submit}>
          <fieldset className="employee-fields" disabled={saving}>
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
          <div className="slug-row"><label>Slug <span aria-hidden="true">*</span><input required minLength={3} maxLength={180} pattern={slugInputPattern} value={form.slug} onChange={event => update('slug', event.target.value.toLowerCase())} placeholder="anna.petrova" /></label><button className="text-button" type="button" disabled={suggesting || !form.first_name.trim() || !form.last_name.trim()} onClick={() => void generateSlug()}>{suggesting ? 'Подбираем…' : 'Сгенерировать slug'} <ArrowRight size={16} /></button></div>
          <p className="field-help">Короткий уникальный адрес из латинских букв. Совпадения получат номер.</p>
          </fieldset>
          {error && <div className="form-error" role="alert">{error}</div>}
          <SessionRecovery status={errorStatus} />
        </form>
      </div>
      <div className="drawer-footer"><button type="button" className="secondary-button" disabled={saving} onClick={close}>Отмена</button><button className="primary-button" type="submit" form="employee-form" disabled={saving}>{saving ? 'Сохраняем…' : 'Сохранить сотрудника'} <ArrowRight size={19} /></button></div>
    </section>
  </div>
}
