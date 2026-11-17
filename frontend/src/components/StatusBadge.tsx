import type { FileStatus } from '../types.ts'

const LABELS: Record<FileStatus, string> = {
  pending:    'Pending',
  processing: 'Processing',
  done:       'Done',
  failed:     'Failed',
}

interface Props {
  status: FileStatus
}

export function StatusBadge({ status }: Props) {
  return (
    <span className={`badge badge--status badge--${status}`}>
      {LABELS[status]}
    </span>
  )
}
