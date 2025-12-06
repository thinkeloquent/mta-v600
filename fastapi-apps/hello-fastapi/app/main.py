"""Hello FastAPI Application - Main Entry Point."""

from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import hello

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    print(f"""
╔════════════════════════════════════════════════════════════╗
║                    Hello FastAPI Server                    ║
╠════════════════════════════════════════════════════════════╣
║  Server running at: http://{settings.HOST}:{settings.PORT:<25}║
║                                                            ║
║  Endpoints:                                                ║
║    GET  /health                    - Health check          ║
║    GET  /api/hello-fastapi         - API info              ║
║    GET  /api/hello-fastapi/hello   - Hello endpoint        ║
║    POST /api/hello-fastapi/echo    - Echo endpoint         ║
║    GET  /docs                      - Swagger UI            ║
║    GET  /redoc                     - ReDoc                 ║
╚════════════════════════════════════════════════════════════╝
    """)


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }


# Register API routes
app.include_router(hello.router, prefix="/api/hello-fastapi", tags=["hello"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
