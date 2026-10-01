import assert from 'node:assert/strict'
import { test } from 'node:test'
import { displayEmployeeName, matchesEmployeeQuery } from '../src/features/employees/employeeSearch.ts'

const employee = {
  first_name: 'Анна',
  last_name: 'Петрова',
  middle_name: 'Сергеевна',
  email: 'anna@example.org',
  position: 'HR-менеджер',
  department: 'Люди',
}

test('search matches the employee name in the displayed surname-first order', () => {
  assert.equal(displayEmployeeName(employee), 'Петрова Анна Сергеевна')
  assert.equal(matchesEmployeeQuery(employee, 'Петрова Анна'), true)
})

test('search keeps matching the original first-name-first order and other fields', () => {
  assert.equal(matchesEmployeeQuery(employee, 'Анна Петрова'), true)
  assert.equal(matchesEmployeeQuery(employee, 'anna@example.org'), true)
  assert.equal(matchesEmployeeQuery(employee, 'несуществующее имя'), false)
})
