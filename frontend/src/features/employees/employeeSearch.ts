import type { Employee } from '../../api'

type SearchableEmployee = Pick<
  Employee,
  'first_name' | 'last_name' | 'middle_name' | 'email' | 'position' | 'department'
>

export function displayEmployeeName(employee: SearchableEmployee) {
  return [employee.last_name, employee.first_name, employee.middle_name]
    .filter((name): name is string => Boolean(name?.trim()))
    .join(' ')
}

export function matchesEmployeeQuery(employee: SearchableEmployee, query: string) {
  const search = query.trim().toLocaleLowerCase('ru')
  if (!search) return true

  return `${displayEmployeeName(employee)} ${employee.first_name} ${employee.last_name} ${employee.middle_name || ''} ${employee.email} ${employee.position} ${employee.department}`
    .toLocaleLowerCase('ru')
    .includes(search)
}
