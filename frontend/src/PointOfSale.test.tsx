import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PointOfSale from './PointOfSale'
import { api } from './api'
import type { Book, Sale } from './types'

vi.mock('./api', () => ({
  api: {
    books: vi.fn(),
    checkout: vi.fn(),
  },
}))

const book: Book = {
  id: 'book-1',
  isbn: '9780306406157',
  title: 'El nombre del viento',
  authors: 'Patrick Rothfuss',
  publisher: null,
  category: null,
  price: '12.50',
  tax_rate: '0.00',
  stock: 3,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const sale: Sale = {
  id: 'sale-1',
  receipt_number: 'BT-20260101-12345678',
  created_at: '2026-01-01T10:00:00Z',
  status: 'completed',
  subtotal: '12.50',
  tax_total: '0.00',
  total: '12.50',
  currency: 'EUR',
  items: [{ id: 'line-1', book_id: book.id, isbn_snapshot: book.isbn, title_snapshot: book.title, quantity: 1, unit_price: '12.50', tax_rate_snapshot: '0.00', tax_amount: '0.00', line_total: '12.50', returned_quantity: 0 }],
  payments: [{ method: 'cash', amount: '12.50', cash_received: '12.50', change_given: '0.00' }],
}

describe('PointOfSale', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('crypto', { randomUUID: vi.fn(() => 'stable-request-key') })
    vi.mocked(api.books).mockResolvedValue({ items: [book], page: 1, page_size: 12, total: 1 })
  })

  it('sends the server-calculated sale and displays the saved receipt', async () => {
    vi.mocked(api.checkout).mockResolvedValue(sale)
    render(<PointOfSale onNotice={vi.fn()} />)

    fireEvent.click(await screen.findByRole('button', { name: /El nombre del viento/ }))
    expect(screen.getAllByText(/12,50/).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'Cobrar' }))

    await waitFor(() => expect(api.checkout).toHaveBeenCalledWith(
      'stable-request-key', [{ book_id: book.id, quantity: 1 }], [{ method: 'cash', amount: '12.50', cash_received: '12.50' }],
    ))
    expect(await screen.findByRole('button', { name: 'Imprimir ticket BT-20260101-12345678' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Ticket BT-20260101/)).toBeInTheDocument()
  })

  it('keeps the cart and reuses its idempotency key after a retryable error', async () => {
    vi.mocked(api.checkout).mockRejectedValueOnce(new Error('Conexión interrumpida')).mockResolvedValueOnce(sale as never)
    render(<PointOfSale onNotice={vi.fn()} />)

    fireEvent.click(await screen.findByRole('button', { name: /El nombre del viento/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Cobrar' }))
    expect(await screen.findByText('Conexión interrumpida')).toBeInTheDocument()
    expect(screen.getByText('1 artículo')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Cobrar' }))
    await waitFor(() => expect(api.checkout).toHaveBeenCalledTimes(2))
    expect(vi.mocked(api.checkout).mock.calls[0][0]).toBe('stable-request-key')
    expect(vi.mocked(api.checkout).mock.calls[1][0]).toBe('stable-request-key')
  })

  it('accepts a split cash and card payment only when allocations match the total', async () => {
    vi.mocked(api.checkout).mockResolvedValue(sale)
    render(<PointOfSale onNotice={vi.fn()} />)

    fireEvent.click(await screen.findByRole('button', { name: /El nombre del viento/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Dividir pago' }))
    fireEvent.change(screen.getByLabelText('Importe en efectivo'), { target: { value: '5.00' } })
    fireEvent.change(screen.getByLabelText('Importe con tarjeta'), { target: { value: '7.50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cobrar' }))

    await waitFor(() => expect(api.checkout).toHaveBeenCalledWith(
      'stable-request-key',
      [{ book_id: book.id, quantity: 1 }],
      [{ method: 'cash', amount: '5.00', cash_received: '5.00' }, { method: 'card', amount: '7.50' }],
    ))
  })
})