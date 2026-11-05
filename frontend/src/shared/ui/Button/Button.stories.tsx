import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, fn, waitFor } from 'storybook/test'

import { ChevronLeftIcon, PlusIcon, RotateCwIcon } from '../icons/icons'
import { expectFocusRing, tokenColor } from '../storyChecks'
import { Button } from './Button'

const meta = {
  title: 'Actions/Button',
  component: Button,
  args: { onPress: fn() },
} satisfies Meta<typeof Button>

export default meta

type Story = StoryObj<typeof meta>

export const Primary: Story = {
  args: { variant: 'primary', children: 'Сохранить сотрудника' },
  play: async ({ args, canvas, userEvent }) => {
    const button = canvas.getByRole('button', { name: 'Сохранить сотрудника' })

    await userEvent.tab()
    await expectFocusRing(button)
    await userEvent.keyboard('{Enter}')
    await expect(args.onPress).toHaveBeenCalledTimes(1)
    await userEvent.keyboard(' ')
    await expect(args.onPress).toHaveBeenCalledTimes(2)

    // Resolved outside waitFor: the probe element it adds would retrigger the wait.
    const hoverColor = tokenColor('--action-primary-hover')
    await userEvent.hover(button)
    await waitFor(() => expect(button).toHaveStyle({ backgroundColor: hoverColor }))
  },
}

export const Secondary: Story = {
  args: { variant: 'secondary', children: 'Отмена' },
}

export const Tertiary: Story = {
  args: { variant: 'tertiary', children: 'Сбросить поиск' },
}

export const Danger: Story = {
  args: { variant: 'danger', children: 'Удалить карточку' },
}

export const DangerQuiet: Story = {
  args: { variant: 'danger-quiet', size: 'sm', children: 'Удалить' },
}

export const WithIcon: Story = {
  args: {
    variant: 'primary',
    children: (
      <>
        <PlusIcon />
        Добавить сотрудника
      </>
    ),
  },
  play: async ({ canvas }) => {
    const button = canvas.getByRole('button')

    await expect(button).toHaveAccessibleName('Добавить сотрудника')
    await expect(button.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  },
}

export const Small: Story = {
  args: {
    variant: 'secondary',
    size: 'sm',
    children: (
      <>
        <ChevronLeftIcon />
        Назад
      </>
    ),
  },
  // The test frame has no padding, and the hit area must not start outside the viewport.
  decorators: [
    (Story) => (
      <div style={{ padding: 'var(--space-4)' }}>
        <Story />
      </div>
    ),
  ],
  play: async ({ canvas }) => {
    const button = canvas.getByRole('button', { name: 'Назад' })
    const { top, bottom, left, width } = button.getBoundingClientRect()
    const hitArea = Number.parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--size-control'),
    )
    const extension = (hitArea - (bottom - top)) / 2
    const x = left + width / 2

    await expect(extension).toBeGreaterThan(0)
    await expect(document.elementFromPoint(x, top - extension + 0.5)).toBe(button)
    await expect(document.elementFromPoint(x, bottom + extension - 0.5)).toBe(button)
  },
}

export const Disabled: Story = {
  args: { variant: 'primary', isDisabled: true, children: 'Сохранить сотрудника' },
  play: async ({ args, canvas, userEvent }) => {
    const button = canvas.getByRole('button', { name: 'Сохранить сотрудника' })

    await expect(button).toBeDisabled()
    await userEvent.tab()
    await expect(button).not.toHaveFocus()
    await userEvent.click(button)
    await expect(args.onPress).not.toHaveBeenCalled()
  },
}

export const Pending: Story = {
  args: { variant: 'secondary', children: 'Повторить' },
  render: function Render({ onPress, ...args }) {
    const [isPending, setIsPending] = useState(false)

    return (
      <Button
        {...args}
        variant="secondary"
        isPending={isPending}
        pendingLabel="Загружаем…"
        onPress={(event) => {
          onPress?.(event)
          setIsPending(true)
        }}
      >
        <RotateCwIcon />
        Повторить
      </Button>
    )
  },
  play: async ({ args, canvas, userEvent }) => {
    const button = canvas.getByRole('button', { name: 'Повторить' })
    const { width } = button.getBoundingClientRect()
    const controlHeight = Number.parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--size-control'),
    )

    await userEvent.tab()
    await userEvent.keyboard('{Enter}')
    await expect(button).toHaveAccessibleName('Загружаем…')
    await expect(button).toHaveAttribute('aria-disabled', 'true')
    await expect(button).toHaveFocus()
    await expect(button.getBoundingClientRect().width).toBe(width)
    await expect(button.getBoundingClientRect().height).toBe(controlHeight)

    await userEvent.keyboard('{Enter}')
    await userEvent.keyboard(' ')
    await expect(args.onPress).toHaveBeenCalledTimes(1)
  },
}

const row = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 'var(--space-4)',
  alignItems: 'center',
} as const

export const Overview: Story = {
  args: { variant: 'primary', children: 'Сохранить сотрудника' },
  render: () => (
    <div style={{ display: 'grid', gap: 'var(--space-4)' }}>
      <div style={row}>
        <Button variant="primary">Сохранить сотрудника</Button>
        <Button variant="primary" isDisabled>
          Сохранить сотрудника
        </Button>
        <Button variant="primary" isPending pendingLabel="Сохраняем…">
          Сохранить сотрудника
        </Button>
      </div>
      <div style={row}>
        <Button variant="secondary">Отмена</Button>
        <Button variant="secondary" isDisabled>
          Отмена
        </Button>
        <Button variant="secondary" isPending pendingLabel="Загружаем…">
          Отмена
        </Button>
      </div>
      <div style={row}>
        <Button variant="tertiary">Сбросить поиск</Button>
        <Button variant="tertiary" isDisabled>
          Сбросить поиск
        </Button>
      </div>
      <div style={row}>
        <Button variant="danger">Удалить карточку</Button>
        <Button variant="danger" isDisabled>
          Удалить карточку
        </Button>
        <Button variant="danger" isPending pendingLabel="Удаляем…">
          Удалить карточку
        </Button>
      </div>
      <div style={row}>
        <Button variant="danger-quiet" size="sm">
          Удалить
        </Button>
        <Button variant="danger-quiet" size="sm" isDisabled>
          Удалить
        </Button>
      </div>
    </div>
  ),
}
