# Dependency licences

Licences of the main dependencies and whether they allow closed-source commercial use.

## How this file was built

1. List Python dependencies with `pip-licenses`.
2. List npm dependencies with `license-checker`, including transitive dependencies.
3. Check each row by hand against that project's upstream repository, then write the check date in **Verified on**.

No lockfile has been scanned yet. **Licence (SPDX)** and **Commercial use (closed source)** are `TO VERIFY` on every row. **Version** is `unpinned` until a lockfile exists. Transitive rows are added only after the commands above have been run.

## Python runtime

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Type | Note | Verified on |
| --- | --- | --- | --- | --- | --- | --- |
| fastapi | unpinned | TO VERIFY | TO VERIFY | direct | HTTP API | — |
| pydantic | unpinned | TO VERIFY | TO VERIFY | direct | v2 models | — |
| pydantic-settings | unpinned | TO VERIFY | TO VERIFY | direct | Settings from environment | — |
| httpx | unpinned | TO VERIFY | TO VERIFY | direct | Google Drive REST v3 client | — |
| pypdf | unpinned | TO VERIFY | TO VERIFY | direct | PDF text extraction | — |
| pypdfium2 | unpinned | TO VERIFY | TO VERIFY | direct | PDF rendering only | — |
| Pillow | unpinned | TO VERIFY | TO VERIFY | direct | Image handling | — |
| pytesseract | unpinned | TO VERIFY | TO VERIFY | direct | Python wrapper; the engine is under System tools | — |

## Frontend runtime

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Type | Note | Verified on |
| --- | --- | --- | --- | --- | --- | --- |
| react | unpinned | TO VERIFY | TO VERIFY | direct | UI library | — |
| react-dom | unpinned | TO VERIFY | TO VERIFY | direct | DOM renderer | — |

## Dev tools

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Type | Note | Verified on |
| --- | --- | --- | --- | --- | --- | --- |
| pytest | unpinned | TO VERIFY | TO VERIFY | direct | Python tests | — |
| ruff | unpinned | TO VERIFY | TO VERIFY | direct | Python linter | — |
| typescript | unpinned | TO VERIFY | TO VERIFY | direct | Frontend typechecker | — |
| vite | unpinned | TO VERIFY | TO VERIFY | direct | Frontend dev server and build | — |

## System tools (not redistributed: Tesseract, language data, PDFium)

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Type | Note | Verified on |
| --- | --- | --- | --- | --- | --- | --- |
| Tesseract | host | TO VERIFY | TO VERIFY | not redistributed | Installed on the host; not shipped in this repository | — |
| Tesseract language data (fra, eng) | host | TO VERIFY | TO VERIFY | not redistributed | Host tessdata for `fra+eng`; not shipped in this repository | — |
| PDFium | n/a | TO VERIFY | TO VERIFY | not redistributed | Used via pypdfium2; not redistributed by this repository | — |

## Considered and rejected (PyMuPDF, Poppler/pdf2image, Ghostscript)

| Dependency | Version | Licence (SPDX) | Commercial use (closed source) | Type | Note | Verified on |
| --- | --- | --- | --- | --- | --- | --- |
| PyMuPDF | n/a | TO VERIFY | TO VERIFY | rejected | Not used. Project rule: no GPL/AGPL dependencies | — |
| Poppler | n/a | TO VERIFY | TO VERIFY | rejected | Not used. Project rule: no Poppler | — |
| pdf2image | n/a | TO VERIFY | TO VERIFY | rejected | Not used. Project rule: no Poppler | — |
| Ghostscript | n/a | TO VERIFY | TO VERIFY | rejected | Not used. Project rule: no Ghostscript | — |
