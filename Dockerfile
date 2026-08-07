# ---- Stage 1: builder ----
# Compiles Python deps (including any that need gcc) into wheels so the
# final image doesn't need build tools.
FROM python:3.12-slim AS builder

WORKDIR /build

# Build deps only needed to compile wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ---- Stage 2: runtime ----
# Slim final image: copies prebuilt wheels, installs them, drops the compiler.
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime-only system deps (libpq for psycopg2, no gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps from the wheels built in stage 1
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Copy application code
COPY app ./app

# Run as a non-root user (security best practice)
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Default command runs the API; the worker service overrides this in compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
