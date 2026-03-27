from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.artifacts import router as artifacts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.projects import router as projects_router
from app.api.routes.scripts import router as scripts_router
from app.api.routes.video_jobs import router as video_jobs_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.schemas.common import HealthResponse

settings = get_settings()
setup_logging()

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(projects_router, prefix=settings.api_v1_prefix)
app.include_router(video_jobs_router, prefix=settings.api_v1_prefix)
app.include_router(scripts_router, prefix=settings.api_v1_prefix)
app.include_router(artifacts_router, prefix=settings.api_v1_prefix)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc),
    )