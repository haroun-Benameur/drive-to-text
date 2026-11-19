import { useState } from 'react'
import { StatusBadge } from './StatusBadge.tsx'
import type { Batch, BatchItem, ExtractionMethod } from '../types.ts'

const METHOD_LABELS: Record<ExtractionMethod, string> = {
  pdf_text:       'PDF parser',
  ocr:            'OCR',
  'pdf_text+ocr': 'PDF parser + OCR',
}

function formatConfidence(value: number): string {
  const rounded = Math.round(value * 10) / 10
  const shown = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)
  return `OCR confidence ${shown}%`
}

function formatDuration(ms: number | null): string {
  if (ms === null) return ''
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

function fileIcon(mimeType: string | null): string {
  if (!mimeType) return '📄'
  if (mimeType === 'application/pdf') return '📄'
  if (mimeType.startsWith('image/')) return '🖼'
  return '📄'
}

function fileIconClass(mimeType: string | null): string {
  if (mimeType?.startsWith('image/')) return 'result-item__file-icon--image'
  if (mimeType === 'application/pdf')  return 'result-item__file-icon--pdf'
  return 'result-item__file-icon--unknown'
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }).catch(() => { /* clipboard API may be blocked */ })
  }

  return (
    <button
      type="button"
      className="btn btn--ghost btn--sm result-item__copy-btn"
      onClick={handleCopy}
      aria-label="Copy extracted text to clipboard"
      title="Copy to clipboard"
    >
      {copied ? '✓ Copied' : '📋 Copy'}
    </button>
  )
}

function ItemDetail({ item }: { item: BatchItem }) {
  const method   = item.extraction_method
  const duration = formatDuration(item.duration_ms)

  return (
    <details className="result-item">
      <summary className="result-item__summary">
        <span className="result-item__chevron" aria-hidden="true">▶</span>

        <span
          className={`result-item__file-icon ${fileIconClass(item.mime_type)}`}
          aria-hidden="true"
        >
          {fileIcon(item.mime_type)}
        </span>

        <span className="result-item__filename" title={item.filename ?? item.file_id}>
          {item.filename ?? item.file_id}
        </span>

        <span className="result-item__meta">
          <StatusBadge status={item.status} />
          {method && (
            <span className="badge badge--method">{METHOD_LABELS[method]}</span>
          )}
          {item.ocr_confidence != null && (
            <span className="badge badge--confidence">
              {formatConfidence(item.ocr_confidence)}
            </span>
          )}
          {duration && (
            <span className="result-item__duration">{duration}</span>
          )}
        </span>
      </summary>

      <div className="result-item__body">

        {/* Error */}
        {item.status === 'failed' && item.error && (
          <div className="result-item__error-box">
            <p className="result-item__error-code">{item.error.code}</p>
            <p className="result-item__error-msg">{item.error.message}</p>
          </div>
        )}

        {/* Warnings */}
        {item.warnings.length > 0 && (
          <ul className="result-item__warnings">
            {item.warnings.map(w => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}

        {/* Extracted text */}
        {item.status === 'done' && (
          item.text && item.text.trim().length > 0 ? (
            <div className="result-item__text-wrapper">
              <CopyButton text={item.text} />
              <pre className="result-item__text" dir="auto">{item.text}</pre>
            </div>
          ) : (
            <p className="result-item__empty">
              No text was extracted from this file.
            </p>
          )
        )}

      </div>
    </details>
  )
}

interface Props {
  batch: Batch
}

export function ResultsList({ batch }: Props) {
  const { counts, items } = batch

  return (
    <section>
      <div className="results__header">
        <h2 className="results__title">Extraction Results</h2>
        <p className="results__summary" aria-live="polite">
          <span>✓ {counts.done} done</span>
          {counts.failed > 0 && <span>✕ {counts.failed} failed</span>}
          {(counts.pending + counts.processing) > 0 && (
            <span>◎ {counts.pending + counts.processing} pending</span>
          )}
        </p>
      </div>

      <div className="results__list">
        {items.map(item => (
          <ItemDetail key={item.file_id} item={item} />
        ))}
      </div>
    </section>
  )
}
