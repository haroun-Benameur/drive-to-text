import type { FileStatus } from '../types.ts'

const CONFIG: Record<FileStatus, { icon: string; label: string }> = {
  pending:    { icon: '○', label: 'Pending' },
  processing: { icon: '◎', label: 'Processing' },
  done:       { icon: '✓', label: 'Done' },
  failed:     { icon: '✕', label: 'Failed' },
}

interface Props {
  status: FileStatus
}

export function StatusBadge({ status }: Props) {
  const { icon, label } = CONFIG[status]
  return (
    <span className={`badge badge--${status}`} aria-label={label}>
      <span aria-hidden="true">{icon}</span>
      {label}
    </span>
  )
}
