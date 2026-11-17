import type { Batch, DriveFilesResponse, OcrLanguage } from './types.ts'

// ── Error class ────────────────────────────────────────────────────────────

export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

// ── Core fetch wrapper ─────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError('NETWORK_ERROR', 'Cannot reach the server.', 0)
  }

  if (!response.ok) {
    let code = 'UNKNOWN_ERROR'
    let message = `HTTP ${response.status}`
    try {
      const body = (await response.json()) as { error?: { code?: string; message?: string } }
      code = body.error?.code ?? code
      message = body.error?.message ?? message
    } catch {
      // non-JSON error body — keep defaults
    }
    throw new ApiError(code, message, response.status)
  }

  return response.json() as Promise<T>
}

// ── Public API helpers ─────────────────────────────────────────────────────

/** List PDF / image files inside a Google Drive folder. */
export function listDriveFiles(folderUrl: string): Promise<DriveFilesResponse> {
  return request<DriveFilesResponse>('/api/drive/files', {
    method: 'POST',
    body: JSON.stringify({ folder_url: folderUrl }),
  })
}

/** Create a new extraction batch and return its initial state. */
export function createBatch(
  fileIds: string[],
  language?: OcrLanguage,
): Promise<Batch> {
  return request<Batch>('/api/batches', {
    method: 'POST',
    body: JSON.stringify({ file_ids: fileIds, language: language ?? null }),
  })
}

/** Fetch the current state of an existing batch. */
export function getBatch(id: string): Promise<Batch> {
  return request<Batch>(`/api/batches/${encodeURIComponent(id)}`)
}

/** Return the URL to download the full batch export JSON. */
export function exportUrl(id: string): string {
  return `/api/batches/${encodeURIComponent(id)}/export`
}
