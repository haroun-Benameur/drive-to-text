# Drive-to-Text Document Extraction POC (TA-2026-01)

Extract text from PDFs and images stored in Google Drive using Tesseract OCR and pypdf.

---

## Architecture overview

```
frontend (React + Vite, port 5173)
    └─ /api proxy ──► backend (FastAPI, port 8000)
                          ├─ Drive REST v3 (download files)
                          ├─ pypdf  (native text extraction)
                          └─ pypdfium2 + Tesseract (OCR fallback)
```

- **No database.** Batches are stored in memory with a configurable TTL.
- **No Celery/Redis.** A `ThreadPoolExecutor` handles concurrent file processing.
- **No GPL/AGPL deps.** pypdfium2 replaces Poppler/Ghostscript for rendering.

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.11 |
| Node.js | 18 |
| Tesseract | 5 |
| Google Drive API key | — |

Install Tesseract:
- **Windows:** [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki). Add `fra` and `ara` language packs.
- **Linux/macOS:** `apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara` / `brew install tesseract`

---

## Setup

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env — set GOOGLE_API_KEY and TESSERACT_CMD if not on PATH
```

### Frontend

```bash
cd frontend
npm install
```

---

## Run

```bash
# Terminal 1 – backend
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2 – frontend
cd frontend && npm run dev
```

Open <http://localhost:5173>.

---

## Tests

```bash
cd backend
pytest            # 162 tests
ruff check .      # linter

cd frontend
npm run build     # TypeScript + Vite build
npm run lint      # ESLint
```

---

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness + Tesseract status |
| POST | `/api/drive/files` | List files in a Drive folder |
| POST | `/api/batches` | Start an extraction batch (202) |
| GET | `/api/batches/{id}` | Poll batch status |
| GET | `/api/batches/{id}/export` | Download results as JSON attachment |

All errors use the envelope: `{"error": {"code": "...", "message": "..."}}`.

---

## Environment variables

See [`backend/.env.example`](backend/.env.example) for the full list with defaults and comments.

---

## Known limits

- Batches are in-memory; they are lost on server restart.
- Maximum 50 files per batch, 25 MB per file, 30 PDF pages per file.
- Only `fra`, `eng`, `ara` (and combinations) are accepted as OCR languages.
- Drive API key is required; OAuth is not implemented.

---

## Licence

See [LICENSE](LICENSE).
