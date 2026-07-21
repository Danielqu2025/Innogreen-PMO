from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers.ops import router as ops_router
from routers.ops import tenant_router

settings = get_settings()

app = FastAPI(
    title="Innogreen PMO API",
    version="1.3.0-phase-b",
    docs_url="/docs" if settings.pmo_enable_docs else None,
    redoc_url="/redoc" if settings.pmo_enable_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ops_router)
app.include_router(tenant_router)


@app.get("/health")
def health() -> dict:
    db_path = Path(settings.pmo_db_path)
    if not db_path.is_absolute():
        db_path = (Path(__file__).resolve().parents[1] / settings.pmo_db_path).resolve()
    return {
        "status": "ok",
        "db_exists": db_path.exists(),
        "db_path": str(db_path),
    }
