import { format, formatDistanceToNow, parseISO } from 'date-fns'

export function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

export function formatDate(d, fmt = 'MMM d, yyyy') {
  if (!d) return '?'
  try { return format(typeof d === 'string' ? parseISO(d) : d, fmt) }
  catch { return d }
}

export function timeAgo(d) {
  if (!d) return ''
  try { return formatDistanceToNow(typeof d === 'string' ? parseISO(d) : d, { addSuffix: true }) }
  catch { return '' }
}

export function formatCurrency(n) {
  if (n == null) return '?'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)
}

export function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

export function downloadBlob(response, fallbackName) {
  const disposition = response?.headers?.['content-disposition'] || ''
  const match = disposition.match(/filename="?([^";]+)"?/i)
  const filename = match?.[1] || fallbackName
  const url = window.URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export const STATUS_COLOR = {
  planning: 'var(--status-planning)',
  in_progress: 'var(--status-in-progress)',
  completed: 'var(--status-completed)',
  on_hold: 'var(--status-on-hold)',
  review: 'var(--status-review)',
  pending: 'var(--status-pending)',
}

export const PRIORITY_COLOR = {
  low: 'var(--priority-low)',
  medium: 'var(--priority-medium)',
  high: 'var(--priority-high)',
  critical: 'var(--danger)',
}

export const STATUS_LABEL = {
  planning: 'Planning',
  in_progress: 'In Progress',
  pending: 'Pending',
  on_hold: 'On Hold',
  completed: 'Completed',

}

export const PRIORITY_LABEL = { low: 'Low', medium: 'Medium', high: 'High', critical: 'Critical' }

export const ROLE_LABEL = { admin: 'Admin', manager: 'Manager', resource: 'Resource', client: 'Client' }

export function getInitials(name = '') {
  return name.split(' ').map(p => p[0]).join('').toUpperCase().slice(0, 2)
}

export function extractError(err) {
  const data = err?.response?.data
  if (!data) return 'An unexpected error occurred.'
  if (typeof data.message === 'string') return data.message
  if (typeof data.detail === 'string') return data.detail
  if (typeof data === 'string') return data
  const errs = data.errors
  if (errs && typeof errs === 'object') {
    return Object.values(errs).flat().join(' ')
  }
  return 'An error occurred.'
}
