import { keycloak } from './keycloak'
import { createApiRequest } from './apiRequest'
export { ApiError } from './apiRequest'

export type Employee = {
  id: number
  first_name: string
  last_name: string
  middle_name: string | null
  email: string
  position: string
  department: string
  start_date: string
  slug: string
  created_at: string
}

export type EmployeeInput = Omit<Employee, 'id' | 'created_at'>

export const request = createApiRequest(keycloak)
