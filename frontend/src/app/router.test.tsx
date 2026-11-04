import { createMemoryHistory, createRouter, RouterProvider } from '@tanstack/react-router'
import { expect, test } from 'vitest'
import { render } from 'vitest-browser-react'

import { routeTree } from './router'

function renderAt(path: string) {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
  })
  return render(<RouterProvider router={router} />)
}

test('renders the home page at the root path', async () => {
  const screen = await renderAt('/')

  await expect.element(screen.getByRole('heading', { level: 1 })).toHaveTextContent('AccessFlow')
})

test('renders the not found page for an unknown path', async () => {
  const screen = await renderAt('/no-such-page')

  await expect
    .element(screen.getByRole('heading', { level: 1 }))
    .toHaveTextContent('Такой страницы нет')
  await expect
    .element(screen.getByText('Адрес введён неверно или страница больше не существует.'))
    .toBeVisible()
})
