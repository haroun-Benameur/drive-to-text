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

  const allSelected = files.length > 0 && selectedIds.size === files.length
  const someSelected = selectedIds.size > 0 && !allSelected

  // Set indeterminate through a ref (can't be set via JSX prop)
  useEffect(() => {
    if (headerRef.current) {
      headerRef.current.indeterminate = someSelected
    }
  }, [someSelected])

  if (files.length === 0) {
    return (
      <p className="empty-state">
        No supported files found in this folder.
      </p>
    )
  }

  // Build a lookup of batch items by file_id
  const itemByFileId = new Map(batch?.items.map(it => [it.file_id, it]) ?? [])

  return (
    <div>
      <p className="selection-info" aria-live="polite">
        {selectedIds.size} of {files.length} selected
      </p>

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
                  aria-label="Select all files"
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
              const item = itemByFileId.get(file.id)
              return (
                <tr key={file.id}>
                  <td className="file-table__check">
                    <label
                      className="sr-only"
                      htmlFor={`file-${file.id}`}
                    >
                      Select {file.name}
                    </label>
                    <input
                      id={`file-${file.id}`}
                      type="checkbox"
                      checked={selectedIds.has(file.id)}
                      onChange={() => onToggle(file.id)}
                      disabled={batchRunning}
                      aria-label={`Select ${file.name}`}
                    />
                  </td>
                  <td className="file-table__name">{file.name}</td>
                  <td>
                    <span
                      className={`badge badge--type badge--${file.kind}`}
                    >
                      {file.kind === 'pdf' ? 'PDF' : 'Image'}
                    </span>
                  </td>
                  <td className="file-table__size">
                    {formatBytes(file.size_bytes)}
                  </td>
                  {batch && (
                    <td>
                      {item ? (
                        <StatusBadge status={item.status} />
                      ) : (
                        <span className="text-muted">—</span>
                      )}
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
