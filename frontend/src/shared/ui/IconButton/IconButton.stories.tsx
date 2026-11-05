import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, fn } from 'storybook/test'

import { LogOutIcon, MenuIcon, XIcon } from '../icons/icons'
import { expectFocusRing } from '../storyChecks'
import { IconButton } from './IconButton'

const meta = {
  title: 'Actions/IconButton',
  component: IconButton,
  args: { 'aria-label': 'Очистить поиск', children: <XIcon />, onPress: fn() },
} satisfies Meta<typeof IconButton>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  play: async ({ args, canvas, userEvent }) => {
    const button = canvas.getByRole('button', { name: 'Очистить поиск' })

    await userEvent.tab()
    await expectFocusRing(button)
    await userEvent.keyboard('{Enter}')
    await expect(args.onPress).toHaveBeenCalledTimes(1)
    await userEvent.keyboard(' ')
    await expect(args.onPress).toHaveBeenCalledTimes(2)
  },
}

export const Disabled: Story = {
  args: { isDisabled: true },
}

export const Inverse: Story = {
  args: { 'aria-label': 'Выйти', children: <LogOutIcon />, isInverse: true },
  decorators: [
    (Story) => (
      <div
        style={{
          display: 'inline-flex',
          padding: 'var(--space-4)',
          background: 'var(--bg-inverse)',
        }}
      >
        <Story />
      </div>
    ),
  ],
  play: async ({ canvas, userEvent }) => {
    await userEvent.tab()
    await expectFocusRing(canvas.getByRole('button', { name: 'Выйти' }), '--focus-ring-inverse')
  },
}

export const OpensPanel: Story = {
  args: { 'aria-label': 'Открыть меню', children: <MenuIcon /> },
  render: function Render({ onPress, ...args }) {
    const [isOpen, setIsOpen] = useState(false)

    return (
      <>
        <IconButton
          {...args}
          aria-expanded={isOpen}
          aria-controls="navigation"
          onPress={(event) => {
            onPress?.(event)
            setIsOpen(!isOpen)
          }}
        />
        <nav id="navigation" aria-label="Разделы" hidden={!isOpen}>
          Сотрудники
        </nav>
      </>
    )
  },
  play: async ({ canvas, userEvent }) => {
    const button = canvas.getByRole('button', { name: 'Открыть меню' })

    await expect(button).toHaveAttribute('aria-expanded', 'false')
    await userEvent.tab()
    await userEvent.keyboard('{Enter}')
    await expect(button).toHaveAttribute('aria-expanded', 'true')
    await expect(canvas.getByRole('navigation', { name: 'Разделы' })).toBeVisible()
  },
}
