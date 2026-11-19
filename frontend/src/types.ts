// Mirrors backend app/models.py exactly.

export type OcrLanguage = 'fra' | 'eng' | 'ara' | 'fra+eng' | 'fra+eng+ara'

// ── Drive listing ──────────────────────────────────────────────────────────

export interface DriveFile {
  id: string
  name: string
  mime_type: string
  kind: 'pdf' | 'image'
  size_bytes: number | null
}

export interface DriveFilesResponse {
  folder_id: string
  files: DriveFile[]
}

// ── Extraction ─────────────────────────────────────────────────────────────

export type ExtractionMethod = 'pdf_text' | 'ocr' | 'pdf_text+ocr'

// ── Batches ────────────────────────────────────────────────────────────────

export type FileStatus = 'pending' | 'processing' | 'done' | 'failed'

export type BatchStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'completed_with_errors'

export interface ErrorInfo {
  code: string
  message: string
}

export interface BatchItem {
  file_id: string
  filename: string | null
  mime_type: string | null
  size_bytes: number | null
  status: FileStatus
  extraction_method: ExtractionMethod | null
  engine: string | null
  language: string
  page_count: number | null
  ocr_pages: number | null
  ocr_confidence: number | null
  text: string | null
  warnings: string[]
  error: ErrorInfo | null
  duration_ms: number | null
}

export interface BatchCounts {
  pending: number
  processing: number
  done: number
  failed: number
}

export interface Batch {
  id: string
  status: BatchStatus
  language: string
  created_at: string
  finished_at: string | null
  counts: BatchCounts
  items: BatchItem[]
}
