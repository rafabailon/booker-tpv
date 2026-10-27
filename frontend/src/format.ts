export function formatMoney(value: number | string, currency: string): string {
  return new Intl.NumberFormat('es-ES', { style: 'currency', currency }).format(Number(value))
}