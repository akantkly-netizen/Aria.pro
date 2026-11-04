import asyncio
import hmac
import logging
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .config import Settings
from .database import JobStore
from .security import validate_media_url
from .worker import WorkerPool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

class CreateJob(BaseModel):
    url: str = Field(min_length=12, max_length=4096)
    quality: str = Field(default="best", pattern="^(best|720p|480p|audio)$")

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    store = JobStore(settings.database_path)
    pool = WorkerPool(store, settings)
    app.state.settings, app.state.store, app.state.pool = settings, store, pool
    await pool.start()
    yield
    await pool.stop()

app = FastAPI(title="Aria Pro API", version="1.0.0", description="Asynchronous media job orchestration for Aria Pro", lifespan=lifespan)

async def require_token(request: Request, authorization: str | None = Header(default=None)):
    expected = request.app.state.settings.api_token
    supplied = authorization or ""
    if not supplied.startswith("Bearer ") or not hmac.compare_digest(supplied[7:], expected):
        raise HTTPException(status_code=401, detail="توکن دسترسی معتبر نیست.", headers={"WWW-Authenticate":"Bearer"})

@app.get("/health")
async def health(request: Request):
    ready = hasattr(request.app.state, "store")
    return {"status":"ok" if ready else "starting", "service":"aria-pro", "version":"1.0.0"}

@app.get("/api/v1/jobs")
async def list_jobs(request: Request, limit: int = 25, _: None = Depends(require_token)):
    if not 1 <= limit <= 100: raise HTTPException(422, "limit باید بین ۱ تا ۱۰۰ باشد.")
    items = await asyncio.to_thread(request.app.state.store.list, limit)
    return {"items":items, "count":len(items)}

@app.post("/api/v1/jobs", status_code=202)
async def create_job(payload: CreateJob, request: Request, _: None = Depends(require_token)):
    try:
        url = await asyncio.to_thread(validate_media_url, payload.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    job_id = uuid.uuid4().hex
    item = await asyncio.to_thread(request.app.state.store.create, job_id, url, payload.quality)
    return {"job":item, "status_url":f"/api/v1/jobs/{job_id}", "file_url":f"/api/v1/jobs/{job_id}/file"}

@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str, request: Request, _: None = Depends(require_token)):
    item = await asyncio.to_thread(request.app.state.store.get, job_id)
    if not item: raise HTTPException(404, "کار پیدا نشد.")
    return {"job":item}

@app.delete("/api/v1/jobs/{job_id}")
async def cancel_job(job_id: str, request: Request, _: None = Depends(require_token)):
    item = await asyncio.to_thread(request.app.state.store.request_cancel, job_id)
    if not item: raise HTTPException(404, "کار پیدا نشد.")
    return {"job":item}

@app.get("/api/v1/jobs/{job_id}/file")
async def get_file(job_id: str, request: Request, _: None = Depends(require_token)):
    store, settings = request.app.state.store, request.app.state.settings
    item = await asyncio.to_thread(store.get, job_id)
    if not item: raise HTTPException(404, "کار پیدا نشد.")
    raw = await asyncio.to_thread(_get_private_path, store, job_id)
    if item["status"] != "succeeded" or not raw: raise HTTPException(409, "فایل هنوز آماده دریافت نیست.")
    path = Path(raw).resolve()
    if settings.download_dir not in path.parents or not path.is_file(): raise HTTPException(404, "فایل در دسترس نیست.")
    return FileResponse(path, filename=item.get("filename") or path.name, media_type="application/octet-stream")

def _get_private_path(store, job_id):
    import sqlite3
    with sqlite3.connect(store.path) as db:
        row = db.execute("SELECT file_path FROM jobs WHERE id=?", (job_id,)).fetchone()
        return row[0] if row else None
