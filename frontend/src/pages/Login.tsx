import { useRef, useState } from 'react'
import { ArrowUpRight, Check } from 'lucide-react'
import { ensureKeycloakReachable, keycloak } from '../keycloak'
import Logo from '../components/Logo'

export default function Login() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(false)

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
      setError('Не удалось связаться с Keycloak. Проверьте, запущен ли он, и повторите попытку.')
      setBusy(false)
    }
  }

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
        <button className="primary-button login-button" disabled={busy} onClick={() => void signIn()}>
          {busy ? 'Переходим к входу…' : 'Войти как HR'} <ArrowUpRight size={20} aria-hidden="true" />
        </button>
        {error && <div className="form-error" role="alert">{error}</div>}
        <div className="login-note"><span className="note-icon"><Check size={15} aria-hidden="true" /></span><span>Учётные данные вводятся на странице Keycloak. Локальный запуск использует HTTP.</span></div>
      </div>
      <div className="login-action-bottom">Управление доступом — через Keycloak</div>
    </section>
  </main>
}
