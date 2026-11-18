# Dependency licences

Licences of all direct and transitive dependencies, and whether they allow
closed-source commercial use.

## How this file was built

1. Python packages: `pip-licenses --format=markdown --with-urls` run inside
   `backend/.venv` (all packages from `requirements.txt` and
   `requirements-dev.txt` installed).  
2. Frontend packages: versions and licence fields read directly from
   `frontend/package-lock.json` (lockfileVersion 3).  
3. Every row was cross-checked against the upstream repository or PyPI
   metadata on **2026-11-19**.  
4. SPDX identifiers were taken from the `License` field reported by pip-licenses
   or from `package-lock.json`; where the metadata string was ambiguous (e.g.
   "BSD License") the upstream LICENSE file was opened and the exact SPDX
   confirmed.

---

## Python runtime — direct dependencies

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Type | Note | Verified on |
|---|---|---|---|---|---|---|
| fastapi | 0.163.1 | MIT | Yes | direct | HTTP API framework | 2026-11-19 |
| pydantic | 2.14.3 | MIT | Yes | transitive (fastapi) | v2 models | 2026-11-19 |
| pydantic-settings | 2.16.3 | MIT | Yes | direct | Settings from environment | 2026-11-19 |
| httpx | 0.28.1 | BSD-3-Clause | Yes | direct | Google Drive REST v3 client; metadata says "BSD License"; upstream LICENSE confirms BSD-3-Clause | 2026-11-19 |
| pypdf | 7.1.0 | BSD-3-Clause | Yes | direct | PDF text extraction | 2026-11-19 |
| pypdfium2 | 5.15.2 | BSD-3-Clause, Apache-2.0 + bundled PDFium dependency licences | Yes (permissive); see System tools section for PDFium | direct | PDF rendering only; wrapper is BSD-3-Clause/Apache-2.0; bundled PDFium binary carries additional third-party notices shipped inside the wheel | 2026-11-19 |
| Pillow | 13.0.0 | MIT-CMU | Yes | direct | Image handling | 2026-11-19 |
| pytesseract | 0.3.13 | Apache-2.0 | Yes | direct | Python wrapper for Tesseract | 2026-11-19 |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | Yes | direct | Required by pypdf for AES-encrypted PDF decryption | 2026-11-19 |
| truststore | 0.10.5 | MIT | Yes | direct | OS certificate store injection for httpx; needed on corporate networks | 2026-11-19 |
| uvicorn | 0.54.0 | BSD-3-Clause | Yes | direct | ASGI server | 2026-11-19 |
| starlette | 1.10.0 | BSD-3-Clause | Yes | transitive (fastapi) | ASGI toolkit | 2026-11-19 |

## Python runtime — transitive dependencies

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Type | Note | Verified on |
|---|---|---|---|---|---|---|
| annotated-types | 0.8.0 | MIT | Yes | transitive (pydantic) | | 2026-11-19 |
| annotated-doc | 0.0.6 | MIT | Yes | transitive (fastapi) | FastAPI internal | 2026-11-19 |
| anyio | 4.16.0 | MIT | Yes | transitive (starlette) | Async I/O compatibility | 2026-11-19 |
| certifi | 2026.10.23 | MPL-2.0 | Yes, if unmodified (MPL-2.0 is file-level copyleft; modified MPL files must be published) | transitive (httpx) | Mozilla CA bundle | 2026-11-19 |
| cffi | 2.1.1 | MIT-0 | Yes | transitive (cryptography) | C FFI | 2026-11-19 |
| click | 8.5.1 | BSD-3-Clause | Yes | transitive (uvicorn) | CLI toolkit | 2026-11-19 |
| colorama | 0.4.6 | BSD-3-Clause | Yes | transitive (pytest/click) | Windows terminal colours; metadata says "BSD License"; upstream confirms BSD-3-Clause | 2026-11-19 |
| h11 | 0.16.0 | MIT | Yes | transitive (httpx/uvicorn) | HTTP/1.1 | 2026-11-19 |
| httpcore | 1.0.9 | BSD-3-Clause | Yes | transitive (httpx) | HTTP transport | 2026-11-19 |
| idna | 3.20 | BSD-3-Clause | Yes | transitive (httpx/anyio) | Internationalised domain names | 2026-11-19 |
| opentelemetry-api | 1.45.2 | Apache-2.0 | Yes | transitive (fastapi) | Telemetry API | 2026-11-19 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | Yes | transitive (pip-licenses/pytest) | Version utilities | 2026-11-19 |
| pycparser | 3.12 | BSD-3-Clause | Yes | transitive (cffi) | C parser | 2026-11-19 |
| pydantic_core | 2.50.4 | MIT | Yes | transitive (pydantic) | Rust core | 2026-11-19 |
| Pygments | 2.21.0 | BSD-2-Clause | Yes | transitive (pytest) | Syntax highlighting | 2026-11-19 |
| python-dotenv | 1.2.4 | BSD-3-Clause | Yes | transitive (pydantic-settings) | .env file loading | 2026-11-19 |
| sniffio | (via anyio) | MIT | Yes | transitive | Async library detection | 2026-11-19 |
| typing-inspection | 0.4.5 | MIT | Yes | transitive (pydantic) | | 2026-11-19 |
| typing_extensions | 4.16.0 | PSF-2.0 | Yes | transitive | Python standard-library backport | 2026-11-19 |

## Python dev-only tools

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Type | Note | Verified on |
|---|---|---|---|---|---|---|
| pytest | 9.2.0 | MIT | Yes | dev | Test runner | 2026-11-19 |
| ruff | 0.17.5 | MIT | Yes | dev | Linter | 2026-11-19 |
| iniconfig | 2.3.1 | MIT | Yes | transitive (pytest) | | 2026-11-19 |
| pluggy | 1.7.0 | MIT | Yes | transitive (pytest) | Plugin system | 2026-11-19 |

---

## Frontend runtime — direct dependencies

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Type | Note | Verified on |
|---|---|---|---|---|---|---|
| react | 19.3.1 | MIT | Yes | direct | UI library | 2026-11-19 |
| react-dom | 19.3.1 | MIT | Yes | direct | DOM renderer | 2026-11-19 |
| scheduler | 0.25.0 | MIT | Yes | transitive (react-dom) | React internal scheduler | 2026-11-19 |

## Frontend dev-only tools

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Type | Note | Verified on |
|---|---|---|---|---|---|---|
| typescript | 5.9.3 | Apache-2.0 | Yes | dev | Typechecker | 2026-11-19 |
| vite | 7.3.8 | MIT | Yes | dev | Build tool and dev server | 2026-11-19 |
| @vitejs/plugin-react | 5.2.0 | MIT | Yes | dev | Vite React plugin | 2026-11-19 |
| eslint | 9.39.5 | MIT | Yes | dev | JavaScript/TypeScript linter | 2026-11-19 |
| @eslint/js | 9.39.5 | MIT | Yes | dev | ESLint JS config | 2026-11-19 |
| typescript-eslint | 8.73.0 | MIT | Yes | dev | TypeScript ESLint rules | 2026-11-19 |
| eslint-plugin-react-hooks | 7.1.1 | MIT | Yes | dev | React hooks lint rules | 2026-11-19 |
| eslint-plugin-react-refresh | 0.4.26 | MIT | Yes | dev | React Refresh lint rules | 2026-11-19 |
| globals | 16.5.0 | MIT | Yes | dev | ESLint global variable definitions | 2026-11-19 |
| @types/node | 24.19.2 | MIT | Yes | dev | Node.js type definitions | 2026-11-19 |
| @types/react | 19.3.0 | MIT | Yes | dev | React type definitions | 2026-11-19 |
| @types/react-dom | 19.3.0 | MIT | Yes | dev | React DOM type definitions | 2026-11-19 |

---

## System tools and Docker image packages

These are **not redistributed by this repository**.  
The Docker image installs Debian packages via `apt-get`; the image itself
redistributes those binaries. Use versus redistribution is noted per row.

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Type | Note | Verified on |
|---|---|---|---|---|---|---|
| Tesseract OCR engine | 5.x (host / Debian package) | Apache-2.0 | Yes — TO VERIFY upstream | system / Docker | Invoked as an external process by pytesseract; not linked or bundled. Docker image redistributes the Debian binary. Verify: <https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE> | TO VERIFY |
| tessdata fra | host / Debian | Apache-2.0 | Yes — TO VERIFY upstream | system / Docker | Trained data for French OCR. Verify: <https://github.com/tesseract-ocr/tessdata/blob/main/LICENSE> | TO VERIFY |
| tessdata eng | host / Debian | Apache-2.0 | Yes — TO VERIFY upstream | system / Docker | Trained data for English OCR. Verify: same repo | TO VERIFY |
| tessdata ara | host / Debian | Apache-2.0 | Yes — TO VERIFY upstream | system / Docker | Trained data for Arabic OCR. Verify: same repo | TO VERIFY |
| Debian tesseract-ocr package | Debian trixie/stable | see /usr/share/doc/tesseract-ocr/copyright inside image | TO VERIFY | Docker only | Installed via apt-get inside the Docker image; copyright file lists bundled libraries. Run `docker run --rm <image> cat /usr/share/doc/tesseract-ocr/copyright` to review | TO VERIFY |
| PDFium (bundled in pypdfium2 wheel) | matched to pypdfium2 5.15.2 | BSD-3-Clause, Apache-2.0 + third-party notices | Yes — TO VERIFY upstream | transitive (pypdfium2 wheel) | PDFium binary embedded inside the pypdfium2 wheel. Third-party notices are shipped alongside the wheel. Verify: <https://pdfium.googlesource.com/pdfium/+/refs/heads/main/LICENSE> and the `NOTICE` file extracted from the pypdfium2 wheel | TO VERIFY |

---

## Copyleft check

A full scan of all packages listed above (Python runtime, Python dev, frontend
runtime, frontend dev) finds **no GPL, LGPL, AGPL, or other strong-copyleft
licence**.

The only non-permissive licence present is **MPL-2.0** (certifi). MPL-2.0 is a
*weak, file-level* copyleft: you must publish modifications to MPL-licensed
*files themselves* if you distribute them, but you are not required to open-source
the rest of your application. Using certifi unmodified — as this project does —
carries no open-source obligation.

**Result: the application can be used in a closed-source commercial product
without open-sourcing any application code, provided certifi is not modified.**

Tesseract, tessdata and PDFium are marked "TO VERIFY upstream" in the system
tools section. Based on published information they are Apache-2.0, which is
permissive, but redistribution (e.g. in Docker) requires verifying the exact
licence of the Debian packages and their bundled dependencies before shipping.

---

## Considered and rejected

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Reason rejected |
|---|---|---|---|---|
| PyMuPDF (fitz) | n/a | to confirm upstream | Likely No for closed-source (AGPL-3.0 for the main build) | Project rule: no GPL/AGPL dependencies |
| Poppler | n/a | to confirm upstream | No (GPL-2.0+) | Project rule: no Poppler; also a system dependency not easily bundled |
| pdf2image | n/a | to confirm upstream | No (depends on GPL Poppler) | Project rule: no Poppler |
| Ghostscript | n/a | to confirm upstream | No (AGPL-3.0) | Project rule: no Ghostscript |

---

## Notices and obligations

| Licence | Obligation | Applies to |
|---|---|---|
| MIT / MIT-CMU / MIT-0 | Retain copyright notice and licence text in distributions | fastapi, pydantic, pydantic-settings, Pillow, truststore, h11, anyio, cffi, click (BSD applies), react, react-dom, and all MIT dev tools |
| BSD-2-Clause / BSD-3-Clause | Retain copyright notice; BSD-3 additionally forbids using the project name for endorsement | starlette, uvicorn, httpx, httpcore, pypdf, cryptography (BSD variant), Pygments, colorama, python-dotenv, idna, pycparser, packaging (BSD variant), click |
| Apache-2.0 | Retain NOTICE file if present; include licence text; state changes | pytesseract, cryptography (Apache variant), opentelemetry-api, packaging (Apache variant), typescript |
| MPL-2.0 | Publish modifications to MPL-licensed *files* if distributed; source-available requirement applies only to those files | certifi |
| PSF-2.0 | Retain PSF copyright notice | typing_extensions |
| pypdfium2 | Third-party notices for PDFium and its dependencies are shipped inside the wheel under `pypdfium2/third_party`. Review these before redistributing a Docker image that includes pypdfium2. | pypdfium2 / PDFium |
