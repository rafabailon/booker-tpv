import { useEffect, useState } from 'react'
import { Alert, Box, Button, Paper, Typography } from '@mui/material'
import AutoStoriesOutlined from '@mui/icons-material/AutoStoriesOutlined'
import DownloadOutlined from '@mui/icons-material/DownloadOutlined'
import EuroOutlined from '@mui/icons-material/EuroOutlined'
import WarningAmberOutlined from '@mui/icons-material/WarningAmberOutlined'
import { api } from './api'
import { formatMoney } from './format'
import type { Book, DailyReport } from './types'

export default function ReportsPage({ currency, threshold, onNotice }: { currency: string; threshold: number; onNotice: (message: string) => void }) {
  const [report, setReport] = useState<DailyReport | null>(null)
  const [lowStock, setLowStock] = useState<Book[]>([])
  const [error, setError] = useState('')
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    Promise.all([api.dailyReport(), api.lowStock(threshold)]).then(([daily, books]) => { setReport(daily); setLowStock(books) })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los informes'))
  }, [threshold])

  async function exportCsv() {
    setExporting(true)
    setError('')
    try {
      const { blob, filename } = await api.dailySalesCsv(report?.date)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 0)
      onNotice('Exportación CSV generada')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo exportar el informe')
    } finally {
      setExporting(false)
    }
  }

  return (
    <Box className="section-page">
      <Box className="page-heading">
        <Box><Typography component="h1">Informes</Typography><Typography className="page-subtitle">Resumen operativo · {report?.date ?? 'hoy'}</Typography></Box>
        <Button variant="outlined" startIcon={<DownloadOutlined />} disabled={exporting || !report} onClick={() => void exportCsv()}>{exporting ? 'Exportando…' : 'Exportar CSV'}</Button>
      </Box>
      {error && <Alert severity="error">{error}</Alert>}
      <Box className="report-grid">
        <Paper elevation={0} className="metric-panel"><span className="metric-icon green"><EuroOutlined /></span><span className="metric-label">VENTA NETA DEL DÍA</span><strong>{report ? formatMoney(report.total, currency) : '—'}</strong><span className="metric-footnote">Bruto {report ? formatMoney(report.sold_total, currency) : '—'} · Devuelto {report ? formatMoney(report.refunded_total, currency) : '—'}</span></Paper>
        <Paper elevation={0} className="metric-panel"><span className="metric-icon orange"><AutoStoriesOutlined /></span><span className="metric-label">TICKETS</span><strong>{report?.sale_count ?? '—'}</strong><span className="metric-footnote">Ventas registradas hoy</span></Paper>
        <Paper elevation={0} className="metric-panel"><span className="metric-icon red"><WarningAmberOutlined /></span><span className="metric-label">STOCK BAJO</span><strong>{lowStock.length}</strong><span className="metric-footnote">Libros con {threshold} unidades o menos</span></Paper>
      </Box>
      <Box className="results-heading"><Typography component="h2">Reponer próximamente</Typography><Typography>umbral: {threshold} unidades</Typography></Box>
      <Box className="low-stock-list">{lowStock.map((book) => <Paper elevation={0} className="low-stock-row" key={book.id}><Box><strong>{book.title}</strong><span>{book.authors || 'Autor no indicado'}</span></Box><span className={`stock-pill ${book.stock < 1 ? 'stock-low' : ''}`}>{book.stock} uds.</span></Paper>)}{!lowStock.length && <span className="empty-table">No hay libros por debajo del umbral.</span>}</Box>
    </Box>
  )
}