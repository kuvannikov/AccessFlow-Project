import ReactDOM from 'react-dom/client'
import Keycloak from 'keycloak-js'
import App from './App'
import './styles.css'

export const keycloak = new Keycloak({
  url: 'http://localhost:8081/auth',
  realm: 'accessflow',
  clientId: 'accessflow-web',
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <App />,
)
