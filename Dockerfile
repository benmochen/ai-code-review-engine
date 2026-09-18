# ---- Stage 1: frontend builder ----
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ---- Stage 2: python wheel builder ----
FROM python:3.12-slim AS python-builder

WORKDIR /build

# Build deps only needed to compile wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ---- Stage 3: runtime ----
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime-only system deps (libpq for psycopg2, no gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps from the wheels built in python-builder
COPY --from=python-builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Copy application code and built frontend assets
COPY app ./app
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Run as a non-root user (security best practice)
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Default command runs the API with proxy headers support; the worker service overrides this in compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
