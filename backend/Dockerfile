# ── Backend image ─────────────────────────────────────────────────────────────
FROM python:3.15-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# APT_PROTOCOL defaults to https (standard).
# Pass --build-arg APT_PROTOCOL=http only on networks with TLS-intercepting
# proxies that break apt's HTTPS connections (e.g. some corporate networks).
# ARG APT_PROTOCOL=https
ARG APT_PROTOCOL=https
# ARG INSTALL_EASYOCR=false
ARG INSTALL_EASYOCR=false
RUN if [ "$APT_PROTOCOL" = "http" ]; then \
      sed -i 's|https://|http://|g' /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
    fi \
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
COPY requirements-optional.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install optional EasyOCR engine when INSTALL_EASYOCR=true.
# Use the CPU-only PyTorch index to avoid the large CUDA build.
RUN if [ "$INSTALL_EASYOCR" = "true" ]; then \
      pip install --no-cache-dir \
          --extra-index-url https://download.pytorch.org/whl/cpu \
          -r requirements-optional.txt; \
    fi

# Copy application source.
COPY app/ ./app/

# Switch to non-root user.
USER appuser

EXPOSE 8000

# Single worker: batches are in-memory and must stay in one process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]