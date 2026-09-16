/**
 * Utility: Format Date
 * Converts ISO date strings to human-readable format
 */
export function formatDate(dateString) {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Utility: Format Duration
 * Converts seconds to human-readable duration (e.g., "1h 23m 45s")
 */
export function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '0m'

  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60

  const parts = []
  if (hours > 0) parts.push(`${hours}h`)
  if (minutes > 0) parts.push(`${minutes}m`)
  if (secs > 0 && hours === 0 && minutes === 0) parts.push(`${secs}s`)

  return parts.join(' ') || '0m'
}

/**
 * Utility: Truncate Text
 * Truncates text to a max length and adds ellipsis
 */
export function truncateText(text, maxLength = 100) {
  if (!text || text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}
