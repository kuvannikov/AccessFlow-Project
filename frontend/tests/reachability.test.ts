import assert from 'node:assert/strict'
import { test } from 'node:test'
import { checkServiceReachable } from '../src/reachability.ts'

test('Keycloak discovery rejects HTTP failures rather than accepting an opaque response', async () => {
  await assert.rejects(checkServiceReachable('https://keycloak.test/discovery', async (_url, options) => {
    assert.notEqual(options?.mode, 'no-cors')
    return new Response(null, { status: 503 })
  }), { message: 'Service is unavailable' })
  await checkServiceReachable('https://keycloak.test/discovery', async () => Response.json({}))
})

test('Keycloak discovery aborts a stalled connection', async () => {
  await assert.rejects(checkServiceReachable('https://keycloak.test/discovery', (_url, options) =>
    new Promise((_resolve, reject) => {
      options?.signal?.addEventListener('abort', () => reject(options.signal?.reason), { once: true })
    }), 20), { name: 'AbortError' })
})
