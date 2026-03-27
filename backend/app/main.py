from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes.artifacts import router as artifacts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.projects import router as projects_router
from app.api.routes.schedules import router as schedules_router
from app.api.routes.scripts import router as scripts_router
from app.api.routes.video_jobs import router as video_jobs_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.startup_checks import run_startup_checks
from app.schemas.common import HealthResponse

settings = get_settings()
setup_logging()
run_startup_checks()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    debug=settings.debug,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(schedules_router, prefix=settings.api_v1_prefix)


@app.get("/health", response_model=HealthResponse)
@limiter.limit("60/minute")
def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc),
    )