import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { createQueryClient } from './queryClient'

function httpError(status: number): Error {
  return Object.assign(new Error(`HTTP ${String(status)}`), { status })
}

async function countAttempts(error: Error): Promise<number> {
  const queryFn = vi.fn<() => Promise<never>>().mockRejectedValue(error)
  const query = createQueryClient()
    .query({ queryKey: ['resource'], queryFn })
    .catch(() => undefined)

  await vi.runAllTimersAsync()
  await query

  return queryFn.mock.calls.length
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

test('retries a network failure twice', async () => {
  expect(await countAttempts(new TypeError('Failed to fetch'))).toBe(3)
})

test('retries a server error twice', async () => {
  expect(await countAttempts(httpError(503))).toBe(3)
})

test.each([400, 401, 403, 404, 409, 422])('does not retry a %i response', async (status) => {
  expect(await countAttempts(httpError(status))).toBe(1)
})
