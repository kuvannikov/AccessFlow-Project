import { CalendarDate } from '@internationalized/date'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { useEffect, useEffectEvent, useState } from 'react'
import {
  Controller,
  type ControllerFieldState,
  type ControllerRenderProps,
  useForm,
} from 'react-hook-form'
import { expect, fn, waitFor, within } from 'storybook/test'

import { Button } from '../Button/Button'
import { DateField } from '../DateField/DateField'
import { type DateEntry, dateEntryError } from '../DateField/dateEntry'
import { tokenColor } from '../storyChecks'
import { TextField } from '../TextField/TextField'
import { Form, FormGroup, FormRow } from './Form'

interface EmployeeValues {
  lastName: string
  firstName: string
  middleName: string
  email: string
  startDate: DateEntry
}

type SaveResult = 'saved' | 'email_taken' | 'rejected'

// Reading order, which is also the order in which focus looks for the first error.
const FIELD_ORDER = [
  'lastName',
  'firstName',
  'middleName',
  'email',
  'startDate',
] as const satisfies readonly (keyof EmployeeValues)[]

const EMPTY: EmployeeValues = {
  lastName: '',
  firstName: '',
  middleName: '',
  email: '',
  startDate: { status: 'empty' },
}

const FILLED: EmployeeValues = {
  lastName: 'Громова',
  firstName: 'Ксения',
  middleName: 'Олеговна',
  email: 'k.gromova@accessflow.example',
  startDate: { status: 'complete', date: new CalendarDate(2026, 10, 19) },
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+$/
const EMAIL_TAKEN = 'Сотрудник с таким email уже есть. Укажите другой адрес.'
const BODY_REJECTED = 'Сервер не принял данные. Проверьте поля и отправьте ещё раз.'

function required(message: string) {
  return (value: string) => value.trim() !== '' || message
}

function textFieldBinding<Name extends 'lastName' | 'firstName' | 'middleName' | 'email'>({
  field,
  fieldState,
}: {
  field: ControllerRenderProps<EmployeeValues, Name>
  fieldState: ControllerFieldState
}) {
  return {
    name: field.name,
    value: field.value,
    onChange: field.onChange,
    onBlur: field.onBlur,
    ref: field.ref,
    errorMessage: fieldState.error?.message,
  }
}

function EmployeeForm({
  defaultValues,
  save,
}: {
  defaultValues: EmployeeValues
  save: (values: EmployeeValues) => Promise<SaveResult>
}) {
  const [takenEmail, setTakenEmail] = useState<string>()
  const {
    control,
    handleSubmit,
    setError,
    setFocus,
    formState: { errors, isSubmitting, submitCount },
  } = useForm({
    defaultValues,
    mode: 'onBlur',
    reValidateMode: 'onBlur',
    shouldFocusError: false,
  })

  const focusFirstError = useEffectEvent(() => {
    const name = FIELD_ORDER.find((field) => errors[field])
    if (name) {
      setFocus(name)
    }
  })

  // The fields are disabled while the form is sent, so focus can reach an error only after
  // they are enabled again; this covers client errors and the ones the server returns.
  useEffect(() => {
    if (!isSubmitting && submitCount > 0) {
      focusFirstError()
    }
  }, [isSubmitting, submitCount])

  const submit = handleSubmit(async (values) => {
    switch (await save(values)) {
      case 'email_taken':
        setTakenEmail(values.email)
        setError('email', { type: 'conflict', message: EMAIL_TAKEN })
        break
      case 'rejected':
        // Root errors are cleared by the next submit.
        setError('root.server', { message: BODY_REJECTED })
        break
      case 'saved':
        break
    }
  })

  return (
    <Form
      onSubmit={(event) => {
        void submit(event)
      }}
      error={errors.root?.server && <p role="alert">{errors.root.server.message}</p>}
      actions={
        <>
          <Button
            type="submit"
            variant="primary"
            isPending={isSubmitting}
            pendingLabel="Сохраняем…"
          >
            Сохранить сотрудника
          </Button>
          {/* A link back to the list once routing exists; leaving now would hide the outcome. */}
          <Button variant="secondary" aria-disabled={isSubmitting}>
            Отмена
          </Button>
        </>
      }
    >
      <FormGroup legend="Личные данные" isDisabled={isSubmitting}>
        <FormRow>
          <Controller
            control={control}
            name="lastName"
            rules={{ validate: required('Укажите фамилию.') }}
            render={(props) => (
              <TextField label="Фамилия" autoComplete="family-name" {...textFieldBinding(props)} />
            )}
          />
          <Controller
            control={control}
            name="firstName"
            rules={{ validate: required('Укажите имя.') }}
            render={(props) => (
              <TextField label="Имя" autoComplete="given-name" {...textFieldBinding(props)} />
            )}
          />
        </FormRow>
        <Controller
          control={control}
          name="middleName"
          render={(props) => (
            <TextField
              label="Отчество"
              isOptional
              autoComplete="additional-name"
              {...textFieldBinding(props)}
            />
          )}
        />
        <Controller
          control={control}
          name="email"
          rules={{
            validate: {
              required: required('Укажите рабочий email.'),
              format: (value) =>
                EMAIL_PATTERN.test(value) || 'Email записан неверно. Укажите адрес вида имя@домен.',
              // Keeps the server's answer while the address stays the same.
              free: (value) => value !== takenEmail || EMAIL_TAKEN,
            },
          }}
          render={(props) => (
            <TextField
              label="Рабочий email"
              type="email"
              autoComplete="email"
              {...textFieldBinding(props)}
            />
          )}
        />
      </FormGroup>
      <FormGroup legend="Работа и выход" isDisabled={isSubmitting}>
        <Controller
          control={control}
          name="startDate"
          rules={{ validate: (entry) => dateEntryError(entry) ?? true }}
          render={({ field, fieldState }) => (
            <div style={{ maxWidth: 'var(--size-date-field)' }}>
              <DateField
                label="Дата выхода"
                name={field.name}
                // The field is uncontrolled: it reads the value once, when it mounts.
                defaultValue={
                  defaultValues.startDate.status === 'complete'
                    ? defaultValues.startDate.date
                    : null
                }
                onChange={field.onChange}
                onBlur={field.onBlur}
                ref={field.ref}
                errorMessage={fieldState.error?.message}
              />
            </div>
          )}
        />
      </FormGroup>
    </Form>
  )
}

const meta = {
  title: 'Forms/Form',
  component: EmployeeForm,
  args: { defaultValues: EMPTY, save: fn(() => Promise.resolve<SaveResult>('saved')) },
} satisfies Meta<typeof EmployeeForm>

export default meta

type Story = StoryObj<typeof meta>

function fieldsOf(root: HTMLElement) {
  const canvas = within(root)
  return {
    lastName: canvas.getByRole('textbox', { name: 'Фамилия' }),
    firstName: canvas.getByRole('textbox', { name: 'Имя' }),
    middleName: canvas.getByRole('textbox', { name: 'Отчество (необязательно)' }),
    email: canvas.getByRole('textbox', { name: 'Рабочий email' }),
    startDate: canvas.getByRole('group', { name: 'Дата выхода' }),
    day: canvas.getByRole('spinbutton', { name: 'день, Дата выхода' }),
    submit: canvas.getByRole('button', { name: 'Сохранить сотрудника' }),
    cancel: canvas.getByRole('button', { name: 'Отмена' }),
  }
}

export const Empty: Story = {
  play: async ({ args, canvas, canvasElement, userEvent }) => {
    const fields = fieldsOf(canvasElement)
    const form = canvasElement.querySelector('form')
    const tokens = getComputedStyle(document.documentElement)

    await expect(canvas.getByRole('group', { name: 'Личные данные' })).toContainElement(
      fields.email,
    )
    await expect(canvas.getByRole('group', { name: 'Работа и выход' })).toContainElement(
      fields.startDate,
    )
    await expect(form).toHaveStyle({ maxWidth: tokens.getPropertyValue('--size-form-max') })
    await expect(fields.lastName.getBoundingClientRect().top).toBe(
      fields.firstName.getBoundingClientRect().top,
    )
    await expect(fields.submit.getBoundingClientRect().left).toBe(
      form?.getBoundingClientRect().left,
    )
    await expect(fields.cancel.getBoundingClientRect().left).toBeGreaterThan(
      fields.submit.getBoundingClientRect().right,
    )

    await userEvent.click(fields.submit)

    await waitFor(() => expect(fields.lastName).toHaveFocus())
    await expect(fields.lastName).toHaveAccessibleDescription('Укажите фамилию.')
    await expect(fields.firstName).toHaveAccessibleDescription('Укажите имя.')
    await expect(fields.email).toHaveAccessibleDescription('Укажите рабочий email.')
    await expect(fields.middleName).not.toHaveAttribute('aria-invalid', 'true')
    await expect(fields.startDate).not.toHaveAttribute('data-invalid')
    await expect(args.save).not.toHaveBeenCalled()
  },
}

export const ValidatesOnBlur: Story = {
  play: async ({ canvasElement, userEvent }) => {
    const fields = fieldsOf(canvasElement)

    await userEvent.tab()
    await userEvent.tab()
    await expect(fields.lastName).toHaveAccessibleDescription('Укажите фамилию.')
    await expect(fields.firstName).not.toHaveAttribute('aria-invalid', 'true')

    await userEvent.click(fields.lastName)
    await userEvent.keyboard('Громова')
    // Typing alone does not judge the value; leaving the field does.
    await expect(fields.lastName).toHaveAttribute('aria-invalid', 'true')
    await userEvent.tab()
    await expect(fields.lastName).not.toHaveAttribute('aria-invalid', 'true')

    await userEvent.click(fields.email)
    await userEvent.keyboard('k.gromova')
    await userEvent.tab()
    await expect(fields.email).toHaveAccessibleDescription(
      'Email записан неверно. Укажите адрес вида имя@домен.',
    )

    await userEvent.keyboard('1910')
    // The calendar button is part of the field, so it takes two steps to leave it.
    await userEvent.tab()
    await userEvent.tab()
    await expect(fields.startDate).toHaveAccessibleDescription(
      'Введите дату полностью: день, месяц и год.',
    )
  },
}

export const CorrectsNonexistentDate: Story = {
  play: async ({ canvasElement, userEvent }) => {
    const fields = fieldsOf(canvasElement)

    await userEvent.click(fields.day)
    await userEvent.keyboard('31022026')
    await userEvent.click(fields.lastName)

    // React Aria moves a day past the end of the month to its last day once the field loses focus.
    await expect(fields.day).toHaveTextContent('28')
    await expect(fields.startDate).not.toHaveAttribute('data-invalid')
    await expect(fields.startDate).toHaveAccessibleDescription('Выбранная дата: 28 февраля 2026 г.')
  },
}

export const FocusesFirstInvalidField: Story = {
  args: { defaultValues: { ...FILLED, startDate: { status: 'empty' } } },
  play: async ({ args, canvasElement, userEvent }) => {
    const fields = fieldsOf(canvasElement)

    await userEvent.click(fields.day)
    await userEvent.keyboard('1910')
    await userEvent.click(fields.submit)

    await waitFor(() => expect(fields.day).toHaveFocus())
    await expect(fields.startDate).toHaveAccessibleDescription(
      'Введите дату полностью: день, месяц и год.',
    )
    await expect(args.save).not.toHaveBeenCalled()

    await userEvent.clear(fields.email)
    await userEvent.click(fields.submit)
    await waitFor(() => expect(fields.email).toHaveFocus())
    await expect(fields.email).toHaveAccessibleDescription('Укажите рабочий email.')
  },
}

export const Submitting: Story = {
  args: {
    defaultValues: FILLED,
    save: fn(() => new Promise<SaveResult>(() => undefined)),
  },
  play: async ({ args, canvas, canvasElement, userEvent }) => {
    const fields = fieldsOf(canvasElement)

    await userEvent.dblClick(fields.submit)

    await waitFor(() => expect(fields.submit).toHaveTextContent('Сохраняем…'))
    await expect(args.save).toHaveBeenCalledOnce()
    await expect(args.save).toHaveBeenCalledWith(FILLED)
    await expect(fields.submit).toHaveAttribute('aria-disabled', 'true')
    await expect(fields.cancel).toHaveAttribute('aria-disabled', 'true')
    // Resolved outside waitFor: the probe element it adds would retrigger the wait.
    const disabledLook = {
      backgroundColor: tokenColor('--bg-disabled'),
      color: tokenColor('--text-disabled'),
    }
    await userEvent.hover(fields.cancel)
    await waitFor(() => expect(fields.cancel).toHaveStyle(disabledLook))
    await expect(canvas.getByRole('group', { name: 'Личные данные' })).toBeDisabled()
    await expect(canvas.getByRole('group', { name: 'Работа и выход' })).toBeDisabled()
    for (const input of [fields.lastName, fields.firstName, fields.middleName, fields.email]) {
      await expect(input).toBeDisabled()
    }
    await expect(fields.startDate).toHaveAttribute('aria-disabled', 'true')
    await expect(canvas.getByRole('button', { name: /Открыть календарь/ })).toBeDisabled()
    await userEvent.tab({ shift: true })
    await expect(canvasElement.querySelector('fieldset')).not.toContainElement(
      document.activeElement as HTMLElement,
    )

    await userEvent.click(fields.submit)
    await userEvent.keyboard('{Enter}')
    await expect(args.save).toHaveBeenCalledOnce()
  },
}

export const EmailTaken: Story = {
  args: {
    defaultValues: FILLED,
    save: fn((values: EmployeeValues) =>
      Promise.resolve<SaveResult>(values.email === FILLED.email ? 'email_taken' : 'saved'),
    ),
  },
  play: async ({ args, canvasElement, userEvent }) => {
    const fields = fieldsOf(canvasElement)

    await userEvent.click(fields.submit)

    await waitFor(() => expect(fields.email).toHaveFocus())
    await expect(fields.email).toHaveAccessibleDescription(EMAIL_TAKEN)
    await expect(fields.email).toHaveValue(FILLED.email)
    await expect(fields.lastName).toHaveValue(FILLED.lastName)
    await expect(fields.day).toHaveTextContent('19')

    await userEvent.tab()
    await expect(fields.email).toHaveAccessibleDescription(EMAIL_TAKEN)

    await userEvent.clear(fields.email)
    await userEvent.keyboard('k.gromova2@accessflow.example')
    await userEvent.tab()
    await expect(fields.email).not.toHaveAttribute('aria-invalid', 'true')

    await userEvent.click(fields.submit)
    await waitFor(() => expect(args.save).toHaveBeenCalledTimes(2))
    await expect(args.save).toHaveBeenLastCalledWith({
      ...FILLED,
      email: 'k.gromova2@accessflow.example',
    })
  },
}

export const Narrow: Story = {
  decorators: [
    // The form's width on a 360 px screen with 16 px page margins.
    (Story) => (
      <div style={{ width: '328px' }}>
        <Story />
      </div>
    ),
  ],
  play: async ({ canvasElement }) => {
    const { lastName, firstName } = fieldsOf(canvasElement)

    await expect(firstName.getBoundingClientRect().top).toBeGreaterThan(
      lastName.getBoundingClientRect().bottom,
    )
    await expect(firstName.getBoundingClientRect().width).toBe(
      lastName.getBoundingClientRect().width,
    )
  },
}

export const FormError: Story = {
  args: {
    defaultValues: FILLED,
    save: fn(() => Promise.resolve<SaveResult>('rejected')),
  },
  play: async ({ canvas, canvasElement, userEvent }) => {
    const fields = fieldsOf(canvasElement)

    await userEvent.click(fields.submit)

    const alert = await canvas.findByRole('alert')
    await expect(alert).toHaveTextContent(BODY_REJECTED)
    const groups = canvasElement.querySelectorAll('fieldset')
    await expect(alert.compareDocumentPosition(groups[groups.length - 1] as Node)).toBe(
      Node.DOCUMENT_POSITION_PRECEDING,
    )
    await expect(alert.compareDocumentPosition(fields.submit)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
    await expect(fields.email).not.toHaveAttribute('aria-invalid', 'true')
  },
}
