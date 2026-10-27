import { useEffect, useState, type FormEvent } from 'react'
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, Paper, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material'
import AddOutlined from '@mui/icons-material/AddOutlined'
import EditOutlined from '@mui/icons-material/EditOutlined'
import SearchOutlined from '@mui/icons-material/SearchOutlined'
import { api } from './api'
import { formatMoney } from './format'
import type { Book, StoreConfig, User } from './types'

interface BookForm {
  isbn: string
  title: string
  authors: string
  publisher: string
  category: string
  price: string
  tax_rate: string
  stock: string
}

const emptyForm: BookForm = { isbn: '', title: '', authors: '', publisher: '', category: '', price: '', tax_rate: '0', stock: '0' }
export default function BooksPage({ config, user, onNotice }: { config: StoreConfig; user: User; onNotice: (message: string) => void }) {
  const [books, setBooks] = useState<Book[]>([])
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [dialog, setDialog] = useState(false)
  const [editing, setEditing] = useState<Book | null>(null)
  const [form, setForm] = useState<BookForm>(emptyForm)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const manager = user.role !== 'cashier'

  async function refresh() {
    const params = new URLSearchParams({ page: String(page), page_size: '50' })
    if (query.trim()) params.set('q', query.trim())
    const result = await api.books(params)
    setBooks(result.items)
    setTotal(result.total)
  }

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({ page: String(page), page_size: '50' })
      if (query.trim()) params.set('q', query.trim())
      api.books(params, controller.signal).then((result) => {
        if (!cancelled) {
          setBooks(result.items)
          setTotal(result.total)
        }
      }).catch((cause: unknown) => {
        if (!cancelled && !(cause instanceof Error && cause.name === 'AbortError')) {
          setError(cause instanceof Error ? cause.message : 'No se pudo cargar el catálogo')
        }
      })
    }, 160)
    return () => { cancelled = true; window.clearTimeout(timer); controller.abort() }
  }, [page, query])

  function openCreate() {
    setEditing(null)
    setForm(emptyForm)
    setError('')
    setDialog(true)
  }

  function openEdit(book: Book) {
    setEditing(book)
    setForm({ isbn: book.isbn ?? '', title: book.title, authors: book.authors, publisher: book.publisher ?? '', category: book.category ?? '', price: book.price, tax_rate: book.tax_rate, stock: String(book.stock) })
    setError('')
    setDialog(true)
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    const payload = {
      isbn: form.isbn.trim() || null,
      title: form.title.trim(),
      authors: form.authors.trim(),
      publisher: form.publisher.trim() || null,
      category: form.category.trim() || null,
      price: form.price,
      tax_rate: form.tax_rate,
    }
    try {
      if (editing) {
        await api.updateBook(editing.id, payload)
      } else {
        await api.createBook({ ...payload, stock: Number(form.stock) })
        setPage(1)
      }
      setDialog(false)
      if (editing || page === 1) await refresh()
      onNotice(editing ? 'Libro actualizado' : 'Libro añadido al catálogo')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo guardar el libro')
    } finally {
      setBusy(false)
    }
  }

  async function archive(book: Book) {
    if (!window.confirm(`¿Archivar «${book.title}»?`)) return
    try {
      await api.archiveBook(book.id)
      await refresh()
      onNotice('Libro archivado')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo archivar el libro')
    }
  }

  function field(name: keyof BookForm, value: string) {
    setForm((current) => ({ ...current, [name]: value }))
  }

  return (
    <Box className="section-page">
      <Box className="page-heading"><Box><Typography component="h1">Catálogo</Typography><Typography className="page-subtitle">Libros y disponibilidad en tienda</Typography></Box>{manager && <Button variant="contained" startIcon={<AddOutlined />} onClick={openCreate}>Añadir libro</Button>}</Box>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <TextField className="table-search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Buscar por título, autor o ISBN" InputProps={{ startAdornment: <SearchOutlined className="search-icon" /> }} />
      <Paper elevation={0} className="table-frame">
        <Table size="medium" aria-label="Catálogo de libros">
          <TableHead><TableRow><TableCell>LIBRO</TableCell><TableCell>ISBN</TableCell><TableCell>PRECIO</TableCell><TableCell>STOCK</TableCell>{manager && <TableCell align="right">ACCIONES</TableCell>}</TableRow></TableHead>
          <TableBody>
            {books.map((book) => <TableRow key={book.id} hover>
              <TableCell><strong className="table-title">{book.title}</strong><span className="table-secondary">{book.authors || 'Autor no indicado'}</span></TableCell>
              <TableCell>{book.isbn || '—'}</TableCell>
              <TableCell>{formatMoney(Number(book.price) * (config.prices_include_tax ? 1 : 1 + Number(book.tax_rate) / 100), config.currency)}</TableCell>
              <TableCell><span className={`stock-pill ${book.stock < 1 ? 'stock-low' : ''}`}>{book.stock}</span></TableCell>
              {manager && <TableCell align="right"><IconButton title="Editar libro" aria-label={`Editar ${book.title}`} onClick={() => openEdit(book)}><EditOutlined /></IconButton><Button size="small" color="inherit" onClick={() => void archive(book)}>Archivar</Button></TableCell>}
            </TableRow>)}
            {!books.length && <TableRow><TableCell colSpan={manager ? 5 : 4} className="empty-table">No hay libros para esta búsqueda.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Paper>
      <Box className="pagination-bar">
        <Typography>{total} libros</Typography>
        <Button disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Anterior</Button>
        <Typography>Página {page}</Typography>
        <Button disabled={page * 50 >= total} onClick={() => setPage((current) => current + 1)}>Siguiente</Button>
      </Box>
      <Dialog open={dialog} onClose={() => !busy && setDialog(false)} fullWidth maxWidth="sm">
        <Box component="form" onSubmit={(event) => void save(event)}>
          <DialogTitle>{editing ? 'Editar libro' : 'Añadir libro'}</DialogTitle>
          <DialogContent className="book-form">
            {error && <Alert severity="error">{error}</Alert>}
            <TextField required label="Título" value={form.title} onChange={(event) => field('title', event.target.value)} />
            <TextField label="Autor / autores" value={form.authors} onChange={(event) => field('authors', event.target.value)} />
            <TextField label="ISBN-10 o ISBN-13" value={form.isbn} onChange={(event) => field('isbn', event.target.value)} />
            <Box className="form-two-columns"><TextField required type="number" label={`Precio ${config.prices_include_tax ? 'con IVA incluido' : 'antes de IVA'} (${config.currency})`} inputProps={{ min: 0, step: '0.01' }} value={form.price} onChange={(event) => field('price', event.target.value)} /><TextField type="number" label="IVA (%)" inputProps={{ min: 0, max: 100, step: '0.01' }} value={form.tax_rate} onChange={(event) => field('tax_rate', event.target.value)} /></Box>
            {!editing && <TextField required type="number" label="Stock inicial" inputProps={{ min: 0, step: 1 }} value={form.stock} onChange={(event) => field('stock', event.target.value)} />}
            <Box className="form-two-columns"><TextField label="Editorial" value={form.publisher} onChange={(event) => field('publisher', event.target.value)} /><TextField label="Categoría" value={form.category} onChange={(event) => field('category', event.target.value)} /></Box>
          </DialogContent>
          <DialogActions><Button onClick={() => setDialog(false)} disabled={busy}>Cancelar</Button><Button type="submit" variant="contained" disabled={busy}>{busy ? 'Guardando…' : 'Guardar'}</Button></DialogActions>
        </Box>
      </Dialog>
    </Box>
  )
}