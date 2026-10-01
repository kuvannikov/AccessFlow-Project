import { useEffect, useState } from 'react'
import { ensureKeycloakReachable, keycloak } from './keycloak'
import Logo from './components/Logo'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'

type AuthState = 'loading' | 'guest' | 'hr' | 'forbidden' | 'error'

export default function App() {
  const [auth, setAuth] = useState<AuthState>('loading')
  const path = window.location.pathname
  useEffect(() => {
    if (path !== '/login' && path !== '/hr') { window.location.replace('/login'); return }
    let active = true
    let timeoutId: number
    const initialization = (async () => {
      await ensureKeycloakReachable()
      return keycloak.init({
        onLoad: 'check-sso',
        pkceMethod: 'S256',
        checkLoginIframe: false,
        silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
        silentCheckSsoFallback: false,
      })
    })()
    const timeout = new Promise<never>((_, reject) => {
      timeoutId = window.setTimeout(() => reject(new Error('Keycloak check timed out')), 15000)
    })

    Promise.race([initialization, timeout])
      .then(authenticated => {
        if (!active) return
        if (!authenticated) { setAuth('guest'); if (path === '/hr') window.location.replace('/login'); return }
        const roles = keycloak.realmAccess?.roles || []
        setAuth(roles.includes('HR') ? 'hr' : 'forbidden')
        if (path === '/login' && roles.includes('HR')) window.location.replace('/hr')
      })
      .catch(() => { if (active) setAuth('error') })
      .finally(() => window.clearTimeout(timeoutId))

    return () => {
      active = false
      window.clearTimeout(timeoutId)
    }
  }, [path])
  if (auth === 'loading') return <div className="boot-screen" role="status"><Logo /><p>Проверяем доступ…</p></div>
  if (auth === 'error') return <div className="access-state"><Logo /><h1>Не удалось проверить вход</h1><p>Проверьте, запущен ли Keycloak, и обновите страницу.</p><button className="primary-button" onClick={() => window.location.reload()}>Повторить</button></div>
  if (auth === 'forbidden') return <div className="access-state"><Logo /><h1>Доступ только для HR</h1><p>Этой учётной записи не назначена роль HR.</p><button className="secondary-button" onClick={() => void keycloak.logout({ redirectUri: `${window.location.origin}/login` })}>Выйти</button></div>
  if (auth === 'guest' || path === '/login') return <Login />
  return <Dashboard />
}
