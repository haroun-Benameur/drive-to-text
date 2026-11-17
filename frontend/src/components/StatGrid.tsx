import type { Batch, DriveFile } from '../types.ts'

interface Props {
  files: DriveFile[]
  selectedIds: Set<string>
  batch: Batch | null
}

interface StatCardProps {
  label: string
  value: number
  variant?: string
}

function StatCard({ label, value, variant }: StatCardProps) {
  return (
    <div className={`stat-card${variant ? ` stat-card--${variant}` : ''}`}>
      <span className="stat-card__label">{label}</span>
      <span className="stat-card__value">{value}</span>
    </div>
  )
}

export function StatGrid({ files, selectedIds, batch }: Props) {
  const total    = files.length
  const selected = selectedIds.size
  const done     = batch?.counts.done    ?? 0
  const failed   = batch?.counts.failed  ?? 0

  return (
    <div className="stat-grid" role="region" aria-label="Batch statistics">
      <StatCard label="Total Files"   value={total}    />
      <StatCard label="Selected"      value={selected} variant="sel" />
      <StatCard label="Completed"     value={done}     variant="done" />
      <StatCard label="Failed"        value={failed}   variant="failed" />
    </div>
  )
}
