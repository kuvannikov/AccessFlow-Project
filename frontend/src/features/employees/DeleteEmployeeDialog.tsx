import { useEffect, useRef, useState } from 'react'
import { ApiError, request, type Employee } from '../../api'
import { keepTabInside } from '../../components/keepTabInside'
import SessionRecovery from '../../components/SessionRecovery'

export default function DeleteEmployeeDialog({ employee, onClose, onDeleted }: { employee: Employee; onClose: () => void; onDeleted: (id: number) => void }) {
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  const [errorStatus, setErrorStatus] = useState(0)
  const deletingRef = useRef(false)
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
      if (event.key === 'Escape' && !deletingRef.current) onClose()
      keepTabInside(event, dialogRef.current, 'button:not(:disabled)')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [deleting, onClose])

  async function remove() {
    if (deletingRef.current) return
    deletingRef.current = true
    setDeleting(true)
    setError('')
    setErrorStatus(0)
    try {
      await request<void>(`/employees/${employee.id}`, { method: 'DELETE' })
      onDeleted(employee.id)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось удалить карточку. Повторите попытку.')
      setErrorStatus(cause instanceof ApiError ? cause.status : 0)
      deletingRef.current = false
      setDeleting(false)
    }
  }

  const fullName = `${employee.last_name} ${employee.first_name} ${employee.middle_name || ''}`.trim()
  return <div className="delete-backdrop" onMouseDown={event => { if (!deletingRef.current && event.target === event.currentTarget) onClose() }}>
    <section ref={dialogRef} className="delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-title" aria-describedby="delete-description" tabIndex={-1}>
      <div className="delete-kicker">ПОДТВЕРЖДЕНИЕ</div>
      <h2 id="delete-title">Удалить карточку?</h2>
      <p id="delete-description">{fullName}<br /><span>{employee.email}</span></p>
      <p className="delete-warning">Карточка и данные сотрудника будут удалены из списка без возможности восстановления. Учётная запись Keycloak, если она существует, не изменится.</p>
      {error && <div className="form-error" role="alert">{error}</div>}
      <SessionRecovery status={errorStatus} />
      <div className="delete-actions"><button ref={cancelRef} className="secondary-button" type="button" disabled={deleting} onClick={onClose}>Отмена</button><button className="danger-button" type="button" disabled={deleting} onClick={() => void remove()}>{deleting ? 'Удаляем…' : 'Удалить карточку'}</button></div>
    </section>
  </div>
}
