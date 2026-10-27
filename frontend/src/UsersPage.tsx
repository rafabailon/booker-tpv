import { useEffect, useState, type FormEvent } from 'react'
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Paper, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material'
import AddOutlined from '@mui/icons-material/AddOutlined'
import PasswordOutlined from '@mui/icons-material/PasswordOutlined'
import { api } from './api'
import type { Role, User } from './types'

const roleName: Record<Role, string> = { admin: 'Administrador', supervisor: 'Supervisor', cashier: 'Cajero' }

export default function UsersPage({ currentUser, onNotice }: { currentUser: User; onNotice: (message: string) => void }) {
  const [users, setUsers] = useState<User[]>([])
  const [open, setOpen] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [passwordUser, setPasswordUser] = useState<User | null>(null)
  const [role, setRole] = useState<Role>('cashier')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function refresh() { setUsers(await api.users()) }
  useEffect(() => {
    api.users().then(setUsers).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los usuarios'))
  }, [])

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.createUser(username.trim(), password, role)
      setOpen(false)
      setUsername('')
      setPassword('')
      await refresh()
      onNotice('Usuario creado')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo crear el usuario')
    } finally { setBusy(false) }
  }

  async function changeRole(user: User, nextRole: Role) {
    try {
      await api.updateUser(user.id, { role: nextRole })
      await refresh()
      onNotice(`Rol de ${user.username} actualizado`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo cambiar el rol')
    }
  }

  async function toggleActive(user: User) {
    try {
      await api.updateUser(user.id, { is_active: !user.is_active })
      await refresh()
      onNotice(user.is_active ? 'Usuario desactivado' : 'Usuario activado')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo cambiar el estado')
    }
  }

  async function resetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!passwordUser) return
    setBusy(true)
    setError('')
    try {
      await api.updateUser(passwordUser.id, { password })
      setPasswordUser(null)
      setPassword('')
      onNotice(`Contraseña de ${passwordUser.username} restablecida`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo restablecer la contraseña')
    } finally { setBusy(false) }
  }

  return (
    <Box className="section-page">
      <Box className="page-heading"><Box><Typography component="h1">Usuarios</Typography><Typography className="page-subtitle">Accesos y roles del personal</Typography></Box><Button variant="contained" startIcon={<AddOutlined />} onClick={() => { setError(''); setOpen(true) }}>Añadir usuario</Button></Box>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <Paper elevation={0} className="table-frame">
        <Table aria-label="Usuarios del sistema"><TableHead><TableRow><TableCell>USUARIO</TableCell><TableCell>ROL</TableCell><TableCell>ALTA</TableCell><TableCell>ESTADO</TableCell><TableCell align="right">ACCIONES</TableCell></TableRow></TableHead>
          <TableBody>{users.map((user) => <TableRow key={user.id}>
            <TableCell><strong>{user.username}</strong></TableCell>
            <TableCell><TextField select size="small" value={user.role} disabled={user.id === currentUser.id} inputProps={{ 'aria-label': `Rol de ${user.username}` }} onChange={(event) => void changeRole(user, event.target.value as Role)}>{Object.entries(roleName).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}</TextField></TableCell>
            <TableCell>{user.created_at ? new Date(user.created_at).toLocaleDateString('es-ES') : '—'}</TableCell>
            <TableCell><span className={`status-pill ${user.is_active ? '' : 'status-returned'}`}>{user.is_active ? 'Activo' : 'Inactivo'}</span></TableCell>
            <TableCell align="right"><Button size="small" aria-label={`Restablecer contraseña de ${user.username}`} title="Restablecer contraseña" onClick={() => { setPassword(''); setPasswordUser(user) }} startIcon={<PasswordOutlined />} /><Button size="small" disabled={user.id === currentUser.id} onClick={() => void toggleActive(user)}>{user.is_active ? 'Desactivar' : 'Activar'}</Button></TableCell>
          </TableRow>)}
            {!users.length && <TableRow><TableCell colSpan={5} className="empty-table">No hay usuarios.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Paper>
      <Dialog open={open} onClose={() => !busy && setOpen(false)} fullWidth maxWidth="xs">
        <Box component="form" onSubmit={(event) => void create(event)}>
          <DialogTitle>Añadir usuario</DialogTitle>
          <DialogContent className="book-form">
            {error && <Alert severity="error">{error}</Alert>}
            <TextField required label="Usuario" autoComplete="off" inputProps={{ minLength: 2, pattern: '[A-Za-z0-9_.-]+' }} value={username} onChange={(event) => setUsername(event.target.value)} />
            <TextField required label="Contraseña inicial" type="password" autoComplete="new-password" inputProps={{ minLength: 12 }} helperText="Mínimo 12 caracteres" value={password} onChange={(event) => setPassword(event.target.value)} />
            <TextField select label="Rol" value={role} onChange={(event) => setRole(event.target.value as Role)}>{Object.entries(roleName).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}</TextField>
          </DialogContent>
          <DialogActions><Button onClick={() => setOpen(false)} disabled={busy}>Cancelar</Button><Button type="submit" variant="contained" disabled={busy}>{busy ? 'Creando…' : 'Crear usuario'}</Button></DialogActions>
        </Box>
      </Dialog>
      <Dialog open={Boolean(passwordUser)} onClose={() => !busy && setPasswordUser(null)} fullWidth maxWidth="xs">
        <Box component="form" onSubmit={(event) => void resetPassword(event)}>
          <DialogTitle>Restablecer contraseña</DialogTitle>
          <DialogContent className="book-form">
            {passwordUser && <Typography>Cuenta: {passwordUser.username}</Typography>}
            {error && <Alert severity="error">{error}</Alert>}
            <TextField required label="Nueva contraseña" type="password" autoComplete="new-password" inputProps={{ minLength: 12 }} helperText="Mínimo 12 caracteres" value={password} onChange={(event) => setPassword(event.target.value)} />
          </DialogContent>
          <DialogActions><Button onClick={() => setPasswordUser(null)} disabled={busy}>Cancelar</Button><Button type="submit" variant="contained" disabled={busy}>{busy ? 'Guardando…' : 'Guardar contraseña'}</Button></DialogActions>
        </Box>
      </Dialog>
    </Box>
  )
}