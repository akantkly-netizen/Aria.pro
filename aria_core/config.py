from dataclasses import dataclass
import os
from pathlib import Path

@dataclass(frozen=True)
class Settings:
    api_token: str
    data_dir: Path
    download_dir: Path
    database_path: Path
    workers: int = 2
    max_file_size_mb: int = 1900
    job_ttl_hours: int = 48

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("ARIA_DATA_DIR", "./data")).expanduser().resolve()
        download_dir = Path(os.getenv("ARIA_DOWNLOAD_DIR", str(data_dir / "downloads"))).expanduser().resolve()
        token = os.getenv("ARIA_API_TOKEN", "").strip()
        if len(token) < 32:
            raise RuntimeError("ARIA_API_TOKEN must be set to a random secret of at least 32 characters")
        workers = int(os.getenv("ARIA_WORKERS", "2"))
        max_size = int(os.getenv("ARIA_MAX_FILE_SIZE_MB", "1900"))
        if not 1 <= workers <= 8:
            raise RuntimeError("ARIA_WORKERS must be between 1 and 8")
        if not 50 <= max_size <= 1900:
            raise RuntimeError("ARIA_MAX_FILE_SIZE_MB must be between 50 and 1900")
        return cls(token, data_dir, download_dir, data_dir / "aria.sqlite3", workers, max_size)
