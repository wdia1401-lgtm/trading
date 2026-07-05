from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import api_router
from .config import settings
from .database import init_db

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "AI-powered startup idea generation & validation platform with an "
        "integrated newsletter ad management module (AdBooker)."
    ),
    lifespan=lifespan,
)
app.include_router(api_router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "version": __version__, "ai_backend": settings.ai_backend}


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(WEB_DIR / "index.html")
