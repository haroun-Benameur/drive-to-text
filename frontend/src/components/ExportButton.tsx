import { exportUrl } from '../api.ts'
import type { Batch } from '../types.ts'

const TERMINAL = new Set(['completed', 'completed_with_errors'])

interface Props {
  batch: Batch
}

export function ExportButton({ batch }: Props) {
  const enabled = TERMINAL.has(batch.status)
  const href    = exportUrl(batch.id)

  if (!enabled) {
    return (
      <button className="btn btn--export" disabled aria-disabled="true">
        <span aria-hidden="true">⬇</span> Export JSON
      </button>
    )
  }

  return (
    <a
      className="btn btn--export"
      href={href}
      download={`extraction-${batch.id}.json`}
    >
      <span aria-hidden="true">⬇</span> Export JSON
    </a>
  )
}
