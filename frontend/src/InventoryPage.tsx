import { useEffect, useState, type FormEvent } from 'react'
import { Alert, Box, Button, MenuItem, Paper, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material'
import { api } from './api'
import type { Book, StockMovement } from './types'

export default function InventoryPage({ onNotice }: { onNotice: (message: string) => void }) {
  const [books, setBooks] = useState<Book[]>([])
  const [movements, setMovements] = useState<StockMovement[]>([])
  const [bookId, setBookId] = useState('')
  const [delta, setDelta] = useState('1')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function refresh() {
    const [page, latest] = await Promise.all([api.books(new URLSearchParams({ page_size: '100' })), api.movements()])
    setBooks(page.items)
    setMovements(latest)
  }
  useEffect(() => {
    Promise.all([api.books(new URLSearchParams({ page_size: '100' })), api.movements()])
      .then(([page, latest]) => { setBooks(page.items); setMovements(latest) })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'No se pudo cargar el inventario'))
  }, [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.adjustStock(bookId, Number(delta), reason.trim())
      setReason('')
      await refresh()
      onNotice('Ajuste de stock registrado')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo ajustar el inventario')
    } finally { setBusy(false) }
  }

  return (
    <Box className="section-page">
      <Box className="page-heading"><Box><Typography component="h1">Inventario</Typography><Typography className="page-subtitle">Existencias y movimientos registrados</Typography></Box></Box>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <Paper component="form" elevation={0} className="adjustment-bar" onSubmit={(event) => void submit(event)}>
        <Typography component="h2">Ajustar existencias</Typography>
        <TextField select required label="Libro" value={bookId} onChange={(event) => setBookId(event.target.value)} className="adjust-book-select">
          {books.map((book) => <MenuItem key={book.id} value={book.id}>{book.title} · stock {book.stock}</MenuItem>)}
        </TextField>
        <TextField required type="number" label="Cambio" value={delta} onChange={(event) => setDelta(event.target.value)} inputProps={{ step: 1 }} className="adjust-quantity" />
        <TextField required label="Motivo" value={reason} onChange={(event) => setReason(event.target.value)} className="adjust-reason" />
        <Button type="submit" variant="contained" disabled={busy || !bookId}>{busy ? 'Guardando…' : 'Registrar ajuste'}</Button>
      </Paper>
      <Box className="results-heading"><Typography component="h2">Movimientos recientes</Typography><Typography>{movements.length}</Typography></Box>
      <Paper elevation={0} className="table-frame">
        <Table aria-label="Movimientos de inventario"><TableHead><TableRow><TableCell>FECHA</TableCell><TableCell>LIBRO</TableCell><TableCell>MOTIVO</TableCell><TableCell align="right">CAMBIO</TableCell></TableRow></TableHead>
          <TableBody>{movements.map((movement) => <TableRow key={movement.id}><TableCell>{new Date(movement.created_at).toLocaleString('es-ES')}</TableCell><TableCell>{books.find((book) => book.id === movement.book_id)?.title ?? 'Libro archivado'}</TableCell><TableCell>{movement.notes || (movement.reason === 'sale' ? 'Venta' : movement.reason === 'return' ? 'Devolución' : 'Ajuste')}</TableCell><TableCell align="right" className={movement.quantity_delta > 0 ? 'quantity-positive' : 'quantity-negative'}>{movement.quantity_delta > 0 ? '+' : ''}{movement.quantity_delta}</TableCell></TableRow>)}
            {!movements.length && <TableRow><TableCell colSpan={4} className="empty-table">No hay movimientos todavía.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  )
}