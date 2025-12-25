function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function htmlPage(body: string, options?: { title?: string }): string {
  const title = options?.title ?? "proxysub";

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(title)}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, 'Noto Sans', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; margin: 2rem; }
    .card { max-width: 860px; padding: 1.25rem 1.5rem; border: 1px solid #e5e7eb; border-radius: 12px; }
    code { background: #f3f4f6; padding: 0.12rem 0.35rem; border-radius: 6px; }
    pre { background: #f3f4f6; padding: 0.9rem 1rem; border-radius: 12px; overflow-x: auto; }
    pre code { background: transparent; padding: 0; }
    a { color: #2563eb; }
    .muted { color: #6b7280; }
  </style>
</head>
<body>
  <div class="card">
  ${body}
  </div>
</body>
</html>`;
}

export function htmlErrorPage(message: string): string {
  const safe = escapeHtml(message);
  return htmlPage(
    `<h2>生成失败</h2><pre><code>${safe}</code></pre><p><a href="/">返回</a></p>`,
    { title: "生成失败" },
  );
}

export function htmlSuccessPage(downloadUrl: string, ttlSeconds: number): string {
  const safeUrl = escapeHtml(downloadUrl);
  const ttlMinutes = Math.max(1, Math.floor(ttlSeconds / 60));

  return htmlPage(
    `<h2>生成成功</h2>
<p>一次性下载链接（复制粘贴）：</p>
<pre><code>${safeUrl}</code></pre>
<p><a href="${safeUrl}">点击下载</a></p>
<p class="muted">链接有效期 ${ttlMinutes} 分钟；下载一次后即失效。</p>
<p><a href="/">返回继续上传</a></p>`,
    { title: "生成成功" },
  );
}
