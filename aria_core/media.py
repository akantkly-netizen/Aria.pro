import asyncio
import os
from pathlib import Path
from yt_dlp import YoutubeDL

class DownloadCancelled(Exception):
    pass

FORMATS = {
    "best": "bestvideo*+bestaudio/best",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "audio": "bestaudio/best",
}

async def download_media(job: dict, destination: Path, store, max_size_mb: int) -> tuple[str, str, dict]:
    destination.mkdir(parents=True, exist_ok=True)
    job_id = job["id"]
    loop = asyncio.get_running_loop()
    state = {"path": None, "info": {}}

    def run_download():
        def hook(data):
            if store.cancelled(job_id):
                raise DownloadCancelled("درخواست دانلود توسط کاربر لغو شد.")
            status = data.get("status")
            info = data.get("info_dict") or {}
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes") or 0
                percent = downloaded * 100 / total if total else 0
                speed_value = data.get("speed") or 0
                speed = f"{speed_value/1024/1024:.2f} MB/s" if speed_value else None
                store.progress(job_id, percent, downloaded, total or None, speed, info.get("filename"))
            elif status == "finished":
                state["path"] = data.get("filename") or info.get("filepath")
                state["info"] = info
                store.progress(job_id, 99.5, data.get("downloaded_bytes") or 0, data.get("total_bytes") or None, None, state["path"])

        options = {
            "format": FORMATS[job["quality"]],
            "outtmpl": str(destination / "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 20,
            "max_filesize": max_size_mb * 1024 * 1024,
            "progress_hooks": [hook],
            "restrictfilenames": True,
            "overwrites": False,
            "cachedir": False,
            "js_runtimes": {"node": {}},
        }
        if job["quality"] == "audio":
            options["format"] = FORMATS["audio"]
            options["postprocessors"] = [{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]
        with YoutubeDL(options) as ydl:
            ydl.download([job["url"]])
        path = state["path"]
        if not path:
            candidates = [p for p in destination.iterdir() if p.is_file() and not p.name.endswith(('.part','.ytdl'))]
            if not candidates: raise RuntimeError("فایل خروجی پس از دانلود پیدا نشد.")
            path = str(max(candidates, key=lambda p:p.stat().st_mtime))
        path = str(Path(path).resolve())
        if not Path(path).is_file():
            candidates = list(destination.glob('*'))
            candidates = [p for p in candidates if p.is_file()]
            if not candidates: raise RuntimeError("فایل نهایی ساخته نشد.")
            path = str(max(candidates,key=lambda p:p.stat().st_mtime))
        return path, Path(path).name, state["info"]

    return await asyncio.to_thread(run_download)
