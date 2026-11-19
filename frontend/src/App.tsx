import { useState } from 'react'
import { ApiError, createBatch, listDriveFiles } from './api.ts'
import { DriveForm } from './components/DriveForm.tsx'
import { ExportButton } from './components/ExportButton.tsx'
import { FileTable } from './components/FileTable.tsx'
import { ResultsList } from './components/ResultsList.tsx'
import { StatGrid } from './components/StatGrid.tsx'
import { useBatchPolling } from './hooks/useBatchPolling.ts'
import type { DriveFile, OcrLanguage } from './types.ts'

const RUNNING = new Set(['queued', 'running'])

export default function App() {
  // ── Drive file list ──────────────────────────────────
  const [files, setFiles]           = useState<DriveFile[]>([])
  const [loadError, setLoadError]   = useState<string | null>(null)
  const [loadLoading, setLoadLoading] = useState(false)

  // ── Selection & language ─────────────────────────────
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [language, setLanguage]       = useState<OcrLanguage>('fra+eng')

  // ── Batch ────────────────────────────────────────────
  const [batchId, setBatchId]         = useState<string | null>(null)
  const [batchError, setBatchError]   = useState<string | null>(null)
  const [batchStarting, setBatchStarting] = useState(false)

  const { batch, error: pollError } = useBatchPolling(batchId)

  const batchRunning  = batch !== null && RUNNING.has(batch.status)
  const batchTerminal =
    batch !== null &&
    (batch.status === 'completed' || batch.status === 'completed_with_errors')

  // ── Handlers ─────────────────────────────────────────

  async function handleLoad(folderUrl: string, lang: OcrLanguage) {
    setLoadError(null)
    setLoadLoading(true)
    setLanguage(lang)
    setSelectedIds(new Set())
    setBatchId(null)
    setBatchError(null)
    try {
      const res = await listDriveFiles(folderUrl)
      setFiles(res.files)
      if (res.files.length === 0) {
        setLoadError('No supported files (PDF, PNG, JPEG) found in this folder.')
      }
    } catch (err) {
      setFiles([])
      setLoadError(err instanceof ApiError ? err.message : 'An unexpected error occurred.')
    } finally {
      setLoadLoading(false)
    }
  }

  function handleToggle(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  function handleToggleAll(select: boolean) {
    setSelectedIds(select ? new Set(files.map(f => f.id)) : new Set())
  }

  async function handleProcess() {
    if (selectedIds.size === 0 || batchRunning) return
    setBatchError(null)
    setBatchStarting(true)
    try {
      const created = await createBatch([...selectedIds], language)
      setBatchId(created.id)
    } catch (err) {
      setBatchError(err instanceof ApiError ? err.message : 'Failed to start batch.')
    } finally {
      setBatchStarting(false)
    }
  }

  function handleNewBatch() {
    setBatchId(null)
    setBatchError(null)
  }

  const batchError2 = batchError ?? pollError

  return (
    <div className="app-shell">

      {/* ── Top bar ───────────────────────────────────── */}
      <header className="app-topbar">
        <div className="app-topbar__inner">
          <div className="app-topbar__icon" aria-hidden="true">📄</div>
          <div className="app-topbar__brand">
            <span className="app-topbar__label">Document Extraction</span>
            <span className="app-topbar__title">Drive-to-Text POC</span>
          </div>
        </div>
      </header>

      <div className="page-body">

        {/* ── 1. Drive folder card ──────────────────────── */}
        <div className="card">
          <div className="card__header">
            <div className="card__icon card__icon--blue" aria-hidden="true">🔗</div>
            <div>
              <p className="card__title">Google Drive Folder</p>
              <p className="card__subtitle">Load PDFs and images from a shared folder</p>
            </div>
          </div>
          <div className="card__body">
            <DriveForm
              loading={loadLoading}
              error={loadError}
              onLoad={handleLoad}
            />
          </div>
        </div>

        {/* ── 2. Stats + file table ─────────────────────── */}
        {files.length > 0 && (
          <>
            <StatGrid files={files} selectedIds={selectedIds} batch={batch} />

            <div className="card">
              <div className="card__header">
                <div className="card__icon card__icon--blue" aria-hidden="true">📋</div>
                <div>
                  <p className="card__title">Files</p>
                  <p className="card__subtitle">
                    {files.length} file{files.length !== 1 ? 's' : ''} found
                    {batchRunning && ' · Processing…'}
                  </p>
                </div>
              </div>
              <div className="card__body">
                <FileTable
                  files={files}
                  selectedIds={selectedIds}
                  batch={batch}
                  batchRunning={batchRunning}
                  onToggle={handleToggle}
                  onToggleAll={handleToggleAll}
                />

                <div className="batch-actions">
                  {!batchTerminal ? (
                    <button
                      className="btn btn--primary"
                      onClick={handleProcess}
                      disabled={selectedIds.size === 0 || batchRunning || batchStarting}
                    >
                      {batchStarting ? (
                        <><span aria-hidden="true">⏳</span> Starting…</>
                      ) : batchRunning ? (
                        <><span aria-hidden="true">⏳</span> Processing…</>
                      ) : (
                        <><span aria-hidden="true">▶</span> Process selected ({selectedIds.size})</>
                      )}
                    </button>
                  ) : (
                    <>
                      <button className="btn btn--secondary" onClick={handleNewBatch}>
                        <span aria-hidden="true">↩</span> New batch
                      </button>
                      <ExportButton batch={batch} />
                    </>
                  )}

                  {batchError2 && (
                    <p className="batch-actions__error" role="alert" aria-live="polite">
                      <span aria-hidden="true">⚠</span> {batchError2}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </>
        )}

        {/* ── 3. Results ────────────────────────────────── */}
        {batch && batch.items.length > 0 && (
          <div className="card">
            <div className="card__header">
              <div className="card__icon card__icon--green" aria-hidden="true">📝</div>
              <div>
                <p className="card__title">Extraction Results</p>
                <p className="card__subtitle">
                  {batch.counts.done} done · {batch.counts.failed} failed · {batch.counts.pending + batch.counts.processing} pending
                </p>
              </div>
            </div>
            <div className="card__body">
              <ResultsList batch={batch} />
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
