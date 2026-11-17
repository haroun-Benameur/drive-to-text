import { type FormEvent, useState } from 'react'
import type { OcrLanguage } from '../types.ts'

const LANGUAGE_OPTIONS: { value: OcrLanguage; label: string }[] = [
  { value: 'fra',         label: 'French' },
  { value: 'eng',         label: 'English' },
  { value: 'ara',         label: 'Arabic' },
  { value: 'fra+eng',     label: 'French + English' },
  { value: 'fra+eng+ara', label: 'French + English + Arabic' },
]

interface Props {
  loading: boolean
  error: string | null
  onLoad: (folderUrl: string, language: OcrLanguage) => void
}

export function DriveForm({ loading, error, onLoad }: Props) {
  const [url, setUrl] = useState('')
  const [language, setLanguage] = useState<OcrLanguage>('fra+eng')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = url.trim()
    if (trimmed) onLoad(trimmed, language)
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <p className="drive-form__hint">
        <span>🔗</span>
        Paste a public Google Drive folder URL — anyone with the link can view.
      </p>

      <div className="drive-form__row">
        <div className="drive-form__field">
          <label htmlFor="folder-url" className="drive-form__label">
            Folder URL
          </label>
          <input
            id="folder-url"
            type="url"
            className="drive-form__input"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://drive.google.com/drive/folders/…"
            disabled={loading}
            aria-describedby={error ? 'folder-url-error' : undefined}
            aria-invalid={error ? 'true' : undefined}
            required
          />
        </div>

        <div className="drive-form__field drive-form__field--narrow">
          <label htmlFor="ocr-language" className="drive-form__label">
            OCR Language
          </label>
          <select
            id="ocr-language"
            className="drive-form__select"
            value={language}
            onChange={e => setLanguage(e.target.value as OcrLanguage)}
            disabled={loading}
          >
            {LANGUAGE_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <button
          type="submit"
          className="btn btn--primary drive-form__btn"
          disabled={loading || !url.trim()}
        >
          {loading ? (
            <><span aria-hidden="true">⏳</span> Loading…</>
          ) : (
            <><span aria-hidden="true">📂</span> Load files</>
          )}
        </button>
      </div>

      <div
        id="folder-url-error"
        className="drive-form__error"
        aria-live="polite"
        role="alert"
      >
        {error ? <><span aria-hidden="true">⚠</span> {error}</> : null}
      </div>
    </form>
  )
}
