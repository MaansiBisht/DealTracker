# syntax=docker/dockerfile:1.7

# ---------- Stage 1: build the React UI -----------------------------------
FROM node:20-alpine AS ui-builder

WORKDIR /ui

COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY ui/ ./
RUN npm run build


# ---------- Stage 2: Python runtime + headless Chromium -------------------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    DATABASE_URL=sqlite:////app/data/dealtracker.db

# Chromium + driver + the system libs Chrome won't start without.
# fonts-liberation gives Chromium a baseline font so rendered prices
# don't show up as tofu.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        fonts-liberation \
        libnss3 \
        libgbm1 \
        libxshmfence1 \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

# Prebuilt UI from stage 1; FastAPI mounts ui/dist as static when present.
COPY --from=ui-builder /ui/dist ./ui/dist

# Persistent SQLite location — mount this as a volume in compose.
RUN mkdir -p /app/data

EXPOSE 8000

# tini reaps zombie chromium processes left over from crashed scrapes.
ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["uvicorn", "src.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
