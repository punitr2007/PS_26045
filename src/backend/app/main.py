from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import chat, health, audit
from app.core.lifespan import lifespan

app = FastAPI(
    title="IP-SAKTI Legal RAG Backend",
    description="FastAPI backend providing RAG-powered legal analysis for the Sahayak frontend",
    version="1.0.0",
    lifespan=lifespan
)

# CORS: reads allowed origins from CORS_ORIGINS env var (comma-separated),
# with defaults for local Vite and preview servers.
import os

cors_env = os.getenv("CORS_ORIGINS", "")
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://localhost:8080",
    "https://ayurveda-ps-26045.vercel.app",
]
if cors_env:
    for origin in cors_env.split(","):
        o = origin.strip()
        if o and o not in allowed_origins:
            allowed_origins.append(o)

# Regex to automatically permit all Vercel deployments (production & preview)
# as well as local frontend dev servers
allow_origin_regex = r"^https:\/\/.*\.vercel\.app$|^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$"
if os.getenv("ALLOW_ALL_CORS", "true").lower() == "true":
    allow_origin_regex = r".*"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Formulation Audit"])


@app.get("/", tags=["Root"], summary="API Root / Service Info")
async def root():
    return {
        "status": "online",
        "service": "IP-SAKTI Legal RAG Backend",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)

