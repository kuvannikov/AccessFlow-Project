import { keycloak } from './main'

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

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message)
  }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  try {
    await keycloak.updateToken(30)
  } catch {
    throw new ApiError(401, 'Сессия истекла. Войдите снова.')
  }
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${keycloak.token}`,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  })
  if (!response.ok) {
    let message = 'Не удалось выполнить запрос. Повторите попытку.'
    let code: string | undefined
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (body.detail && typeof body.detail === 'object' && !Array.isArray(body.detail)) {
        if (typeof body.detail.message === 'string') message = body.detail.message
        if (typeof body.detail.code === 'string') code = body.detail.code
      }
      else if (Array.isArray(body.detail) && body.detail.length) {
        const field = body.detail[0]?.loc?.at(-1)
        const labels: Record<string, string> = {
          first_name: 'Имя', last_name: 'Фамилия', middle_name: 'Отчество',
          email: 'Рабочий email', position: 'Должность', department: 'Подразделение',
          start_date: 'Дата выхода', slug: 'Slug',
        }
        message = field && labels[field] ? `Проверьте поле «${labels[field]}».` : 'Проверьте введённые данные.'
        if ((field === 'first_name' || field === 'last_name') &&
            body.detail[0]?.msg?.includes('буквы, для которых нельзя создать slug')) {
          message = 'Для имени и фамилии используйте латиницу либо русские, украинские и белорусские буквы.'
        }
      }
      if (response.status === 500 && typeof body.request_id === 'string') {
        message = `Внутренняя ошибка сервера. Код запроса: ${body.request_id}`
      }
    } catch { /* Response may not contain JSON. */ }
    throw new ApiError(response.status, message, code)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
