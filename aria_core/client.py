import argparse
import json
import os
from pathlib import Path
import sys
import httpx

def main():
    parser = argparse.ArgumentParser(description="Aria Pro API command line client")
    parser.add_argument("--server", default=os.getenv("ARIA_SERVER", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("ARIA_API_TOKEN", ""))
    sub = parser.add_subparsers(dest="command", required=True)
    submit = sub.add_parser("submit"); submit.add_argument("url"); submit.add_argument("--quality", choices=["best","720p","480p","audio"], default="best")
    status = sub.add_parser("status"); status.add_argument("job_id")
    cancel = sub.add_parser("cancel"); cancel.add_argument("job_id")
    listing = sub.add_parser("list"); listing.add_argument("--limit", type=int, default=25)
    download = sub.add_parser("download"); download.add_argument("job_id"); download.add_argument("--output", default=".")
    args = parser.parse_args()
    if len(args.token) < 32: parser.error("توکن معتبر را با --token یا ARIA_API_TOKEN تنظیم کن.")
    headers = {"Authorization": f"Bearer {args.token}"}
    base = args.server.rstrip("/")
    with httpx.Client(timeout=30, headers=headers, follow_redirects=False) as client:
        if args.command == "download":
            target = Path(args.output).expanduser().resolve(); target.mkdir(parents=True, exist_ok=True)
            with client.stream("GET", base+f"/api/v1/jobs/{args.job_id}/file") as response:
                if not response.is_success:
                    print(f"HTTP {response.status_code}: {response.read().decode(errors='replace')}", file=sys.stderr); return 1
                disposition = response.headers.get("content-disposition", "")
                filename = disposition.split("filename=")[-1].strip('"') or args.job_id
                path = target / Path(filename).name
                with path.open("wb") as output:
                    for chunk in response.iter_bytes(1024*1024): output.write(chunk)
            print(f"Saved: {path}"); return 0
        if args.command == "submit": response = client.post(base+"/api/v1/jobs", json={"url":args.url,"quality":args.quality})
        elif args.command == "status": response = client.get(base+f"/api/v1/jobs/{args.job_id}")
        elif args.command == "cancel": response = client.delete(base+f"/api/v1/jobs/{args.job_id}")
        else: response = client.get(base+"/api/v1/jobs", params={"limit":args.limit})
        if not response.is_success:
            print(f"HTTP {response.status_code}: {response.text}", file=sys.stderr); return 1
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
