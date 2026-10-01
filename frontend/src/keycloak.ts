import Keycloak from 'keycloak-js'
import { checkServiceReachable } from './reachability'

const keycloakUrl = import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8081/auth'
const realm = 'accessflow'

export const keycloak = new Keycloak({
  url: keycloakUrl,
  realm,
  clientId: 'accessflow-web',
})

export function ensureKeycloakReachable() {
  return checkServiceReachable(`${keycloakUrl.replace(/\/$/, '')}/realms/${realm}/.well-known/openid-configuration`)
}
