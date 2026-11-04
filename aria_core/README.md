# Aria Pro — Media Job API

یک سرویس مستقل و قابل استقرار برای صف‌بندی و مدیریت دانلود رسانه در کنار Userbot فعلی Aria. این سرویس جایگزین `main.py` نیست و اجرای فعلی ربات را تغییر نمی‌دهد.

## قابلیت‌های عملیاتی

- API مبتنی بر FastAPI با مستندات OpenAPI در `/docs`
- صف پایدار SQLite با WAL؛ کارهای در صف پس از Restart باقی می‌مانند
- Workerهای هم‌زمان قابل تنظیم، نوار پیشرفت، لغو کار و بازیابی کارهای نیمه‌تمام
- کیفیت‌های best، 720p، 480p و استخراج MP3
- محدودیت حجم فایل، timeout و retry
- احراز هویت Bearer Token و مقایسه امن توکن
- محدودسازی دامنه‌ها به منابع پشتیبانی‌شده و رد مقصدهای IP خصوصی برای کاهش ریسک SSRF
- Docker غیر root، فایل‌سیستم فقط‌خواندنی، healthcheck و volume پایدار

## اجرا با Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-api.txt
export ARIA_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python -m aria_core
```

Windows PowerShell: به‌جای `source` از `.venv\Scripts\Activate.ps1` استفاده کن.

## اجرا با Docker Compose

```bash
export ARIA_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
docker compose -f docker-compose.api.yml up -d --build
```

سرویس به‌صورت پیش‌فرض فقط روی loopback میزبان منتشر می‌شود. برای دسترسی عمومی، آن را پشت Reverse Proxy با TLS و محدودیت دسترسی قرار بده؛ پورت را مستقیماً روی اینترنت باز نکن.

## ابزار خط فرمان (CLI)

بعد از تنظیم `ARIA_API_TOKEN` می‌توانی بدون ساخت درخواست‌های curl کارها را مدیریت کنی:

```bash
python -m aria_core.client submit "https://www.youtube.com/watch?v=VIDEO_ID" --quality 720p
python -m aria_core.client list
python -m aria_core.client status JOB_ID
python -m aria_core.client cancel JOB_ID
python -m aria_core.client download JOB_ID --output ./media
```

برای تغییر نشانی سرویس از `ARIA_SERVER` یا گزینه `--server` استفاده کن. دریافت فایل به‌صورت streaming انجام می‌شود تا فایل‌های حجیم در RAM بارگذاری کامل نشوند.

## API

تمام مسیرهای `/api/v1` به هدر زیر نیاز دارند:

```http
Authorization: Bearer YOUR_ARIA_API_TOKEN
```

### ایجاد کار

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs \
  -H "Authorization: Bearer $ARIA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=VIDEO_ID","quality":"720p"}'
```

کیفیت‌های قابل قبول: `best`، `720p`، `480p` و `audio`. پاسخ شامل شناسه کار و مسیرهای پیگیری و دریافت فایل است.

### پیگیری، لغو و دریافت

- `GET /api/v1/jobs/{id}` — وضعیت و پیشرفت
- `GET /api/v1/jobs?limit=25` — فهرست کارها
- `DELETE /api/v1/jobs/{id}` — لغو کار
- `GET /api/v1/jobs/{id}/file` — دریافت فایل پس از تکمیل
- `GET /health` — سلامت سرویس (بدون احراز هویت)

## تنظیمات

| متغیر | کاربرد | پیش‌فرض |
|---|---|---|
| `ARIA_API_TOKEN` | کلید دسترسی؛ حداقل ۳۲ نویسه | اجباری |
| `ARIA_WORKERS` | تعداد Workerها (۱ تا ۸) | `2` |
| `ARIA_MAX_FILE_SIZE_MB` | سقف حجم خروجی (۵۰ تا ۱۹۰۰ مگابایت) | `1900` |
| `ARIA_DATA_DIR` | مسیر پایگاه داده و داده‌ها | `./data` |
| `ARIA_DOWNLOAD_DIR` | مسیر فایل‌های خروجی | `./data/downloads` |
| `ARIA_PORT` / `PORT` | پورت HTTP | `8000` |

## توسعه و تست

```bash
pip install -r requirements-api.txt
pytest -q
```

> این API فقط برای رسانه‌هایی طراحی شده که مجاز به دریافت آن‌ها هستی. رعایت قوانین پلتفرم و حقوق ناشر بر عهده استفاده‌کننده است.
