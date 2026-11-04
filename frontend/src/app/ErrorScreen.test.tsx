import {
  createMemoryHistory,
  createRootRoute,
  createRouter,
  RouterProvider,
} from '@tanstack/react-router'
import { expect, test } from 'vitest'
import { render } from 'vitest-browser-react'

import { ErrorScreen } from './ErrorScreen'

function renderFailingRoute(error: Error) {
  const rootRoute = createRootRoute({
    component: () => {
      throw error
    },
    errorComponent: ErrorScreen,
  })
  const router = createRouter({
    routeTree: rootRoute,
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })
  return render(<RouterProvider router={router} />)
}

test('replaces a failed route with the error screen', async () => {
  const screen = await renderFailingRoute(new Error('Render failed'))

  await expect
    .element(screen.getByRole('heading', { level: 1 }))
    .toHaveTextContent('Что-то сломалось на нашей стороне')
  await expect.element(screen.getByRole('button', { name: 'Обновить страницу' })).toBeVisible()
  await expect.element(screen.getByText(/Код запроса:/)).not.toBeInTheDocument()
})

test('shows the request ID carried by the error', async () => {
  const error = Object.assign(new Error('Server error'), { requestId: 'c0ffee00-request' })
  const screen = await renderFailingRoute(error)

  await expect.element(screen.getByText('Код запроса: c0ffee00-request')).toBeVisible()
})
