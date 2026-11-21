import { BookOpen, GraduationCap, Monitor } from 'lucide-react'

export const roomStyles = {
  'computer-lab': { icon: Monitor, color: '#0e956b', tone: 'green' },
  library: { icon: BookOpen, color: '#6675cf', tone: 'violet' },
  classroom: { icon: GraduationCap, color: '#e3a043', tone: 'amber' },
}

export const periods = [['today', 'Today'], ['7d', '7 days'], ['30d', '30 days']]
export const zone = 'Asia/Kolkata'

export function hasRoomData(analytics, entry) {
  return entry.has_data ?? analytics.daily.some(day => Object.hasOwn(day.rooms, entry.room_id))
}

export function showNumber(value, maximum = 2, minimum = 0) {
  return value == null ? '—' : new Intl.NumberFormat('en-IN', {
    maximumFractionDigits: maximum, minimumFractionDigits: minimum,
  }).format(value)
}

export function showCost(value) {
  return value == null ? '—' : `₹${showNumber(value, 2, 2)}`
}

export function formatTime(value, options = {}) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: zone, ...options,
  }).format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value))
}

export function shortTime(value) {
  return formatTime(value, { hour: 'numeric', minute: '2-digit', hour12: true })
}

export function fullTime(value) {
  return formatTime(value, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', second: '2-digit' })
}
