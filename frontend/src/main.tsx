import React from 'react'
import ReactDOM from 'react-dom/client'
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import '@fontsource-variable/dm-sans'
import App from './App'
import './styles.css'

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#275f4d', dark: '#194739', contrastText: '#ffffff' },
    secondary: { main: '#dc794d' },
    background: { default: '#f3f5f0', paper: '#ffffff' },
    text: { primary: '#202b26', secondary: '#69756e' },
    success: { main: '#32815e' },
    warning: { main: '#ba6c2c' },
  },
  typography: {
    fontFamily: 'DM Sans Variable, sans-serif',
    button: { textTransform: 'none', fontWeight: 650 },
    h1: { fontSize: '1.65rem', fontWeight: 720 },
    h2: { fontSize: '1.2rem', fontWeight: 700 },
  },
  shape: { borderRadius: 8 },
  components: {
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiTableCell: { styleOverrides: { head: { fontWeight: 700, color: '#69756e' } } },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </React.StrictMode>,
)