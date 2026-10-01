import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ApiError, createApiRequest } from '../src/apiRequest.ts'

function session() {
  return { token: 'test-token', authenticated: true, updateToken: async (_minValidity: number) => false }
}

test('API refreshes the session and preserves Headers supplied by the caller', async () => {
  const auth = session()
  let minimum = 0
  auth.updateToken = async value => { minimum = value; return false }
  const request = createApiRequest(auth, async (url, options) => {
    assert.equal(url, '/api/employees')
    const headers = new Headers(options?.headers)
    assert.equal(headers.get('Authorization'), 'Bearer test-token')
    assert.equal(headers.get('X-Request-ID'), 'test-request')
    assert.equal(headers.get('Content-Type'), 'application/json')
    return Response.json({ id: 1 }, { status: 201 })
  })
  assert.deepEqual(await request('/employees', {
    method: 'POST', body: '{}', headers: new Headers({ 'X-Request-ID': 'test-request' }),
  }), { id: 1 })
  assert.equal(minimum, 30)
})

for (const code of ['email_conflict', 'slug_conflict']) {
  test(`HTTP 409 preserves the ${code} contract for form recovery`, async () => {
    const request = createApiRequest(session(), async () => Response.json({
      detail: { code, message: 'Конфликт' },
    }, { status: 409 }))
    await assert.rejects(request('/employees', { method: 'POST', body: '{}' }),
      (cause: unknown) => cause instanceof ApiError && cause.status === 409 &&
        cause.code === code && cause.message === 'Конфликт')
  })
}

test('validation errors show a field label without echoing submitted data', async () => {
  const request = createApiRequest(session(), async () => Response.json({
    detail: [{ loc: ['body', 'email'], input: 'private@example.org', msg: 'invalid email' }],
  }, { status: 422 }))
  await assert.rejects(request('/employees'), { status: 422, message: 'Проверьте поле «Рабочий email».' })
})

test('missing session and HTTP 401 offer an explicit login recovery message', async () => {
  let requests = 0
  const auth = { ...session(), authenticated: false }
  const request = createApiRequest(auth, async () => {
    requests += 1
    return Response.json({ detail: 'Недействительный токен' }, { status: 401 })
  })
  await assert.rejects(request('/employees'), { status: 401, message: 'Сессия истекла. Войдите снова.' })
  assert.equal(requests, 0)
  auth.authenticated = true
  await assert.rejects(request('/employees'), { status: 401, message: 'Сессия истекла. Войдите снова.' })
  assert.equal(requests, 1)
})

test('a transient Keycloak refresh failure is recoverable without claiming session expiry', async () => {
  let offline = true
  let requests = 0
  const auth = session()
  auth.updateToken = async () => {
    if (offline) throw new TypeError('Failed to fetch')
    return false
  }
  const request = createApiRequest(auth, async () => { requests += 1; return Response.json([]) })
  await assert.rejects(request('/employees'), { status: 503 })
  assert.equal(requests, 0)
  offline = false
  assert.deepEqual(await request('/employees'), [])
  assert.equal(requests, 1)
})

test('an expired refresh session returns 401 without sending an unauthenticated API request', async () => {
  const auth = session()
  auth.updateToken = async () => {
    auth.authenticated = false
    auth.token = ''
    throw new Error('refresh rejected')
  }
  let requests = 0
  const request = createApiRequest(auth, async () => { requests += 1; return Response.json([]) })
  await assert.rejects(request('/employees'), { status: 401, message: 'Сессия истекла. Войдите снова.' })
  assert.equal(requests, 0)
})

test('a stalled refresh has a deadline and its late completion never sends an API request', async () => {
  let complete!: (value: boolean) => void
  const auth = session()
  auth.updateToken = () => new Promise(resolve => { complete = resolve })
  let requests = 0
  const request = createApiRequest(auth, async () => { requests += 1; return Response.json([]) }, 20)
  await assert.rejects(request('/employees'), { status: 0 })
  complete(false)
  await Promise.resolve()
  assert.equal(requests, 0)
})

test('a stalled API request is aborted without an automatic mutation retry', async () => {
  let requests = 0
  let signal: AbortSignal | undefined
  const request = createApiRequest(session(), (_url, options) => {
    requests += 1
    signal = options?.signal as AbortSignal
    return new Promise<Response>(() => {})
  }, 20)
  await assert.rejects(request('/employees', { method: 'POST', body: '{}' }), { status: 0 })
  assert.equal(signal?.aborted, true)
  assert.equal(requests, 1)
})

test('the deadline also covers a response body which never completes', async () => {
  const response = { ok: true, status: 200, json: () => new Promise(() => {}) } as Response
  const request = createApiRequest(session(), async () => response, 20)
  await assert.rejects(request('/employees'), { status: 0 })
})

test('caller cancellation prevents a pending refresh from fetching stale data', async () => {
  let complete!: (value: boolean) => void
  const auth = session()
  auth.updateToken = () => new Promise(resolve => { complete = resolve })
  let requests = 0
  const request = createApiRequest(auth, async () => { requests += 1; return Response.json([]) })
  const controller = new AbortController()
  const pending = request('/employees', { signal: controller.signal })
  controller.abort()
  await assert.rejects(pending, { name: 'AbortError' })
  complete(false)
  await Promise.resolve()
  assert.equal(requests, 0)
})

test('an already cancelled request starts neither token refresh nor fetch', async () => {
  const auth = session()
  let refreshes = 0
  let requests = 0
  auth.updateToken = async () => { refreshes += 1; return false }
  const request = createApiRequest(auth, async () => { requests += 1; return Response.json([]) })
  const controller = new AbortController()
  controller.abort()
  await assert.rejects(request('/employees', { signal: controller.signal }), { name: 'AbortError' })
  assert.equal(refreshes, 0)
  assert.equal(requests, 0)
})

test('non-JSON and network errors produce safe, recoverable messages', async () => {
  const unavailable = createApiRequest(session(), async () => new Response('internal proxy error', { status: 503 }))
  await assert.rejects(unavailable('/employees'), { status: 503, message: 'Не удалось выполнить запрос. Повторите попытку.' })
  const disconnected = createApiRequest(session(), async () => { throw new TypeError('network internals') })
  await assert.rejects(disconnected('/employees'), { status: 0, message: 'Не удалось связаться с сервером. Проверьте соединение и повторите попытку.' })
})

test('successful deletion accepts HTTP 204 without parsing JSON', async () => {
  const request = createApiRequest(session(), async () => new Response(null, { status: 204 }))
  assert.equal(await request('/employees/1', { method: 'DELETE' }), undefined)
})
