import { CalendarDate, getLocalTimeZone, today } from '@internationalized/date'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, waitFor, within } from 'storybook/test'

import { tokenColor } from '../storyChecks'
import { DateField } from './DateField'

const meta = {
  title: 'Forms/DateField',
  component: DateField,
  args: { label: 'Дата выхода', onChange: fn() },
  decorators: [
    (Story) => (
      <div style={{ maxWidth: 'var(--size-date-field)' }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof DateField>

export default meta

type Story = StoryObj<typeof meta>

function segmentsOf(root: HTMLElement) {
  const canvas = within(root)
  return {
    day: canvas.getByRole('spinbutton', { name: 'день, Дата выхода' }),
    month: canvas.getByRole('spinbutton', { name: 'месяц, Дата выхода' }),
    year: canvas.getByRole('spinbutton', { name: 'год, Дата выхода' }),
  }
}

/** The calendar is rendered in a popover at the end of the body, outside the story canvas. */
function screen() {
  return within(document.body)
}

export const Empty: Story = {
  play: async ({ args, canvas, canvasElement, userEvent }) => {
    const group = canvas.getByRole('group', { name: 'Дата выхода' })
    const { day, month, year } = segmentsOf(canvasElement)
    const ringColor = tokenColor('--focus-ring')
    const fill = tokenColor('--action-primary')

    await expect(day).toHaveTextContent('дд')
    await expect(month).toHaveTextContent('мм')
    await expect(year).toHaveTextContent('гггг')

    await userEvent.tab()
    await expect(day).toHaveFocus()
    await waitFor(() =>
      expect(group).toHaveStyle({
        outlineStyle: 'solid',
        outlineWidth: getComputedStyle(document.documentElement).getPropertyValue('--ring-width'),
        outlineColor: ringColor,
        borderColor: ringColor,
      }),
    )
    await expect(day).toHaveStyle({ backgroundColor: fill })

    await userEvent.keyboard('14102026')
    await expect(day).toHaveTextContent('14')
    await expect(month).toHaveTextContent('10')
    await expect(year).toHaveTextContent('2026')
    await expect(args.onChange).toHaveBeenLastCalledWith({
      status: 'complete',
      date: new CalendarDate(2026, 10, 14),
    })
  },
}

export const SegmentLimits: Story = {
  play: async ({ canvasElement, userEvent }) => {
    const { day, month, year } = segmentsOf(canvasElement)

    await userEvent.tab()
    // 35 is not a day, so the second digit starts the value again and moves on.
    await userEvent.keyboard('35')
    await expect(day).toHaveTextContent('05')
    await expect(month).toHaveFocus()
    await userEvent.keyboard('13')
    await expect(month).toHaveTextContent('03')
    await expect(year).toHaveFocus()

    await userEvent.click(day)
    await userEvent.keyboard('{ArrowUp}')
    await expect(day).toHaveTextContent('06')
    await userEvent.keyboard('{ArrowDown}{ArrowDown}')
    await expect(day).toHaveTextContent('04')
    await userEvent.keyboard('31{Shift>}{Tab}{/Shift}{ArrowUp}')
    await expect(day).toHaveTextContent('01')
  },
}

export const Incomplete: Story = {
  play: async ({ args, userEvent }) => {
    await userEvent.tab()
    await userEvent.keyboard('1410')
    await userEvent.tab()
    await expect(args.onChange).toHaveBeenLastCalledWith({ status: 'incomplete' })
  },
}

export const Nonexistent: Story = {
  play: async ({ args, canvasElement, userEvent }) => {
    const { day, month, year } = segmentsOf(canvasElement)

    await userEvent.tab()
    await userEvent.keyboard('31022026')
    await expect(day).toHaveTextContent('31')
    await expect(month).toHaveTextContent('02')
    await expect(year).toHaveTextContent('2026')
    await expect(args.onChange).toHaveBeenLastCalledWith({ status: 'nonexistent' })
  },
}

export const Invalid: Story = {
  args: { errorMessage: 'Введите дату полностью: день, месяц и год.' },
  play: async ({ canvas, canvasElement }) => {
    const group = canvas.getByRole('group', { name: 'Дата выхода' })
    const danger = tokenColor('--action-danger')

    await expect(group).toHaveAccessibleDescription('Введите дату полностью: день, месяц и год.')
    await expect(group).toHaveStyle({
      borderColor: danger,
      boxShadow: `${danger} 0px 0px 0px 1px inset`,
    })
    await expect(canvasElement.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  },
}

export const Disabled: Story = {
  args: { defaultValue: new CalendarDate(2026, 10, 14), isDisabled: true },
  play: async ({ canvas, userEvent }) => {
    const group = canvas.getByRole('group', { name: 'Дата выхода' })

    await expect(group).toHaveAttribute('aria-disabled', 'true')
    await expect(group).toHaveStyle({ backgroundColor: tokenColor('--bg-disabled') })
    await expect(canvas.getByRole('button', { name: /Открыть календарь/ })).toBeDisabled()
    await userEvent.tab()
    await expect(group).not.toContainElement(document.activeElement as HTMLElement)
  },
}

export const CalendarKeyboard: Story = {
  args: { defaultValue: new CalendarDate(2026, 10, 14) },
  play: async ({ args, canvas, canvasElement, userEvent }) => {
    const group = canvas.getByRole('group', { name: 'Дата выхода' })
    const trigger = canvas.getByRole('button', { name: 'Открыть календарь Дата выхода' })

    await userEvent.tab()
    await userEvent.tab()
    await userEvent.tab()
    await userEvent.tab()
    await expect(trigger).toHaveFocus()
    await userEvent.keyboard('{Enter}')

    const dialog = await screen().findByRole('dialog', { name: 'Календарь: Дата выхода' })
    const calendar = within(dialog)
    await expect(calendar.getByText('Октябрь 2026')).toBeVisible()
    await expect(calendar.getByRole('button', { name: 'Предыдущий месяц' })).toBeEnabled()
    await expect(calendar.getByRole('button', { name: 'Следующий месяц' })).toBeEnabled()
    await expect(dialog.querySelectorAll('th')).toHaveLength(7)
    await expect(dialog.querySelector('th')).toHaveTextContent('пн')

    // Day labels come from React Aria and cannot be replaced.
    const selected = calendar.getByRole('button', { name: 'Выбрано среда, 14 октября 2026 г.' })
    await expect(selected).toHaveFocus()
    await expect(selected).toHaveStyle({ backgroundColor: tokenColor('--action-primary') })

    const popover = dialog.parentElement?.getBoundingClientRect()
    const space = getComputedStyle(document.documentElement).getPropertyValue('--space-1')
    await expect(popover?.top).toBe(group.getBoundingClientRect().bottom + Number.parseFloat(space))
    await expect(popover?.width).toBe(326)

    await userEvent.keyboard('{ArrowRight}')
    await expect(
      calendar.getByRole('button', { name: 'четверг, 15 октября 2026 г.' }),
    ).toHaveFocus()
    await userEvent.keyboard('{ArrowDown}')
    await expect(
      calendar.getByRole('button', { name: 'четверг, 22 октября 2026 г.' }),
    ).toHaveFocus()
    await userEvent.keyboard('{PageDown}')
    await expect(
      calendar.getByRole('button', { name: 'воскресенье, 22 ноября 2026 г.' }),
    ).toHaveFocus()
    await expect(calendar.getByText('Ноябрь 2026')).toBeVisible()
    await userEvent.keyboard('{PageUp}{PageUp}')
    await expect(calendar.getByText('Сентябрь 2026')).toBeVisible()
    await userEvent.keyboard('{PageDown}')
    // Home and End go to the first and last day of the month.
    await userEvent.keyboard('{Home}')
    await expect(calendar.getByRole('button', { name: 'четверг, 1 октября 2026 г.' })).toHaveFocus()
    await userEvent.keyboard('{End}')
    await expect(
      calendar.getByRole('button', { name: 'суббота, 31 октября 2026 г.' }),
    ).toHaveFocus()

    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(screen().queryByRole('dialog')).not.toBeInTheDocument())
    await expect(trigger).toHaveFocus()
    await expect(segmentsOf(canvasElement).day).toHaveTextContent('31')
    await expect(args.onChange).toHaveBeenLastCalledWith({
      status: 'complete',
      date: new CalendarDate(2026, 10, 31),
    })
  },
}

export const CalendarEscape: Story = {
  args: { defaultValue: new CalendarDate(2026, 10, 14) },
  play: async ({ args, canvas, canvasElement, userEvent }) => {
    const trigger = canvas.getByRole('button', { name: 'Открыть календарь Дата выхода' })

    await userEvent.click(trigger)
    await screen().findByRole('dialog', { name: 'Календарь: Дата выхода' })
    await userEvent.keyboard('{ArrowRight}{Escape}')
    await waitFor(() => expect(screen().queryByRole('dialog')).not.toBeInTheDocument())
    await expect(trigger).toHaveFocus()
    await expect(segmentsOf(canvasElement).day).toHaveTextContent('14')
    await expect(args.onChange).not.toHaveBeenCalled()
  },
}

export const Today: Story = {
  play: async ({ canvas, userEvent }) => {
    const now = today(getLocalTimeZone())

    await userEvent.click(canvas.getByRole('button', { name: 'Открыть календарь Дата выхода' }))
    const dialog = await screen().findByRole('dialog', { name: 'Календарь: Дата выхода' })
    const day = dialog.querySelector('[data-today]')

    await expect(day).toHaveFocus()
    await expect(day).toHaveTextContent(String(now.day))
    await expect(day?.getAttribute('aria-label')).toMatch(/^Сегодня, /)
    await expect(day).toHaveStyle({
      borderColor: tokenColor('--border-control'),
      fontWeight: '600',
    })
  },
}

export const MinMax: Story = {
  args: {
    defaultValue: new CalendarDate(2026, 10, 14),
    minValue: new CalendarDate(2026, 10, 5),
    maxValue: new CalendarDate(2026, 10, 20),
  },
  play: async ({ canvas, userEvent }) => {
    await userEvent.click(canvas.getByRole('button', { name: 'Открыть календарь Дата выхода' }))
    const calendar = within(await screen().findByRole('dialog'))

    const outside = calendar.getByRole('button', { name: 'воскресенье, 4 октября 2026 г.' })
    await expect(outside).toHaveAttribute('aria-disabled', 'true')
    await expect(outside).toHaveStyle({ color: tokenColor('--text-disabled') })
    await expect(calendar.getByRole('button', { name: 'Следующий месяц' })).toBeDisabled()
    await expect(calendar.getByRole('button', { name: 'Предыдущий месяц' })).toBeDisabled()

    await userEvent.keyboard('{Home}')
    await expect(
      calendar.getByRole('button', {
        name: 'понедельник, 5 октября 2026 г., Первая доступная дата',
      }),
    ).toHaveFocus()
  },
}
