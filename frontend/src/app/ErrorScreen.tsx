import type { ErrorComponentProps } from '@tanstack/react-router'

function requestIdOf(error: unknown): string | undefined {
  if (
    typeof error === 'object' &&
    error !== null &&
    'requestId' in error &&
    typeof error.requestId === 'string'
  ) {
    return error.requestId
  }
  return undefined
}

export function ErrorScreen({ error }: ErrorComponentProps) {
  const requestId = requestIdOf(error)

  return (
    <main>
      <h1>Что-то сломалось на нашей стороне</h1>
      <p>
        Страница не открылась из-за ошибки приложения. Обновите страницу. Если ошибка повторится,
        передайте администратору код запроса.
      </p>
      {requestId !== undefined && <p>Код запроса: {requestId}</p>}
      <button
        type="button"
        onClick={() => {
          window.location.reload()
        }}
      >
        Обновить страницу
      </button>
    </main>
  )
}
