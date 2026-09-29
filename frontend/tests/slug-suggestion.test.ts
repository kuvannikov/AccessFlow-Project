import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createSlugSuggestion } from '../src/slugSuggestion.ts'

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
