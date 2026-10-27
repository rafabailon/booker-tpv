import { useState, type FormEvent } from 'react'
import { Alert, Box, Button, CircularProgress, TextField, Typography } from '@mui/material'
import MenuBookOutlined from '@mui/icons-material/MenuBookOutlined'
import { api } from './api'
import type { User } from './types'

export default function Login({ onAuthenticated }: { onAuthenticated: (user: User) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      onAuthenticated(await api.login(username, password))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo iniciar sesión')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Box className="login-page">
      <Box className="login-aside">
        <div className="login-aside-top"><MenuBookOutlined /><span>Booker TPV</span></div>
        <div className="login-editorial">
          <span className="eyebrow">LIBRERÍA · SISTEMA DE CAJA</span>
          <Typography component="h1">Cada historia,<br />en su sitio.</Typography>
          <p>Gestión de mostrador e inventario.</p>
          <div className="book-spines" aria-hidden="true"><i /><i /><i /><i /><i /><i /></div>
        </div>
        <span className="login-edition">PUESTO DE VENTA · EDICIÓN 01</span>
      </Box>
      <Box component="form" onSubmit={submit} className="login-form">
        <span className="eyebrow">ACCESO AL MOSTRADOR</span>
        <Typography component="h2">Iniciar sesión</Typography>
        <Typography className="login-hint">Introduce tus credenciales para abrir la caja.</Typography>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField autoFocus required fullWidth label="Usuario" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        <TextField required fullWidth label="Contraseña" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
        <Button type="submit" variant="contained" size="large" disabled={busy} endIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}>Entrar en caja</Button>
      </Box>
    </Box>
  )
}