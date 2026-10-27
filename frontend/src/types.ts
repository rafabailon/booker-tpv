export type Role = 'admin' | 'supervisor' | 'cashier'
export type PaymentMethod = 'cash' | 'card' | 'other'

export interface User {
  id: string
  username: string
  role: Role
  is_active?: boolean
  created_at?: string
}

export interface StoreConfig {
  currency: string
  prices_include_tax: boolean
  low_stock_threshold: number
}

export interface Book {
  id: string
  isbn: string | null
  title: string
  authors: string
  publisher: string | null
  category: string | null
  price: string
  tax_rate: string
  stock: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface BookPage {
  items: Book[]
  page: number
  page_size: number
  total: number
}

export interface SaleItem {
  id: string
  book_id: string | null
  isbn_snapshot: string | null
  title_snapshot: string
  quantity: number
  unit_price: string
  tax_rate_snapshot: string
  tax_amount: string
  line_total: string
  returned_quantity: number
}

export interface Payment {
  method: PaymentMethod
  amount: string
  cash_received: string | null
  change_given: string | null
}

export interface Sale {
  id: string
  receipt_number: string
  created_at: string
  status: 'completed' | 'partially_returned' | 'returned'
  subtotal: string
  tax_total: string
  total: string
  currency: string
  items: SaleItem[]
  payments: Payment[]
}

export interface PageSales {
  items: Sale[]
  page: number
  page_size: number
  total: number
}

export interface StockMovement {
  id: string
  book_id: string
  quantity_delta: number
  reason: string
  created_at: string
  notes: string | null
}

export interface DailyReport {
  date: string
  total: string
  sold_total: string
  refunded_total: string
  currency: string
  sale_count: number
  return_count: number
}