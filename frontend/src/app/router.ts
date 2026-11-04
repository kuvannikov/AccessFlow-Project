import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'

import { HomePage } from '../pages/HomePage'
import { NotFoundPage } from '../pages/NotFoundPage'

const rootRoute = createRootRoute({
  notFoundComponent: NotFoundPage,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: HomePage,
})

export const routeTree = rootRoute.addChildren([indexRoute])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
