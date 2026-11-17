# ── Backend image ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install Tesseract and language packs, then clean up apt lists to keep
# the image small. Use http:// to avoid corporate TLS interception on the
# Debian apt mirrors.
RUN sed -i 's|https://|http://|g' /etc/apt/sources.list.d/*.sources 2>/dev/null || true \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-eng \
      tesseract-ocr-fra \
      tesseract-ocr-ara \
 && rm -rf /var/lib/apt/lists/*

# Create a non-root user so the process never runs as root.
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Install Python dependencies before copying application code so the
# dependency layer is cached even when source files change.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source.
COPY app/ ./app/

# Switch to non-root user.
USER appuser

EXPOSE 8000

# Single worker: batches are in-memory and must stay in one process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
