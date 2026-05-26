# Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build
RUN cp /frontend/public/pdf.worker.min.mjs /frontend/dist/pdf.worker.min.mjs

# Build backend
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/uploads/books /app/uploads/covers /app/uploads/audio /app/uploads/vids /app/data

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./

# Copy built frontend
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]