import { useState } from 'react'
import { ApiError, createBatch, listDriveFiles } from './api.ts'
import { DriveForm } from './components/DriveForm.tsx'
import { ExportButton } from './components/ExportButton.tsx'
import { FileTable } from './components/FileTable.tsx'
import { ResultsList } from './components/ResultsList.tsx'
import { useBatchPolling } from './hooks/useBatchPolling.ts'
import type { DriveFile, OcrLanguage } from './types.ts'

const RUNNING = new Set(['queued', 'running'])

export default function App() {
  // ── Drive file list ──────────────────────────────────
  const [files, setFiles] = useState<DriveFile[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadLoading, setLoadLoading] = useState(false)

  // ── Selection & language ─────────────────────────────
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [language, setLanguage] = useState<OcrLanguage>('fra+eng')

  // ── Batch ────────────────────────────────────────────
  const [batchId, setBatchId] = useState<string | null>(null)
  const [batchError, setBatchError] = useState<string | null>(null)
  const [batchStarting, setBatchStarting] = useState(false)

  const { batch, error: pollError } = useBatchPolling(batchId)

  const batchRunning = batch !== null && RUNNING.has(batch.status)
  const batchTerminal =
    batch !== null &&
    (batch.status === 'completed' || batch.status === 'completed_with_errors')

  // ── Handlers ─────────────────────────────────────────

  async function handleLoad(folderUrl: string, lang: OcrLanguage) {
    setLoadError(null)
    setLoadLoading(true)
    setLanguage(lang)
    // Reset selection and batch when loading a new folder
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
      if (next.has(id)) next.delete(id)
      else next.add(id)
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

  const anyError = loadError ?? batchError ?? pollError

  return (
    <main className="container page">
      <header className="page__header">
        <h1 className="page__title">Drive-to-Text POC</h1>
        <p className="page__subtitle">
          Extract text from PDFs and images stored in Google Drive.
        </p>
      </header>

      {/* ── 1. Folder form ──────────────────────────────── */}
      <section className="section">
        <DriveForm
          loading={loadLoading}
          error={loadError}
          onLoad={handleLoad}
        />
      </section>

      {/* ── 2. File list + batch controls ───────────────── */}
      {files.length > 0 && (
        <section className="section">
          <FileTable
            files={files}
            selectedIds={selectedIds}
            batch={batch}
            batchRunning={batchRunning}
            onToggle={handleToggle}
            onToggleAll={handleToggleAll}
          />

          <div className="batch-toolbar">
            {!batchTerminal ? (
              <button
                className="btn btn--primary"
                onClick={handleProcess}
                disabled={selectedIds.size === 0 || batchRunning || batchStarting}
              >
                {batchStarting
                  ? 'Starting…'
                  : batchRunning
                    ? 'Processing…'
                    : `Process selected (${selectedIds.size})`}
              </button>
            ) : (
              <>
                <button
                  className="btn btn--secondary"
                  onClick={handleNewBatch}
                >
                  New batch
                </button>
                <ExportButton batch={batch} />
              </>
            )}

            {anyError && !loadError && (
              <p className="inline-error" role="alert" aria-live="polite">
                {anyError}
              </p>
            )}
          </div>
        </section>
      )}

      {/* ── 3. Results ──────────────────────────────────── */}
      {batch && batch.items.length > 0 && (
        <section className="section">
          <ResultsList batch={batch} />
        </section>
      )}
    </main>
  )
}
