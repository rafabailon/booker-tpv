import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Login from './Login'
import { api } from './api'

vi.mock('./api', () => ({
  api: {
    login: vi.fn(),
  },
}))

const user = { id: 'user-1', username: 'admin', role: 'admin' as const }

describe('Login', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('submits credentials and reports the authenticated user', async () => {
    vi.mocked(api.login).mockResolvedValue(user)
    const onAuthenticated = vi.fn()
    render(<Login onAuthenticated={onAuthenticated} />)

    fireEvent.change(screen.getByLabelText(/Usuario/), { target: { value: 'admin' } })
    fireEvent.change(screen.getByLabelText(/Contraseña/), { target: { value: 'secret-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar en caja' }))

    await waitFor(() => expect(api.login).toHaveBeenCalledWith('admin', 'secret-password'))
    expect(onAuthenticated).toHaveBeenCalledWith(user)
  })

  it('shows the server error and keeps the form available', async () => {
    vi.mocked(api.login).mockRejectedValue(new Error('Usuario o contraseña incorrectos'))
    render(<Login onAuthenticated={vi.fn()} />)

    fireEvent.change(screen.getByLabelText(/Usuario/), { target: { value: 'admin' } })
    fireEvent.change(screen.getByLabelText(/Contraseña/), { target: { value: 'wrong-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar en caja' }))

    expect(await screen.findByText('Usuario o contraseña incorrectos')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Entrar en caja' })).toBeEnabled()
  })

  it('shows a generic message when the failure is not an Error instance', async () => {
    vi.mocked(api.login).mockRejectedValue('network down')
    render(<Login onAuthenticated={vi.fn()} />)

    fireEvent.change(screen.getByLabelText(/Usuario/), { target: { value: 'admin' } })
    fireEvent.change(screen.getByLabelText(/Contraseña/), { target: { value: 'secret-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar en caja' }))

    expect(await screen.findByText('No se pudo iniciar sesión')).toBeInTheDocument()
  })
})
