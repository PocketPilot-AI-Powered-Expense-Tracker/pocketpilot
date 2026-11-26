import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.db.mongo import close_client, ensure_indexes, get_db
from app.routers import ai, analytics, auth, budget, expenses, income, pending, routines


log = logging.getLogger("pocketpilot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await ensure_indexes(get_db())
    except Exception:
        log.exception("Could not connect to MongoDB / create indexes. Check MONGODB_URI and Atlas network access.")
        raise
    log.info("PocketPilot API started (environment=%s)", settings.ENVIRONMENT)
    yield
    await close_client()


settings = get_settings()
_problems = settings.production_problems()
if _problems:
    raise RuntimeError("Unsafe production settings: " + "; ".join(_problems))
app = FastAPI(title="PocketPilot API", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)

app.include_router(auth.router)
app.include_router(budget.router)
app.include_router(expenses.router)
app.include_router(income.router)
app.include_router(routines.router)
app.include_router(routines.occ_router)
app.include_router(pending.router)
app.include_router(analytics.router)
app.include_router(ai.router)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    # Log the details for us; never leak internals to the client.
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})


@app.get("/api/health", tags=["health"])
async def health():
    """Liveness: the process is up (used by Render's health check)."""
    return {"status": "ok"}


@app.get("/api/health/ready", tags=["health"])
async def ready(db=Depends(get_db)):
    """Readiness: the database answers."""
    try:
        await db.command("ping")
    except Exception:
        log.exception("Database ping failed")
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "unreachable"})
    return {"status": "ok", "database": "ok"}
