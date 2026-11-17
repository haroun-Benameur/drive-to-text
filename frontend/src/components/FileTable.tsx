import { useEffect, useRef } from 'react'
import { formatBytes } from '../utils.ts'
import { StatusBadge } from './StatusBadge.tsx'
import type { Batch, DriveFile } from '../types.ts'

interface Props {
  files: DriveFile[]
  selectedIds: Set<string>
  batch: Batch | null
  batchRunning: boolean
  onToggle: (id: string) => void
  onToggleAll: (select: boolean) => void
}

export function FileTable({
  files,
  selectedIds,
  batch,
  batchRunning,
  onToggle,
  onToggleAll,
}: Props) {
  const headerRef = useRef<HTMLInputElement>(null)

  const allSelected  = files.length > 0 && selectedIds.size === files.length
  const someSelected = selectedIds.size > 0 && !allSelected

  useEffect(() => {
    if (headerRef.current) {
      headerRef.current.indeterminate = someSelected
    }
  }, [someSelected])

  if (files.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon">📭</div>
        <p className="empty-state__text">No supported files (PDF, PNG, JPEG) found in this folder.</p>
      </div>
    )
  }

  const itemByFileId = new Map(batch?.items.map(it => [it.file_id, it]) ?? [])

  return (
    <div>
      <div className="table-toolbar">
        <p className="table-toolbar__info" aria-live="polite">
          {selectedIds.size} of {files.length} file{files.length !== 1 ? 's' : ''} selected
        </p>
      </div>

      <div className="table-scroll">
        <table className="file-table">
          <thead>
            <tr>
              <th className="file-table__check">
                <label className="sr-only" htmlFor="select-all-files">
                  Select all files
                </label>
                <input
                  id="select-all-files"
                  ref={headerRef}
                  type="checkbox"
                  checked={allSelected}
                  onChange={e => onToggleAll(e.target.checked)}
                  disabled={batchRunning}
                />
              </th>
              <th>Name</th>
              <th>Type</th>
              <th>Size</th>
              {batch && <th>Status</th>}
            </tr>
          </thead>
          <tbody>
            {files.map(file => {
              const item    = itemByFileId.get(file.id)
              const checked = selectedIds.has(file.id)
              return (
                <tr key={file.id} className={checked ? 'is-selected' : undefined}>
                  <td className="file-table__check">
                    <label className="sr-only" htmlFor={`file-${file.id}`}>
                      Select {file.name}
                    </label>
                    <input
                      id={`file-${file.id}`}
                      type="checkbox"
                      checked={checked}
                      onChange={() => onToggle(file.id)}
                      disabled={batchRunning}
                    />
                  </td>
                  <td>
                    <div className="file-table__name-cell">
                      <span
                        className={`file-table__file-icon file-table__file-icon--${file.kind}`}
                        aria-hidden="true"
                      >
                        {file.kind === 'pdf' ? '📄' : '🖼'}
                      </span>
                      <span className="file-table__filename" title={file.name}>
                        {file.name}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className={`badge badge--${file.kind}`}>
                      {file.kind === 'pdf' ? 'PDF' : 'Image'}
                    </span>
                  </td>
                  <td className="file-table__size">{formatBytes(file.size_bytes)}</td>
                  {batch && (
                    <td>
                      {item
                        ? <StatusBadge status={item.status} />
                        : <span className="text-muted">—</span>}
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
