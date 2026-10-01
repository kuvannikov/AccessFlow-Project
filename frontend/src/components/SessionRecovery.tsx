import { useRef, useState } from 'react'
import { ensureKeycloakReachable, keycloak } from '../keycloak'

export default function SessionRecovery({ status }: { status: number }) {
  const pending = useRef(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (status !== 401) return null

  async function signIn() {
    if (pending.current) return
    pending.current = true
    setBusy(true)
    setError('')
    try {
      await ensureKeycloakReachable()
      await keycloak.login({ redirectUri: `${window.location.origin}/hr`, locale: 'ru' })
    } catch {
      pending.current = false
      setBusy(false)
      setError('Служба входа недоступна. Повторите попытку после восстановления Keycloak.')
    }
  }

  return <div className="session-recovery">
    <button type="button" className="secondary-button" disabled={busy} onClick={() => void signIn()}>{busy ? 'Переходим к входу…' : 'Войти снова'}</button>
    {error && <p role="alert">{error}</p>}
  </div>
}
