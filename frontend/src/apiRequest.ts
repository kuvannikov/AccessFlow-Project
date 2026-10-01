type Session = {
  token?: string
  authenticated?: boolean
  updateToken: (minValidity: number) => Promise<boolean>
}

export class ApiError extends Error {
  status: number
  code?: string

  constructor(status: number, message: string, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export function createApiRequest(session: Session, fetcher: typeof fetch = fetch, timeoutMs = 15000) {
  return async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    if (options.signal?.aborted) throw options.signal.reason
    const controller = new AbortController()
    const abort = () => controller.abort(options.signal?.reason)
    options.signal?.addEventListener('abort', abort, { once: true })
    const timeoutId = setTimeout(() => controller.abort(new ApiError(0,
      'Сервер не ответил вовремя. Проверьте результат перед повторной попыткой.')), timeoutMs)
    const interrupted = new Promise<never>((_, reject) => {
      if (controller.signal.aborted) reject(controller.signal.reason)
      else controller.signal.addEventListener('abort', () => reject(controller.signal.reason), { once: true })
    })

    try {
      try {
        await Promise.race([session.updateToken(30), interrupted])
      } catch {
        if (controller.signal.aborted) throw controller.signal.reason
        if (!session.authenticated) throw new ApiError(401, 'Сессия истекла. Войдите снова.')
        throw new ApiError(503, 'Служба входа недоступна. Повторите попытку после восстановления Keycloak.')
      }
      if (controller.signal.aborted) throw controller.signal.reason
      if (!session.token || !session.authenticated) {
        throw new ApiError(401, 'Сессия истекла. Войдите снова.')
      }
      const headers = new Headers(options.headers)
      headers.set('Authorization', `Bearer ${session.token}`)
      if (options.body) headers.set('Content-Type', 'application/json')
      const response = await Promise.race([fetcher(`/api${path}`, {
        ...options, headers, signal: controller.signal,
      }), interrupted])
      if (!response.ok) {
        let message = 'Не удалось выполнить запрос. Повторите попытку.'
        let code: string | undefined
        try {
          const body = await Promise.race([response.json(), interrupted])
          if (typeof body.detail === 'string') message = body.detail
          else if (body.detail && typeof body.detail === 'object' && !Array.isArray(body.detail)) {
            if (typeof body.detail.message === 'string') message = body.detail.message
            if (typeof body.detail.code === 'string') code = body.detail.code
          } else if (Array.isArray(body.detail) && body.detail.length) {
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
        } catch {
          if (controller.signal.aborted) throw controller.signal.reason
          // An error response may not contain JSON.
        }
        if (response.status === 401) message = 'Сессия истекла. Войдите снова.'
        throw new ApiError(response.status, message, code)
      }
      if (response.status === 204) return undefined as T
      return await Promise.race([response.json() as Promise<T>, interrupted])
    } catch (cause) {
      if (cause instanceof ApiError || controller.signal.aborted) throw cause
      throw new ApiError(0, 'Не удалось связаться с сервером. Проверьте соединение и повторите попытку.')
    } finally {
      clearTimeout(timeoutId)
      options.signal?.removeEventListener('abort', abort)
    }
  }
}
