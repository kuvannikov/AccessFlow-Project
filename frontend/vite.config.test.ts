import { createServer, type ViteDevServer } from 'vite'
import { afterAll, beforeAll, expect, test } from 'vitest'

let server: ViteDevServer | undefined

beforeAll(async () => {
  server = await createServer({
    root: import.meta.dirname,
    server: { middlewareMode: true },
    logLevel: 'silent',
  })
})

afterAll(async () => {
  await server?.close()
})

test('components are compiled by React Compiler', async () => {
  const result = await server?.transformRequest('/src/app/App.tsx')

  expect(result?.code).toContain('react.memo_cache_sentinel')
})
