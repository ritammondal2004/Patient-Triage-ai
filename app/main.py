
"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_audit, routes_overrides, routes_patients, routes_queue, routes_triage
from app.core.config import get_settings
from app.core.database import init_db
from app.services.triage_service import TriageEngineError, engine_info

settings = get_settings()

DESCRIPTION = """
AI-assisted Emergency Department triage decision support (prototype).

Decision support only: the clinician always holds final authority. Every score carries a
confidence indicator, the safety layer can only escalate, and every override is logged.
Runs on 100% synthetic data. Not validated for clinical use.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Idempotent: safe on every boot whether or not the schema already exists.
    try:
        init_db()
        print("[ok] database ready")
    except Exception as exc:
        print(f"[warn] database init failed: {exc}")

    info = engine_info()
    if "error" in info:
        print(f"[warn] risk engine not loadable: {info['error']}")
    else:
        print(f"[ok] engine {info['production_model']} v{info['model_version']} "
              f"@ threshold {info['operating_threshold']}")
    yield


app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version="1.0.0-prototype",
    lifespan=lifespan) 

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    routes_patients.router,
    routes_triage.router,
    routes_queue.router,
    routes_overrides.router,
    routes_audit.router,
):
    app.include_router(router)


@app.exception_handler(TriageEngineError)
async def engine_error_handler(request, exc: TriageEngineError):
    # 503, not 500: the engine is unavailable, and the caller should retry rather than treat the patient as unscored.
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/", tags=["meta"])
def root():
    return {
        "name": settings.app_name,
        "version": "1.0.0-prototype",
        "status": "PROTOTYPE - NOT VALIDATED FOR CLINICAL USE",
        "jurisdiction": settings.jurisdiction,
        "docs": "/docs",
    }


@app.get("/health", tags=["meta"])
def health():
    info = engine_info()
    return {
        "status": "degraded" if "error" in info else "ok",
        "environment": settings.environment,
        "engine": info,
    }