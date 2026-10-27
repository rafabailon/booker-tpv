import { useEffect, useState } from 'react'
import { Alert, AppBar, Box, Button, CircularProgress, Drawer, IconButton, Snackbar, Toolbar, Typography } from '@mui/material'
import AssessmentOutlined from '@mui/icons-material/AssessmentOutlined'
import BookOutlined from '@mui/icons-material/BookOutlined'
import Inventory2Outlined from '@mui/icons-material/Inventory2Outlined'
import LogoutOutlined from '@mui/icons-material/LogoutOutlined'
import PointOfSaleOutlined from '@mui/icons-material/PointOfSaleOutlined'
import ReceiptLongOutlined from '@mui/icons-material/ReceiptLongOutlined'
import MenuBookOutlined from '@mui/icons-material/MenuBookOutlined'
import GroupsOutlined from '@mui/icons-material/GroupsOutlined'
import { api } from './api'
import type { StoreConfig, User } from './types'
import Login from './Login'
import PointOfSale from './PointOfSale'
import BooksPage from './BooksPage'
import SalesPage from './SalesPage'
import InventoryPage from './InventoryPage'
import ReportsPage from './ReportsPage'
import UsersPage from './UsersPage'

type View = 'pos' | 'books' | 'sales' | 'inventory' | 'reports' | 'users'

const navigation: Array<{ id: View; label: string; icon: typeof PointOfSaleOutlined; managerOnly?: boolean; adminOnly?: boolean }> = [
  { id: 'pos', label: 'Caja', icon: PointOfSaleOutlined },
  { id: 'books', label: 'Catálogo', icon: BookOutlined },
  { id: 'sales', label: 'Ventas', icon: ReceiptLongOutlined },
  { id: 'inventory', label: 'Inventario', icon: Inventory2Outlined, managerOnly: true },
  { id: 'reports', label: 'Informes', icon: AssessmentOutlined, managerOnly: true },
  { id: 'users', label: 'Usuarios', icon: GroupsOutlined, adminOnly: true },
]

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [storeConfig, setStoreConfig] = useState<StoreConfig>({ currency: 'EUR', prices_include_tax: true, low_stock_threshold: 3 })
  const [view, setView] = useState<View>('pos')
  const [starting, setStarting] = useState(true)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let cancelled = false
    api.me().then((current) => !cancelled && setUser(current)).catch(() => !cancelled && setUser(null)).finally(() => !cancelled && setStarting(false))
    api.publicConfig().then((config) => !cancelled && setStoreConfig(config)).catch(() => undefined)
    return () => { cancelled = true }
  }, [])

  async function signOut() {
    try {
      await api.logout()
    } finally {
      setUser(null)
    }
  }

  if (starting) return <Box className="startup"><CircularProgress size={28} /></Box>
  if (!user) return <Login onAuthenticated={setUser} />

  const isManager = user.role !== 'cashier'
  const currentLabel = navigation.find((item) => item.id === view)?.label ?? 'Caja'

  return (
    <Box className="app-shell">
      <Drawer variant="permanent" className="sidebar" PaperProps={{ className: 'sidebar-paper' }}>
        <Box className="brand-lockup">
          <Box className="brand-mark"><MenuBookOutlined /></Box>
          <Box><Typography className="brand-name">Booker<span> TPV</span></Typography><Typography className="brand-caption">LIBRERÍA · MOSTRADOR</Typography></Box>
        </Box>
        <Typography className="nav-caption">OPERACIONES</Typography>
        <Box component="nav" className="nav-list" aria-label="Navegación principal">
          {navigation.filter((item) => (!item.managerOnly || isManager) && (!item.adminOnly || user.role === 'admin')).map(({ id, label, icon: Icon }) => (
            <Button key={id} aria-label={label} title={label} className={`nav-item ${view === id ? 'selected' : ''}`} onClick={() => setView(id)} startIcon={<Icon />}>
              {label}
            </Button>
          ))}
        </Box>
        <Box className="sidebar-bottom">
          <span className="connection-dot" />
          <Box><Typography className="connection-label">Sistema conectado</Typography><Typography className="user-caption">{user.username} · {user.role}</Typography></Box>
        </Box>
      </Drawer>

      <Box component="main" className="main-column">
        <AppBar position="sticky" elevation={0} className="topbar">
          <Toolbar className="topbar-content">
            <Box className="mobile-brand"><MenuBookOutlined /><strong>Booker TPV</strong></Box>
            <Typography className="breadcrumb">{currentLabel}</Typography>
            <Box className="topbar-actions">
              <Typography className="topbar-user">{user.username}</Typography>
              <IconButton aria-label="Cerrar sesión" title="Cerrar sesión" onClick={signOut} size="small"><LogoutOutlined /></IconButton>
            </Box>
          </Toolbar>
        </AppBar>
        <Box className="workspace">
          {view === 'pos' && <PointOfSale config={storeConfig} onNotice={setNotice} />}
          {view === 'books' && <BooksPage config={storeConfig} user={user} onNotice={setNotice} />}
          {view === 'sales' && <SalesPage currency={storeConfig.currency} user={user} onNotice={setNotice} />}
          {view === 'inventory' && isManager && <InventoryPage onNotice={setNotice} />}
          {view === 'reports' && isManager && <ReportsPage currency={storeConfig.currency} threshold={storeConfig.low_stock_threshold} onNotice={setNotice} />}
          {view === 'users' && user.role === 'admin' && <UsersPage currentUser={user} onNotice={setNotice} />}
        </Box>
      </Box>
      <Snackbar open={Boolean(notice)} autoHideDuration={4500} onClose={() => setNotice('')} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert onClose={() => setNotice('')} severity="success" variant="filled">{notice}</Alert>
      </Snackbar>
    </Box>
  )
}