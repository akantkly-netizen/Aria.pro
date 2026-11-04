import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_DOMAINS = ("youtube.com", "youtu.be", "youtube-nocookie.com", "instagram.com", "tiktok.com")

def validate_media_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 4096:
        raise ValueError("URL نامعتبر است یا بیش از حد طولانی است.")
    parsed = urlsplit(url.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("فقط لینک HTTPS معتبر پشتیبانی می‌شود.")
    host = parsed.hostname.lower().rstrip(".")
    if not any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS):
        raise ValueError("این دامنه در فهرست منابع پشتیبانی‌شده Aria نیست.")
    if parsed.port not in (None, 443):
        raise ValueError("پورت سفارشی مجاز نیست.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise ValueError("دامنه قابل resolve نیست.") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("آدرس مقصد عمومی و معتبر نیست.")
    return url.strip()
