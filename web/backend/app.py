import sys
from pathlib import Path
from contextlib import asynccontextmanager

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .database import engine, Base
from .routes import sessions as sessions_routes
from .routes import dashboard as dashboard_routes
from .routes import mistakes as mistakes_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="OT Tutor API", lifespan=lifespan)

import os as _os
_cors_origins = _os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:4173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_routes.router, prefix="/api")
app.include_router(dashboard_routes.router, prefix="/api")
app.include_router(mistakes_routes.router, prefix="/api")

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}

# Serve built React frontend in production
DIST = ROOT / "web" / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file = DIST / full_path
        if file.exists() and file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(DIST / "index.html"))
