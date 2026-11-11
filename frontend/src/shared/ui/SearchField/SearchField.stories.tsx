import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn } from 'storybook/test'

import { expectFocusRing } from '../storyChecks'
import { SearchField } from './SearchField'

const meta = {
  title: 'Forms/SearchField',
  component: SearchField,
  args: {
    label: 'Поиск сотрудников',
    placeholder: 'ФИО, email, должность или отдел',
    onChange: fn(),
    onClear: fn(),
  },
  decorators: [
    (Story) => (
      <div style={{ maxWidth: 'var(--size-search-max)' }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof SearchField>

export default meta

type Story = StoryObj<typeof meta>

export const Empty: Story = {
  play: async ({ args, canvas, canvasElement, userEvent }) => {
    const input = canvas.getByRole('searchbox', { name: 'Поиск сотрудников' })

    await expect(input).toHaveAttribute('placeholder', 'ФИО, email, должность или отдел')
    await expect(canvas.queryByRole('button')).not.toBeInTheDocument()
    await expect(canvasElement.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')

    await userEvent.tab()
    await expectFocusRing(input)
    await userEvent.keyboard('разраб')
    await expect(args.onChange).toHaveBeenLastCalledWith('разраб')
    await userEvent.keyboard('{Escape}')
    await expect(input).toHaveValue('')
    await expect(input).toHaveFocus()
    await expect(args.onClear).toHaveBeenCalledTimes(1)
  },
}

export const WithValue: Story = {
  args: { defaultValue: 'Соколова' },
  play: async ({ args, canvas, userEvent }) => {
    const input = canvas.getByRole('searchbox', { name: 'Поиск сотрудников' })
    const clear = canvas.getByRole('button', { name: 'Очистить поиск' })

    await userEvent.tab()
    await expect(input).toHaveFocus()
    await userEvent.tab()
    await expect(clear).not.toHaveFocus()

    await userEvent.click(clear)
    await expect(input).toHaveValue('')
    await expect(input).toHaveFocus()
    await expect(args.onClear).toHaveBeenCalledTimes(1)
    await expect(clear).not.toBeInTheDocument()
  },
}
