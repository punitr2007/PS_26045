# 🐳 Docker Deployment Guide — IP-SAKTI Legal RAG

This guide explains how to build, test, and deploy both the **FastAPI Backend** and the **TanStack Start / React Frontend** using Docker and Docker Compose.

---

## ⚡ Quickstart: Docker Compose (Full Stack)

To build and run both the frontend and backend together:

### 1. Configure Backend Environment
Ensure your `.env` exists in `code/backend/.env`:
```bash
cp code/backend/.env.example code/backend/.env
# Edit code/backend/.env with your GEMINI_API_KEY, QDRANT_URL, etc.
```

### 2. Start All Services
From the workspace root directory:
```bash
docker compose up --build
```

- **Frontend**: Accessible at [http://localhost:3000](http://localhost:3000)
- **Backend API & Swagger Docs**: Accessible at [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check**: [http://localhost:8000/api/v1/health/live](http://localhost:8000/api/v1/health/live)

To run in the background (detached):
```bash
docker compose up -d --build
```

To stop all services:
```bash
docker compose down
```

---

## 📦 Individual Service Builds

### 1. Backend (`code/backend`)

The backend uses a lightweight Python 3.12 slim image with `uv` for fast dependency installation.

#### Build the Image
```bash
docker build -t ip-shakti-backend ./code/backend
```

#### Run the Container
```bash
docker run -d \
  --name ip-shakti-backend \
  -p 8000:8000 \
  --env-file ./code/backend/.env \
  -v backend_checkpoints:/app/checkpoints \
  ip-shakti-backend
```

---

### 2. Frontend (`code/frontend`)

The frontend is a TanStack Start / Nitro SSR application built using a multi-stage Dockerfile (`node:20-alpine`) with `pnpm`.

#### Build the Image
> [!NOTE]
> Since the frontend is executed in the user's browser, `VITE_BACKEND_URL` specifies the public/accessible URL of the backend API.

```bash
docker build \
  --build-arg VITE_BACKEND_URL=http://localhost:8000 \
  -t ip-shakti-frontend \
  ./code/frontend
```

For production domain deployment:
```bash
docker build \
  --build-arg VITE_BACKEND_URL=https://api.yourdomain.com \
  -t ip-shakti-frontend \
  ./code/frontend
```

#### Run the Container
```bash
docker run -d \
  --name ip-shakti-frontend \
  -p 3000:3000 \
  ip-shakti-frontend
```

---

## ☁️ Cloud & Production Deployment Notes

### Environment Variables
| Service | Variable | Description |
|---|---|---|
| **Backend** | `PORT` | Listening port (defaults to `8000`) |
| **Backend** | `WORKERS` | Number of Uvicorn workers (defaults to `2`) |
| **Backend** | `CORS_ORIGINS` | Comma-separated list of allowed origins (e.g. `https://yourdomain.com`) |
| **Backend** | `GEMINI_API_KEY` | Google Gemini API key for embeddings / LLM |
| **Backend** | `QDRANT_API_KEY` / `CLUSTER_ENDPOINT` | Vector database connectivity |
| **Frontend** | `VITE_BACKEND_URL` | Backend URL passed during `docker build` |
| **Frontend** | `PORT` | Listening port for Nitro SSR server (defaults to `3000`) |
| **Frontend** | `HOST` | Binding address (defaults to `0.0.0.0`) |

### Production Platforms
- **AWS ECS / GCP Cloud Run / Render / Railway**: Both Dockerfiles support dynamic `$PORT` environment variable injection out-of-the-box.
- **Persistent Storage**: For conversational checkpoints and session memory across backend restarts, mount a persistent volume to `/app/checkpoints`.
