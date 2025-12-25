import YAML from "yaml";
import { Redis } from "@upstash/redis";

import { buildConfigFromDoc, dumpYaml } from "../../../lib/convert";
import { htmlErrorPage, htmlSuccessPage } from "../../../lib/html";
import { generateShortToken } from "../../../lib/token";

export const runtime = "edge";
export const dynamic = "force-dynamic";

let _redis: Redis | null = null;
function getRedis(): Redis {
  if (_redis) return _redis;
  _redis = Redis.fromEnv();
  return _redis;
}

const TEMPLATE_PATH = "/templates/ryan.yaml";
const DEFAULT_ONE_TIME_TTL_S = 180;

let _templateTextCache: string | null = null;

function getTtlSeconds(): number {
  const raw = (process.env.ONE_TIME_DOWNLOAD_TTL_S ?? "").trim();
  if (!raw) return DEFAULT_ONE_TIME_TTL_S;
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n) || n <= 0) return DEFAULT_ONE_TIME_TTL_S;
  return n;
}

function getPublicOrigin(request: Request): string {
  const configured = (process.env.PUBLIC_BASE_URL ?? "").trim();
  if (configured) return configured.replace(/\/+$/, "");
  return new URL(request.url).origin;
}

async function loadTemplateText(origin: string): Promise<string> {
  if (_templateTextCache) return _templateTextCache;
  const resp = await fetch(new URL(TEMPLATE_PATH, origin));
  if (!resp.ok) {
    throw new Error(`Template missing: ${resp.status} ${resp.statusText}`);
  }
  _templateTextCache = await resp.text();
  return _templateTextCache;
}

export async function POST(request: Request): Promise<Response> {
  try {
    const form = await request.formData();
    const file = form.get("file");
    if (!(file instanceof File)) {
      return new Response(htmlErrorPage("缺少上传文件：file"), {
        status: 400,
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }

    const subsText = await file.text();
    let subsDoc: unknown;
    try {
      subsDoc = YAML.parse(subsText);
    } catch (err) {
      return new Response(htmlErrorPage(`Invalid YAML: ${String(err)}`), {
        status: 400,
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }

    const origin = getPublicOrigin(request);
    const templateText = await loadTemplateText(origin);
    const config = buildConfigFromDoc({ templateText, subsDoc });
    const outputYaml = dumpYaml(config);

    const ttlSeconds = getTtlSeconds();
    const token = generateShortToken(10);
    await getRedis().set(`ot:${token}`, outputYaml, { ex: ttlSeconds });

    const downloadUrl = new URL(`/api/d/${token}`, origin).toString();
    return new Response(htmlSuccessPage(downloadUrl, ttlSeconds), {
      headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
    });
  } catch (err) {
    return new Response(htmlErrorPage(String(err)), {
      status: 500,
      headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
    });
  }
}
