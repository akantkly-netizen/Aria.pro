import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run("aria_core.api:app", host=os.getenv("ARIA_HOST", "0.0.0.0"), port=int(os.getenv("PORT", os.getenv("ARIA_PORT", "8000"))), workers=1, proxy_headers=False)
