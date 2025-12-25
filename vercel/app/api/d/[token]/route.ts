import { Redis } from "@upstash/redis";

export const runtime = "edge";
export const dynamic = "force-dynamic";

let _redis: Redis | null = null;
function getRedis(): Redis {
  if (_redis) return _redis;
  _redis = Redis.fromEnv();
  return _redis;
}

export async function GET(_request: Request, ctx: { params: Promise<{ token: string }> }): Promise<Response> {
  const { token } = await ctx.params;
  const key = `ot:${token}`;

  const yamlText = await getRedis().get<string>(key);
  if (!yamlText) {
    return new Response("Not found or already downloaded", {
      status: 404,
      headers: { "cache-control": "no-store" },
    });
  }

  await getRedis().del(key);

  return new Response(yamlText, {
    headers: {
      "content-type": "application/x-yaml; charset=utf-8",
      "content-disposition": `attachment; filename="${token}.yaml"`,
      "cache-control": "no-store",
    },
  });
}
