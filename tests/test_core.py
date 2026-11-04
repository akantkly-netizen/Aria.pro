import tempfile
from pathlib import Path
import pytest
from aria_core.database import JobStore
from aria_core.config import Settings
from aria_core.security import validate_media_url

def test_job_lifecycle_and_cancel():
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(Path(tmp)/"jobs.sqlite3")
        item = store.create("abc", "https://youtu.be/example", "best")
        assert item["status"] == "queued"
        assert store.claim() == "abc"
        store.progress("abc", 42, 420, 1000, "1 MB/s", "clip.mp4")
        assert store.get("abc")["progress"] == 42
        store.request_cancel("abc")
        assert store.cancelled("abc")
        store.fail("abc", "cancelled", True)
        assert store.get("abc")["status"] == "cancelled"

def test_queued_cancel():
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(Path(tmp)/"jobs.sqlite3")
        store.create("abc", "https://youtu.be/example", "best")
        assert store.request_cancel("abc")["status"] == "cancelled"

def test_settings_require_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIA_API_TOKEN", "x"*40)
    monkeypatch.setenv("ARIA_DATA_DIR", str(tmp_path))
    assert Settings.from_env().database_path == tmp_path / "aria.sqlite3"
    monkeypatch.setenv("ARIA_API_TOKEN", "short")
    with pytest.raises(RuntimeError): Settings.from_env()

@pytest.mark.parametrize("url", ["http://youtube.com/watch?v=x", "https://127.0.0.1/x", "https://evil.example/video", "https://user:pass@youtube.com/watch?v=x"])
def test_rejects_unsafe_urls(url):
    with pytest.raises(ValueError): validate_media_url(url)


def test_api_health_and_auth(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from aria_core.api import app
    monkeypatch.setenv("ARIA_API_TOKEN", "z"*48)
    monkeypatch.setenv("ARIA_DATA_DIR", str(tmp_path))
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/api/v1/jobs").status_code == 401
        response = client.get("/api/v1/jobs", headers={"Authorization":"Bearer "+"z"*48})
        assert response.status_code == 200 and response.json()["count"] == 0


def test_running_job_recovered_after_restart():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/"jobs.sqlite3"
        store = JobStore(path)
        store.create("abc", "https://youtu.be/example", "best")
        assert store.claim() == "abc"
        recovered = JobStore(path)
        assert recovered.get("abc")["status"] == "queued"

def test_url_allowlist_with_public_dns(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(None,None,None,None,("142.250.72.14",443))])
    assert validate_media_url("https://www.youtube.com/watch?v=demo").startswith("https://")
