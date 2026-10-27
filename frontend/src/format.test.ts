import { describe, expect, it } from 'vitest'
import { formatMoney } from './format'

describe('formatMoney', () => {
  it('formats decimal strings with Spanish separators and the store currency', () => {
    const expected = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(12.5)
    expect(formatMoney('12.50', 'EUR')).toBe(expected)
  })

  it('formats numeric values and zero amounts', () => {
    expect(formatMoney(0, 'USD')).toBe(new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'USD' }).format(0))
  })
})
