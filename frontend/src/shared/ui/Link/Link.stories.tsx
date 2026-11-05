import type { Meta, StoryObj } from '@storybook/react-vite'
import { RouterProvider } from 'react-aria-components'
import { expect, fn } from 'storybook/test'

import { ChevronLeftIcon } from '../icons/icons'
import { expectFocusRing } from '../storyChecks'
import { Link } from './Link'

// The router takes over navigation, so following a link does not unload the story.
const navigate = fn()

const meta = {
  title: 'Actions/Link',
  component: Link,
  args: { href: '/support' },
  decorators: [
    (Story) => (
      <RouterProvider navigate={navigate}>
        <Story />
      </RouterProvider>
    ),
  ],
  beforeEach: () => {
    navigate.mockClear()
  },
} satisfies Meta<typeof Link>

export default meta

type Story = StoryObj<typeof meta>

export const Inline: Story = {
  args: { children: 'напишите администратору' },
  render: (args) => (
    <p style={{ maxWidth: 'var(--size-text-max)' }}>
      Этой учётной записи не назначена роль HR. Если роль должна быть, <Link {...args} />.
    </p>
  ),
  play: async ({ canvas, userEvent }) => {
    const link = canvas.getByRole('link', { name: 'напишите администратору' })

    await userEvent.tab()
    await expectFocusRing(link)
    // Space scrolls the page; only Enter follows a link.
    await userEvent.keyboard(' ')
    await expect(navigate).not.toHaveBeenCalled()
    await userEvent.keyboard('{Enter}')
    await expect(navigate).toHaveBeenCalledTimes(1)
    await expect(navigate.mock.lastCall?.[0]).toBe('/support')

    await userEvent.hover(link)
    await expect(link).toHaveStyle({ textDecorationThickness: '2px' })
  },
}

export const Standalone: Story = {
  args: {
    variant: 'standalone',
    children: (
      <>
        <ChevronLeftIcon />К списку сотрудников
      </>
    ),
  },
  play: async ({ canvas, userEvent }) => {
    const link = canvas.getByRole('link', { name: 'К списку сотрудников' })

    await expect(link.getBoundingClientRect().height).toBeGreaterThanOrEqual(44)
    await userEvent.tab()
    await expectFocusRing(link)
  },
}
