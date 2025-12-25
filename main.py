from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from proxysub.builder import build_and_write_yaml

APP_ROOT = Path(__file__).resolve().parent
DEFAULT_TEMPLATE_PATH = APP_ROOT / "templates" / "ryan.yaml"
DEFAULT_SUBS_PATH = APP_ROOT / "subs.yaml"
DEFAULT_TEMP_DIR = APP_ROOT / "temp"
DEFAULT_OUTPUT_PATH = DEFAULT_TEMP_DIR / "sub.yaml"

app = FastAPI(title="proxysub", version="0.1.0")


@app.get("/", response_class=PlainTextResponse)
def index() -> str:
    return "OK\nDownload: /sub.yaml\n"


@app.get("/sub.yaml")
def download_subscription() -> FileResponse:
    try:
        result = build_and_write_yaml(
            template_path=DEFAULT_TEMPLATE_PATH,
            subs_path=DEFAULT_SUBS_PATH,
            output_path=DEFAULT_OUTPUT_PATH,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FileResponse(
        path=result.output_path,
        media_type="application/x-yaml",
        filename="sub.yaml",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
