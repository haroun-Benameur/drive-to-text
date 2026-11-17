/**
 * Format a byte count as a human-readable string.
 *
 * @example
 * formatBytes(null)        // "unknown"
 * formatBytes(0)           // "0 B"
 * formatBytes(1536)        // "1.5 KB"
 * formatBytes(1572864)     // "1.5 MB"
 */
export function formatBytes(n: number | null): string {
  if (n === null) return 'unknown'
  if (n === 0) return '0 B'

  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const exp = Math.min(Math.floor(Math.log2(n) / 10), units.length - 1)
  const value = n / Math.pow(1024, exp)

  // Show one decimal place for KB and above, none for bytes.
  const formatted = exp === 0 ? String(value) : value.toFixed(1)
  return `${formatted} ${units[exp]}`
}
