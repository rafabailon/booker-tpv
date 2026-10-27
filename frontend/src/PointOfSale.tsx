import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Box, Button, CircularProgress, Divider, IconButton, InputAdornment, Paper, TextField, Typography } from '@mui/material'
import AddOutlined from '@mui/icons-material/AddOutlined'
import CreditCardOutlined from '@mui/icons-material/CreditCardOutlined'
import DeleteOutline from '@mui/icons-material/DeleteOutline'
import LocalOfferOutlined from '@mui/icons-material/LocalOfferOutlined'
import MenuBookOutlined from '@mui/icons-material/MenuBookOutlined'
import PaymentsOutlined from '@mui/icons-material/PaymentsOutlined'
import PrintOutlined from '@mui/icons-material/PrintOutlined'
import RemoveOutlined from '@mui/icons-material/RemoveOutlined'
import SearchOutlined from '@mui/icons-material/SearchOutlined'
import { api } from './api'
import { formatMoney } from './format'
import type { Book, PaymentMethod, Sale, StoreConfig } from './types'

interface CartLine { book: Book; quantity: number }

function cents(price: string): number {
  const [whole, fraction = ''] = price.split('.')
  return Number(whole) * 100 + Number(fraction.padEnd(2, '0').slice(0, 2))
}

function grossCents(book: Book, pricesIncludeTax: boolean): number {
  const base = BigInt(cents(book.price))
  if (pricesIncludeTax || Number(book.tax_rate) === 0) return Number(base)
  const [whole, fraction = ''] = book.tax_rate.split('.')
  const rateBasisPoints = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0').slice(0, 2))
  return Number((base * (10000n + rateBasisPoints) + 5000n) / 10000n)
}

export default function PointOfSale({ config, onNotice }: { config?: StoreConfig; onNotice: (message: string) => void }) {
  const currency = config?.currency ?? 'EUR'
  const [search, setSearch] = useState('')
  const [books, setBooks] = useState<Book[]>([])
  const [cart, setCart] = useState<CartLine[]>([])
  const [method, setMethod] = useState<PaymentMethod>('cash')
  const [cashReceived, setCashReceived] = useState('')
  const [splitPayment, setSplitPayment] = useState(false)
  const [cashAmount, setCashAmount] = useState('0.00')
  const [cardAmount, setCardAmount] = useState('0.00')
  const [loadingBooks, setLoadingBooks] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState<Sale | null>(null)
  const requestKey = useRef<string | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const totalCents = useMemo(() => cart.reduce((sum, line) => sum + grossCents(line.book, config?.prices_include_tax ?? true) * line.quantity, 0), [cart, config?.prices_include_tax])
  const itemCount = cart.reduce((sum, line) => sum + line.quantity, 0)
  const total = (totalCents / 100).toFixed(2)
  const splitTotal = cents(cashAmount || '0') + cents(cardAmount || '0')
  const splitIsValid = splitTotal === totalCents && (cents(cashAmount || '0') > 0 || cents(cardAmount || '0') > 0)

  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoadingBooks(true)
      const params = new URLSearchParams({ page_size: '12' })
      if (search.trim()) params.set('q', search.trim())
      api.books(params, controller.signal).then((result) => setBooks(result.items)).catch((cause: unknown) => {
        if (cause instanceof Error && cause.name === 'AbortError') return
        setError(cause instanceof Error ? cause.message : 'No se pudo buscar el catálogo')
      }).finally(() => {
        if (!controller.signal.aborted) setLoadingBooks(false)
      })
    }, 180)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [search])

  function addBook(book: Book) {
    if (book.stock < 1) return
    requestKey.current = null
    setReceipt(null)
    setSplitPayment(false)
    setCart((current) => {
      const found = current.find((line) => line.book.id === book.id)
      if (found) return current.map((line) => line.book.id === book.id ? { ...line, quantity: Math.min(line.quantity + 1, book.stock) } : line)
      return [...current, { book, quantity: 1 }]
    })
    setError('')
    searchRef.current?.focus()
  }

  function changeQuantity(bookId: string, delta: number) {
    requestKey.current = null
    setReceipt(null)
    setSplitPayment(false)
    setCart((current) => current.flatMap((line) => {
      if (line.book.id !== bookId) return [line]
      const quantity = line.quantity + delta
      return quantity < 1 ? [] : [{ ...line, quantity: Math.min(quantity, line.book.stock) }]
    }))
  }

  async function handleCheckout() {
    if (!cart.length) return
    setBusy(true)
    setError('')
    requestKey.current ??= crypto.randomUUID()
    const payments = splitPayment
      ? [
          ...(cents(cashAmount || '0') > 0 ? [{ method: 'cash' as const, amount: cashAmount, cash_received: cashReceived || cashAmount }] : []),
          ...(cents(cardAmount || '0') > 0 ? [{ method: 'card' as const, amount: cardAmount }] : []),
        ]
      : [{ method: method as 'cash' | 'card', amount: total, ...(method === 'cash' ? { cash_received: cashReceived || total } : {}) }]
    try {
      const sale = await api.checkout(requestKey.current, cart.map(({ book, quantity }) => ({ book_id: book.id, quantity })), payments)
      setReceipt(sale)
      setCart([])
      setCashReceived('')
      setSplitPayment(false)
      setCashAmount('0.00')
      setCardAmount('0.00')
      requestKey.current = null
      onNotice(`Venta ${sale.receipt_number} registrada`)
      searchRef.current?.focus()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo completar la venta. Puedes reintentar.')
    } finally {
      setBusy(false)
    }
  }

  async function scanISBN() {
    const params = new URLSearchParams({ isbn: search.trim(), page_size: '1' })
    const page = await api.books(params)
    if (page.items[0]) addBook(page.items[0])
    else setError('No se encontró un libro con ese ISBN')
  }

  return (
    <Box className="pos-page">
      <Box className="page-heading">
        <Box><Typography component="h1">Caja</Typography><Typography className="page-subtitle">Venta en mostrador</Typography></Box>
        <div className="register-open"><span className="connection-dot" />Caja abierta</div>
      </Box>
      <Box className="pos-layout">
        <Box className="catalog-column">
          <TextField
            inputRef={searchRef}
            autoFocus
            fullWidth
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter' && search.trim()) void scanISBN() }}
            placeholder="Buscar título, autor o escanear ISBN"
            inputProps={{ 'aria-label': 'Buscar libros o escanear ISBN' }}
            InputProps={{ startAdornment: <InputAdornment position="start"><SearchOutlined /></InputAdornment> }}
          />
          <Box className="results-heading"><Typography component="h2">Catálogo</Typography><Typography>{loadingBooks ? 'Buscando…' : `${books.length} resultados`}</Typography></Box>
          <Box className="product-list">
            {loadingBooks && !books.length && <Box className="inline-loading"><CircularProgress size={24} /></Box>}
            {!loadingBooks && !books.length && <Box className="empty-results"><MenuBookOutlined /><span>No hay libros que mostrar</span></Box>}
            {books.map((book) => (
              <Paper component="button" elevation={0} className={`product-row ${book.stock < 1 ? 'out-of-stock' : ''}`} key={book.id} onClick={() => addBook(book)} disabled={book.stock < 1}>
                <Box className="cover-mark"><MenuBookOutlined /></Box>
                <Box className="product-info"><strong>{book.title}</strong><span>{book.authors || 'Autor no indicado'}{book.isbn ? ` · ${book.isbn}` : ''}</span></Box>
                <Box className="product-meta"><strong>{formatMoney(grossCents(book, config?.prices_include_tax ?? true) / 100, currency)}</strong><span>{book.stock > 0 ? `${book.stock} en stock` : 'Agotado'}</span></Box>
                <AddOutlined className="product-add" />
              </Paper>
            ))}
          </Box>
        </Box>

        <Paper elevation={0} className="cart-panel">
          <Box className="cart-heading"><Box><Typography component="h2">Venta actual</Typography><Typography>{itemCount} {itemCount === 1 ? 'artículo' : 'artículos'}</Typography></Box><LocalOfferOutlined /></Box>
          <Divider />
          <Box className="cart-lines">
            {!cart.length && <Box className="cart-empty"><span className="cart-empty-icon"><LocalOfferOutlined /></span><strong>La cesta está vacía</strong><span>Busca un libro para empezar la venta</span></Box>}
            {cart.map(({ book, quantity }) => (
              <Box className="cart-line" key={book.id}>
                <Box className="cart-line-copy"><strong>{book.title}</strong><span>{formatMoney(grossCents(book, config?.prices_include_tax ?? true) / 100, currency)} / unidad</span></Box>
                <Box className="quantity-control">
                  <IconButton aria-label={`Quitar una unidad de ${book.title}`} size="small" onClick={() => changeQuantity(book.id, -1)}><RemoveOutlined fontSize="small" /></IconButton>
                  <span>{quantity}</span>
                  <IconButton aria-label={`Añadir una unidad de ${book.title}`} size="small" disabled={quantity >= book.stock} onClick={() => changeQuantity(book.id, 1)}><AddOutlined fontSize="small" /></IconButton>
                </Box>
                <strong className="line-total">{formatMoney(grossCents(book, config?.prices_include_tax ?? true) * quantity / 100, currency)}</strong>
                <IconButton aria-label={`Eliminar ${book.title}`} size="small" onClick={() => changeQuantity(book.id, -quantity)}><DeleteOutline fontSize="small" /></IconButton>
              </Box>
            ))}
          </Box>
          <Box className="payment-area">
            <Divider />
            {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
            <Box className="total-row"><span>Total</span><strong>{formatMoney(totalCents / 100, currency)}</strong></Box>
            {splitPayment ? <>
              <Button className="print-button" onClick={() => { requestKey.current = null; setSplitPayment(false) }}>Volver a un método</Button>
              <Box className="split-payment-fields">
                <TextField label="Importe en efectivo" size="small" type="number" inputProps={{ min: 0, step: '0.01' }} value={cashAmount} onChange={(event) => { requestKey.current = null; setCashAmount(event.target.value) }} />
                <TextField label="Importe con tarjeta" size="small" type="number" inputProps={{ min: 0, step: '0.01' }} value={cardAmount} onChange={(event) => { requestKey.current = null; setCardAmount(event.target.value) }} />
                {cents(cashAmount || '0') > 0 && <TextField label="Efectivo recibido" size="small" type="number" inputProps={{ min: cashAmount, step: '0.01' }} value={cashReceived || cashAmount} onChange={(event) => { requestKey.current = null; setCashReceived(event.target.value) }} />}
              </Box>
              {!splitIsValid && <Typography className="payment-warning">Reparte el importe exacto entre los métodos.</Typography>}
            </> : <>
              <Box className="payment-methods" role="group" aria-label="Método de pago">
                <Button className={method === 'cash' ? 'payment-selected' : ''} onClick={() => { requestKey.current = null; setMethod('cash') }} startIcon={<PaymentsOutlined />}>Efectivo</Button>
                <Button className={method === 'card' ? 'payment-selected' : ''} onClick={() => { requestKey.current = null; setMethod('card') }} startIcon={<CreditCardOutlined />}>Tarjeta</Button>
              </Box>
              {method === 'cash' && cart.length > 0 && <TextField label="Efectivo recibido" size="small" type="number" inputProps={{ min: total, step: '0.01' }} value={cashReceived || total} onChange={(event) => { requestKey.current = null; setCashReceived(event.target.value) }} />}
              <Button className="print-button" onClick={() => { requestKey.current = null; setCashAmount(total); setCardAmount('0.00'); setSplitPayment(true) }}>Dividir pago</Button>
            </>}
            <Button variant="contained" size="large" fullWidth disabled={busy || cart.length === 0 || (splitPayment && !splitIsValid)} onClick={() => void handleCheckout()}>
              {busy ? <CircularProgress size={22} color="inherit" /> : 'Cobrar'}
            </Button>
            {receipt && <Button className="print-button" fullWidth startIcon={<PrintOutlined />} onClick={() => window.print()}>Imprimir ticket {receipt.receipt_number}</Button>}
          </Box>
        </Paper>
      </Box>
      {receipt && <Box className="ticket-print" aria-label={`Ticket ${receipt.receipt_number}`}>
        <div className="ticket-brand">Booker TPV <span>· Comprobante informativo</span></div>
        <div className="ticket-number">{receipt.receipt_number}</div>
        <div className="ticket-date">{new Date(receipt.created_at).toLocaleString('es-ES')}</div>
        <div className="ticket-items">{receipt.items.map((item) => <div className="ticket-line" key={item.id}><span>{item.quantity} × {item.title_snapshot}</span><span>{formatMoney(item.line_total, currency)}</span></div>)}</div>
        <div className="ticket-total"><span>Total</span><strong>{formatMoney(receipt.total, currency)}</strong></div>
        <div className="ticket-footer">Gracias por apoyar a tu librería.</div>
      </Box>}
    </Box>
  )
}