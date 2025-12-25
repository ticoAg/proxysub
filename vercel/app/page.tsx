import fs from "node:fs";
import path from "node:path";

import { marked } from "marked";

export const dynamic = "force-static";

const TEMPLATE_SOURCE_URL = "https://linux.do/t/topic/1282245";
const PROJECT_GITHUB_URL = "https://github.com/ticoAg/proxysub";

function loadDocsMarkdown(): string {
  try {
    return fs.readFileSync(path.join(process.cwd(), "docs", "index.md"), "utf8");
  } catch {
    return "（文档文件缺失）";
  }
}

function getDeployCommit(): string {
  for (const key of [
    "VERCEL_GIT_COMMIT_SHA",
    "GITHUB_SHA",
    "COMMIT_SHA",
    "DEPLOY_COMMIT_SHA",
    "SOURCE_VERSION",
  ] as const) {
    const value = process.env[key]?.trim();
    if (value) return value;
  }
  return "unknown";
}

export default function Page() {
  const docsHtml = marked.parse(loadDocsMarkdown());
  const commit = getDeployCommit();
  const commitShort = commit === "unknown" ? commit : commit.slice(0, 7);

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

      <p className="muted">
        模板下载：{" "}
        <a href="/templates/ryan.yaml" download>
          templates/ryan.yaml
        </a>{" "}
        （最终配置基于此模板生成；来源：{" "}
        <a href={TEMPLATE_SOURCE_URL} target="_blank" rel="noreferrer">
          {TEMPLATE_SOURCE_URL}
        </a>
        ）
      </p>
      <p className="muted">
        项目地址：{" "}
        <a href={PROJECT_GITHUB_URL} target="_blank" rel="noreferrer">
          {PROJECT_GITHUB_URL}
        </a>
        ；部署版本：<code title={commit}>{commitShort}</code>
      </p>
      <p className="muted">
        免责声明：本项目仅供学习与交流使用；请遵守当地法律法规；因使用本项目/配置导致的任何后果由使用者自行承担。
      </p>

      <hr />
      <div className="md" dangerouslySetInnerHTML={{ __html: docsHtml }} />
    </>
  );
}
