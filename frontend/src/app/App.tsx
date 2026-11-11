import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { I18nProvider } from 'react-aria-components'

import { createQueryClient } from './queryClient'
import { router } from './router'

const queryClient = createQueryClient()

export function App() {
  return (
    // React Aria takes its locale from the browser language, not from the page.
    <I18nProvider locale="ru-RU">
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </I18nProvider>
  )
}
