import { useEffect, useState } from 'react'
import { Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Paper, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material'
import ReceiptLongOutlined from '@mui/icons-material/ReceiptLongOutlined'
import { api } from './api'
import { formatMoney } from './format'
import type { Sale, User } from './types'

export default function SalesPage({ currency, user, onNotice }: { currency: string; user: User; onNotice: (message: string) => void }) {
  const [sales, setSales] = useState<Sale[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [selected, setSelected] = useState<Sale | null>(null)
  const [returning, setReturning] = useState(false)
  const [reason, setReason] = useState('')
  const [returnLines, setReturnLines] = useState<Record<string, { quantity: number; restock: boolean }>>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const canReturn = user.role !== 'cashier'

  async function refresh() {
    const result = await api.sales(page)
    setSales(result.items)
    setTotal(result.total)
  }
  useEffect(() => {
    api.sales(page).then((result) => { setSales(result.items); setTotal(result.total) })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'No se pudieron cargar las ventas'))
  }, [page])

  async function openSale(sale: Sale) {
    try { setSelected(await api.sale(sale.id)); setError('') }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo abrir el ticket') }
  }

  async function submitReturn() {
    if (!selected || !reason.trim()) return
    const items = selected.items.flatMap((item) => {
      const selection = returnLines[item.id]
      return selection?.quantity
        ? [{ sale_item_id: item.id, quantity: selection.quantity, restock: selection.restock }]
        : []
    })
    if (!items.length) return
    setBusy(true)
    try {
      const result = await api.returnSale(selected.id, reason, items)
      onNotice(`Devolución registrada · ${formatMoney(result.refund_total, currency)}`)
      setReturning(false)
      setSelected(null)
      setReason('')
      setReturnLines({})
      await refresh()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo registrar la devolución')
    } finally { setBusy(false) }
  }

  return (
    <Box className="section-page">
      <Box className="page-heading"><Box><Typography component="h1">Ventas</Typography><Typography className="page-subtitle">Tickets recientes y devoluciones</Typography></Box><span className="records-count">{total} tickets</span></Box>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <Paper elevation={0} className="table-frame">
        <Table aria-label="Ventas recientes">
          <TableHead><TableRow><TableCell>TICKET</TableCell><TableCell>FECHA</TableCell><TableCell>ARTÍCULOS</TableCell><TableCell>ESTADO</TableCell><TableCell align="right">TOTAL</TableCell></TableRow></TableHead>
          <TableBody>
            {sales.map((sale) => <TableRow key={sale.id} hover onClick={() => void openSale(sale)} className="clickable-row">
              <TableCell><strong>{sale.receipt_number}</strong></TableCell><TableCell>{new Date(sale.created_at).toLocaleString('es-ES')}</TableCell><TableCell>{sale.items.reduce((sum, item) => sum + item.quantity, 0)}</TableCell><TableCell><span className={`status-pill status-${sale.status}`}>{sale.status === 'completed' ? 'Completada' : sale.status === 'returned' ? 'Devuelta' : 'Parcial'}</span></TableCell><TableCell align="right">{formatMoney(sale.total, currency)}</TableCell>
            </TableRow>)}
            {!sales.length && <TableRow><TableCell colSpan={5} className="empty-table">Todavía no hay ventas registradas.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Paper>
      <Box className="pagination-bar">
        <Button disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Anterior</Button>
        <Typography>Página {page}</Typography>
        <Button disabled={page * 50 >= total} onClick={() => setPage((current) => current + 1)}>Siguiente</Button>
      </Box>
      <Dialog open={Boolean(selected)} onClose={() => setSelected(null)} fullWidth maxWidth="sm">
        <DialogTitle className="receipt-dialog-title"><ReceiptLongOutlined />{selected?.receipt_number}</DialogTitle>
        <DialogContent>
          {selected && <>
            <Typography className="receipt-date">{new Date(selected.created_at).toLocaleString('es-ES')}</Typography>
            {selected.items.map((item) => <Box className="receipt-line" key={item.id}><span>{item.quantity} × {item.title_snapshot}</span><strong>{formatMoney(item.line_total, currency)}</strong></Box>)}
            <Box className="receipt-total"><span>Total</span><strong>{formatMoney(selected.total, currency)}</strong></Box>
            <Typography className="receipt-date">Pago: {selected.payments.map((payment) => payment.method === 'cash' ? 'Efectivo' : payment.method === 'card' ? 'Tarjeta' : 'Otro').join(', ')}</Typography>
            {returning && <Box className="return-form">
              <Alert severity="warning">Selecciona las unidades que devuelve el cliente y si cada línea vuelve a estar disponible.</Alert>
              {selected.items.map((item) => {
                const available = item.quantity - item.returned_quantity
                const selection = returnLines[item.id] ?? { quantity: 0, restock: true }
                return <Box className="return-line-select" key={item.id}>
                  <TextField
                    type="number"
                    label={`${item.title_snapshot} · disponibles ${available}`}
                    value={selection.quantity}
                    disabled={available < 1}
                    inputProps={{ min: 0, max: available, step: 1 }}
                    onChange={(event) => setReturnLines((current) => ({
                      ...current,
                      [item.id]: { ...selection, quantity: Math.min(available, Math.max(0, Number(event.target.value))) },
                    }))}
                  />
                  <FormControlLabel
                    control={<Checkbox checked={selection.restock} disabled={available < 1} onChange={(event) => setReturnLines((current) => ({
                      ...current,
                      [item.id]: { ...selection, restock: event.target.checked },
                    }))} />}
                    label="Reponer en stock"
                  />
                </Box>
              })}
              <TextField required fullWidth label="Motivo de devolución" value={reason} onChange={(event) => setReason(event.target.value)} multiline minRows={2} />
              {error && <Alert severity="error">{error}</Alert>}
            </Box>}
          </>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setSelected(null); setReturning(false); setError('') }}>Cerrar</Button>
          {canReturn && selected && selected.status !== 'returned' && !returning && <Button color="warning" onClick={() => {
            setReturnLines(Object.fromEntries(selected.items.map((item) => [item.id, { quantity: 0, restock: true }])))
            setReason('')
            setReturning(true)
          }}>Registrar devolución</Button>}
          {returning && <Button variant="contained" color="warning" disabled={busy || reason.trim().length < 2 || !Object.values(returnLines).some((item) => item.quantity > 0)} onClick={() => void submitReturn()}>{busy ? 'Registrando…' : 'Confirmar devolución'}</Button>}
        </DialogActions>
      </Dialog>
    </Box>
  )
}