import fs from "node:fs";
import path from "node:path";

import { marked } from "marked";

export const dynamic = "force-static";

function loadDocsMarkdown(): string {
  try {
    return fs.readFileSync(path.join(process.cwd(), "docs", "index.md"), "utf8");
  } catch {
    return "（文档文件缺失）";
  }
}

export default function Page() {
  const docsHtml = marked.parse(loadDocsMarkdown());

  return (
    <>
      <h2>proxysub</h2>
      <p className="muted">
        上传配置 YAML（仅需要包含 <code>proxies</code> 与 <code>proxy-providers</code>），生成一次性短链下载。
      </p>
      <form action="/api/upload" method="post" encType="multipart/form-data">
        <div>
          <input type="file" name="file" accept=".yaml,.yml,application/x-yaml,text/yaml" required />
        </div>
        <button type="submit">生成订阅</button>
      </form>

      <hr />
      <div className="md" dangerouslySetInnerHTML={{ __html: docsHtml }} />
    </>
  );
}
