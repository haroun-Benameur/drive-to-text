import { StatusBadge } from './StatusBadge.tsx'
import type { Batch, BatchItem, ExtractionMethod } from '../types.ts'

const METHOD_LABELS: Record<ExtractionMethod, string> = {
  pdf_text:      'PDF parser',
  ocr:           'OCR',
  'pdf_text+ocr': 'PDF parser + OCR',
}

function formatDuration(ms: number | null): string {
  if (ms === null) return ''
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

function ItemDetail({ item }: { item: BatchItem }) {
  const method = item.extraction_method
  const duration = formatDuration(item.duration_ms)

  const summaryParts: string[] = []
  if (method) summaryParts.push(METHOD_LABELS[method])
  if (duration) summaryParts.push(duration)

  return (
    <details className="result-item">
      <summary className="result-item__summary">
        <span className="result-item__filename">
          {item.filename ?? item.file_id}
        </span>
        <StatusBadge status={item.status} />
        {method && (
          <span className="badge badge--method">{METHOD_LABELS[method]}</span>
        )}
        {duration && (
          <span className="result-item__duration">{duration}</span>
        )}
      </summary>

      <div className="result-item__body">
        {/* ── Error ──────────────────────────────────────── */}
        {item.status === 'failed' && item.error && (
          <div className="result-item__error">
            <strong>{item.error.code}</strong>
            <p>{item.error.message}</p>
          </div>
        )}

        {/* ── Warnings ───────────────────────────────────── */}
        {item.warnings.length > 0 && (
          <ul className="result-item__warnings">
            {item.warnings.map(w => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}

        {/* ── Text ───────────────────────────────────────── */}
        {item.status === 'done' && (
          item.text && item.text.trim().length > 0 ? (
            <pre className="result-item__text" dir="auto">
              {item.text}
            </pre>
          ) : (
            <p className="text-muted result-item__empty">
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
    <section className="results">
      <div className="results__header">
        <h2 className="results__title">Results</h2>
        <p className="results__summary" aria-live="polite">
          {counts.done} done
          {counts.failed > 0 && `, ${counts.failed} failed`}
          {(counts.pending + counts.processing) > 0 &&
            `, ${counts.pending + counts.processing} pending`}
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
