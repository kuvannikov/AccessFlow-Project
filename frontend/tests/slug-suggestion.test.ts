import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createSlugSuggestion, slugInputPattern } from '../src/slugSuggestion.ts'

test('the browser slug pattern uses valid Unicode-sets syntax and rejects invalid addresses', () => {
  const pattern = new RegExp(`^(?:${slugInputPattern})$`, 'v')
  for (const value of ['anna.petrova', 'anna.petrova-2', 'a1-b2']) assert.equal(pattern.test(value), true)
  for (const value of ['anna_petrova', 'anna..petrova', 'anna-', '<script>', 'Анна']) assert.equal(pattern.test(value), false)
})

test('an old response cannot restore a slug after the name changes', async () => {
  let resolveOld!: (slug: string) => void
  const oldResponse = new Promise<string>(resolve => { resolveOld = resolve })
  const applied: string[] = []
  const failures: unknown[] = []
  const suggester = createSlugSuggestion(
    names => names.first_name === 'Вася' ? oldResponse : Promise.resolve('anna.ivanova'),
    (_, slug) => { applied.push(slug) },
    error => { failures.push(error) },
    () => {},
  )

  const first = suggester.suggest({ first_name: 'Вася', last_name: 'Иванов' })
  suggester.invalidate() // The user edits the first name while the first request is pending.
  await suggester.suggest({ first_name: 'Анна', last_name: 'Иванова' })
  resolveOld('vasya.ivanov')
  await first

  assert.deepEqual(applied, ['anna.ivanova'])
  assert.deepEqual(failures, [])
})

test('manual slug edits reject both an old suggestion and its old error', async () => {
  let rejectOld!: (error: Error) => void
  const oldResponse = new Promise<string>((_resolve, reject) => { rejectOld = reject })
  const applied: string[] = []
  const failures: unknown[] = []
  let settled = 0
  const suggester = createSlugSuggestion(() => oldResponse, (_, slug) => { applied.push(slug) },
    error => { failures.push(error) }, () => { settled += 1 })
  const pending = suggester.suggest({ first_name: 'Вася', last_name: 'Иванов' })
  suggester.invalidate()
  rejectOld(new Error('obsolete response'))
  await pending
  assert.deepEqual(applied, [])
  assert.deepEqual(failures, [])
  assert.equal(settled, 0)
})
