import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, fn, waitFor } from 'storybook/test'

import { Button } from '../Button/Button'
import { expectFocusRing, tokenColor } from '../storyChecks'
import { TextField } from './TextField'

const meta = {
  title: 'Forms/TextField',
  component: TextField,
  args: { label: 'Фамилия', onChange: fn() },
  decorators: [
    (Story) => (
      <div style={{ maxWidth: 'var(--size-form-max)' }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof TextField>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { autoComplete: 'family-name' },
  play: async ({ args, canvas, userEvent }) => {
    const input = canvas.getByRole('textbox', { name: 'Фамилия' })
    // Resolved outside waitFor: the probe element it adds would retrigger the wait.
    const focusColor = tokenColor('--focus-ring')

    await userEvent.tab()
    await expectFocusRing(input)
    await waitFor(() => expect(input).toHaveStyle({ borderColor: focusColor }))
    await userEvent.keyboard('Соколова')
    await expect(input).toHaveValue('Соколова')
    await expect(args.onChange).toHaveBeenLastCalledWith('Соколова')

    const hoverColor = tokenColor('--text-primary')
    await userEvent.tab()
    await userEvent.hover(input)
    await waitFor(() => expect(input).toHaveStyle({ borderColor: hoverColor }))
  },
}

export const Optional: Story = {
  args: { label: 'Отчество', isOptional: true, defaultValue: 'Сергеевна' },
  play: async ({ canvas }) => {
    await expect(canvas.getByRole('textbox')).toHaveAccessibleName('Отчество (необязательно)')
  },
}

export const WithDescription: Story = {
  args: {
    label: 'Slug',
    description: 'Латинские буквы, цифры, точка и дефис. Подставится по фамилии и имени.',
  },
  play: async ({ canvas }) => {
    await expect(canvas.getByRole('textbox', { name: 'Slug' })).toHaveAccessibleDescription(
      'Латинские буквы, цифры, точка и дефис. Подставится по фамилии и имени.',
    )
  },
}

export const Status: Story = {
  args: {
    label: 'Slug',
    defaultValue: 'anna.sokolova',
    description: 'Подставлен по ФИО. Латинские буквы, цифры, точка и дефис.',
  },
  render: function Render(args) {
    const [isLookingUp, setIsLookingUp] = useState(false)

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <TextField {...args} {...(isLookingUp && { status: 'Подбираем свободный slug…' })} />
        <div>
          <Button
            variant="secondary"
            size="sm"
            onPress={() => {
              setIsLookingUp(true)
            }}
          >
            Подобрать по ФИО
          </Button>
        </div>
      </div>
    )
  },
  play: async ({ canvas, userEvent }) => {
    const input = canvas.getByRole('textbox', { name: 'Slug' })
    const region = canvas.getByRole('status')

    await expect(region).toHaveTextContent('Подставлен по ФИО.')
    await userEvent.click(canvas.getByRole('button', { name: 'Подобрать по ФИО' }))
    // A live region announces changes only if it was in the page before them.
    await expect(canvas.getByRole('status')).toBe(region)
    await expect(region).toHaveTextContent('Подбираем свободный slug…')
    await expect(input).toHaveAccessibleDescription('Подбираем свободный slug…')
    await expect(input).toBeEnabled()
  },
}

export const Invalid: Story = {
  args: {
    label: 'Рабочий email',
    type: 'email',
    autoComplete: 'email',
    defaultValue: 'a.sokolova@accessflow.example',
    description: 'Адрес в домене компании.',
    errorMessage: 'Сотрудник с таким email уже есть. Укажите другой адрес.',
  },
  play: async ({ canvas, canvasElement }) => {
    const input = canvas.getByRole('textbox', { name: 'Рабочий email' })
    const danger = tokenColor('--action-danger')

    await expect(input).toHaveAttribute('aria-invalid', 'true')
    await expect(input).toHaveAccessibleDescription(
      'Сотрудник с таким email уже есть. Укажите другой адрес.',
    )
    await expect(canvas.queryByText('Адрес в домене компании.')).not.toBeInTheDocument()
    await expect(input).toHaveStyle({
      borderColor: danger,
      boxShadow: `${danger} 0px 0px 0px 1px inset`,
    })
    await expect(canvasElement.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  },
}

export const Disabled: Story = {
  args: { label: 'Должность', defaultValue: 'Frontend-разработчик', isDisabled: true },
  play: async ({ canvas, userEvent }) => {
    const input = canvas.getByRole('textbox', { name: 'Должность' })

    await expect(input).toBeDisabled()
    await userEvent.tab()
    await expect(input).not.toHaveFocus()
  },
}

export const ReadOnly: Story = {
  args: { label: 'Идентификатор', defaultValue: '4f1c2a9e', isReadOnly: true },
  play: async ({ canvas, userEvent }) => {
    const input = canvas.getByRole('textbox', { name: 'Идентификатор' })

    await userEvent.tab()
    await expect(input).toHaveFocus()
    await userEvent.keyboard('0')
    await expect(input).toHaveValue('4f1c2a9e')
    await expect(input).toHaveStyle({ backgroundColor: tokenColor('--bg-sunken') })
  },
}
