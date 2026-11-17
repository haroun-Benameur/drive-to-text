import { exportUrl } from '../api.ts'
import type { Batch } from '../types.ts'

const TERMINAL = new Set(['completed', 'completed_with_errors'])

interface Props {
  batch: Batch
}

export function ExportButton({ batch }: Props) {
  const enabled = TERMINAL.has(batch.status)
  const href = exportUrl(batch.id)

  if (!enabled) {
    return (
      <button className="btn btn--outline" disabled aria-disabled="true">
        Export JSON
      </button>
    )
  }

  return (
    <a
      className="btn btn--outline"
      href={href}
      download={`extraction-${batch.id}.json`}
    >
      Export JSON
    </a>
  )
}
