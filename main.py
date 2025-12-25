from __future__ import annotations

import secrets
import string
import time
from dataclasses import dataclass
from pathlib import Path

import markdown as markdown_lib
import yaml
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from proxysub.builder import build_and_write_yaml_from_doc

APP_ROOT = Path(__file__).resolve().parent
DEFAULT_TEMPLATE_PATH = APP_ROOT / "templates" / "ryan.yaml"
DEFAULT_TEMP_DIR = APP_ROOT / "temp"
DEFAULT_DOCS_MD_PATH = APP_ROOT / "docs" / "index.md"
_OUTPUT_TOKEN_ALPHABET = string.ascii_letters + string.digits
_ONE_TIME_DOWNLOAD_TTL_S = 3600

app = FastAPI(title="proxysub", version="0.1.0")


def _generate_short_token(length: int = 8) -> str:
    if length <= 0:
        raise ValueError("length must be > 0")
    return "".join(secrets.choice(_OUTPUT_TOKEN_ALPHABET) for _ in range(length))


@dataclass(frozen=True)
class _OneTimeDownload:
    path: Path
    created_at: float


_ONE_TIME_DOWNLOADS: dict[str, _OneTimeDownload] = {}


def _cleanup_one_time_downloads(*, now: float | None = None) -> None:
    if now is None:
        now = time.time()

    stale_tokens = [
        token for token, item in _ONE_TIME_DOWNLOADS.items() if now - item.created_at > _ONE_TIME_DOWNLOAD_TTL_S
    ]
    for token in stale_tokens:
        item = _ONE_TIME_DOWNLOADS.pop(token, None)
        if item is None:
            continue
        item.path.unlink(missing_ok=True)


def _reserve_one_time_download(*, temp_dir: Path, suffix: str = ".yaml") -> tuple[str, Path]:
    _cleanup_one_time_downloads()
    for _ in range(24):
        token = _generate_short_token(10)
        if token in _ONE_TIME_DOWNLOADS:
            continue
        path = temp_dir / f"{token}{suffix}"
        if path.exists():
            continue
        return token, path
    raise RuntimeError("failed to reserve one-time download slot")


def _html_page(*, body: str, title: str = "proxysub") -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
	  <style>
	    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, 'Noto Sans', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; margin: 2rem; }}
	    .card {{ max-width: 860px; padding: 1.25rem 1.5rem; border: 1px solid #e5e7eb; border-radius: 12px; }}
	    code {{ background: #f3f4f6; padding: 0.12rem 0.35rem; border-radius: 6px; }}
	    pre {{ background: #f3f4f6; padding: 0.9rem 1rem; border-radius: 12px; overflow-x: auto; }}
	    pre code {{ background: transparent; padding: 0; }}
	    input[type="file"] {{ margin: 0.75rem 0; }}
	    button {{ padding: 0.55rem 0.9rem; border-radius: 10px; border: 1px solid #d1d5db; background: #111827; color: white; cursor: pointer; }}
	    button:hover {{ opacity: 0.92; }}
	    a {{ color: #2563eb; }}
	    .muted {{ color: #6b7280; }}
	  </style>
</head>
<body>
  <div class="card">
  {body}
  </div>
</body>
	</html>"""


def _render_markdown(md_text: str) -> str:
    return markdown_lib.markdown(md_text, extensions=["fenced_code", "tables"], output_format="html5")


def _load_docs_markdown(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "（文档文件缺失）"


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    docs_html = _render_markdown(_load_docs_markdown(DEFAULT_DOCS_MD_PATH))
    body = (
        "<h2>proxysub</h2>"
        "<p class=\"muted\">上传配置 YAML（仅需要包含 <code>proxies</code> 与 <code>proxy-providers</code>），生成一次性短链下载。</p>"
        "<form action=\"/upload\" method=\"post\" enctype=\"multipart/form-data\">"
        "<div><input type=\"file\" name=\"file\" accept=\".yaml,.yml,application/x-yaml,text/yaml\" required></div>"
        "<button type=\"submit\">生成订阅</button>"
        "</form>"
        "<hr style=\"border:none;border-top:1px solid #e5e7eb;margin:1.25rem 0;\" />"
        f"<div class=\"md\">{docs_html}</div>"
    )
    return HTMLResponse(_html_page(body=body))


@app.post("/upload", response_class=HTMLResponse)
async def upload_subscription(request: Request, file: UploadFile = File(...)) -> HTMLResponse:
    raw = await file.read()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc

    token, output_path = _reserve_one_time_download(temp_dir=DEFAULT_TEMP_DIR)

    try:
        result = build_and_write_yaml_from_doc(
            template_path=DEFAULT_TEMPLATE_PATH,
            subs_doc=doc,
            output_path=output_path,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _ONE_TIME_DOWNLOADS[token] = _OneTimeDownload(path=result.output_path, created_at=time.time())
    download_path = f"/{token}.yaml"
    download_url = str(request.url_for("download_one_time_yaml", token=token))

    body = f"""
<h2>生成成功</h2>
<p>一次性下载链接（复制粘贴）：</p>
<pre><code>{download_url}</code></pre>
<p><a href="{download_path}">点击下载</a></p>
<p class="muted">链接有效期 {_ONE_TIME_DOWNLOAD_TTL_S // 60} 分钟；下载一次后即失效。</p>
<p><a href="/">返回继续上传</a></p>
"""
    return HTMLResponse(_html_page(body=body, title="生成成功"))


@app.get("/{token}.yaml")
def download_one_time_yaml(token: str, background_tasks: BackgroundTasks) -> FileResponse:
    _cleanup_one_time_downloads()

    item = _ONE_TIME_DOWNLOADS.pop(token, None)
    if item is None or not item.path.exists():
        raise HTTPException(status_code=404, detail="Not found or already downloaded")

    background_tasks.add_task(item.path.unlink, missing_ok=True)
    return FileResponse(
        path=item.path,
        media_type="application/x-yaml",
        filename=item.path.name,
        background=background_tasks,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
