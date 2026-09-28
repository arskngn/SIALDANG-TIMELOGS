import sys
import uvicorn

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    uvicorn.run("app.app:app", host="127.0.0.1", port=8000, reload=True, log_level="info")
