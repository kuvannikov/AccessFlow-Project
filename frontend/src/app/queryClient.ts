import { QueryClient } from '@tanstack/react-query'

const MAX_RETRIES = 2

// A 4xx answer is final: the same request gets the same answer again.
function isClientError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    typeof error.status === 'number' &&
    error.status >= 400 &&
    error.status < 500
  )
}

function shouldRetry(failureCount: number, error: unknown): boolean {
  return failureCount < MAX_RETRIES && !isClientError(error)
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetry },
    },
  })
}
