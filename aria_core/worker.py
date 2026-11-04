import asyncio
import logging
import shutil
from pathlib import Path
from .media import download_media, DownloadCancelled

log = logging.getLogger("aria.worker")

class WorkerPool:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.tasks = []
        self.stopping = asyncio.Event()

    async def start(self):
        self.settings.download_dir.mkdir(parents=True, exist_ok=True)
        self.tasks = [asyncio.create_task(self._run(i), name=f"aria-worker-{i}") for i in range(self.settings.workers)]
        self.tasks.append(asyncio.create_task(self._maintenance(), name="aria-maintenance"))

    async def stop(self):
        self.stopping.set()
        for task in self.tasks: task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def _maintenance(self):
        while not self.stopping.is_set():
            try:
                expired = await asyncio.to_thread(self.store.prune, self.settings.job_ttl_hours)
                for raw_path in expired:
                    path = Path(raw_path).resolve()
                    if self.settings.download_dir in path.parents:
                        shutil.rmtree(path.parent, ignore_errors=True)
            except Exception:
                log.exception("retention cleanup failed")
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=3600)
            except asyncio.TimeoutError:
                pass

    async def _run(self, number):
        while not self.stopping.is_set():
            job_id = await asyncio.to_thread(self.store.claim)
            if not job_id:
                await asyncio.sleep(0.6)
                continue
            job = await asyncio.to_thread(self.store.get, job_id)
            folder = self.settings.download_dir / job_id
            try:
                path, filename, info = await download_media(job, folder, self.store, self.settings.max_file_size_mb)
                metadata = {k: info.get(k) for k in ("id","title","extractor","duration","width","height","webpage_url") if info.get(k) is not None}
                await asyncio.to_thread(self.store.finish, job_id, path, filename, metadata)
            except DownloadCancelled as exc:
                await asyncio.to_thread(self.store.fail, job_id, str(exc), True)
                shutil.rmtree(folder, ignore_errors=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("job %s failed", job_id)
                await asyncio.to_thread(self.store.fail, job_id, f"{type(exc).__name__}: {exc}")
                shutil.rmtree(folder, ignore_errors=True)
