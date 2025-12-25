import YAML, { YAMLSeq } from "yaml";

const TEST_URL = "https://www.gstatic.com/generate_204";
const WEST_COWBOY_GROUP_NAME = "西部牛仔";
const LEGACY_DIALER_GROUP_NAME = "dialer-group";
const DEFAULT_WEST_COWBOY_EXPECTED_STATUS = 407;
const US_TOKEN_RE = /(^|[^A-Za-z0-9])US([^A-Za-z0-9]|$)/i;

type AnyDict = Record<string, unknown>;

type SubsConfig = {
  proxyProviderUrls: string[];
  proxyProviders: Record<string, AnyDict>;
  proxies: AnyDict[];
  westCowboyUrl?: string;
  westCowboyExpectedStatus?: string | number;
  usHomeProxyName: string;
};

function isPlainObject(value: unknown): value is AnyDict {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function deepClone<T>(value: T): T {
  if (typeof globalThis.structuredClone === "function") {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value)) as T;
}

function uniqStrings(values: unknown[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    if (typeof value !== "string") continue;
    if (seen.has(value)) continue;
    seen.add(value);
    out.push(value);
  }
  return out;
}

function parseSubsConfig(doc: unknown): SubsConfig {
  const root = doc ?? {};
  if (!isPlainObject(root)) {
    throw new Error(`Upload YAML must be a mapping, got ${typeof root}`);
  }

  let rawProxyProviders: unknown = root["proxy-providers"];
  if (rawProxyProviders === undefined) {
    rawProxyProviders = root["subs"];
  }

  const proxyProviderUrls: string[] = [];
  const proxyProviders: Record<string, AnyDict> = {};
  if (Array.isArray(rawProxyProviders)) {
    for (const entry of rawProxyProviders) {
      if (typeof entry !== "string") continue;
      const url = entry.trim();
      if (!url) continue;
      proxyProviderUrls.push(url);
    }
  } else if (isPlainObject(rawProxyProviders)) {
    for (const [rawName, rawProvider] of Object.entries(rawProxyProviders)) {
      const name = rawName.trim();
      if (!name) continue;
      if (isPlainObject(rawProvider)) {
        proxyProviders[name] = rawProvider;
      } else if (typeof rawProvider === "string") {
        proxyProviders[name] = { url: rawProvider.trim() };
      }
    }
  }

  const rawProxies = root["proxies"];
  const proxies: AnyDict[] = Array.isArray(rawProxies) ? rawProxies.filter(isPlainObject) : [];

  const westCowboy = (root["west-cowboy"] ?? root["west_cowboy"]) as unknown;
  let westCowboyUrl: string | undefined;
  let westCowboyExpectedStatus: string | number | undefined;
  if (isPlainObject(westCowboy)) {
    const rawUrl = (westCowboy["url"] ?? westCowboy["test-url"] ?? westCowboy["test_url"]) as unknown;
    if (typeof rawUrl === "string" && rawUrl.trim()) {
      westCowboyUrl = rawUrl.trim();
    }

    const rawExpected = (westCowboy["expected-status"] ?? westCowboy["expected_status"]) as unknown;
    if ((typeof rawExpected === "string" || typeof rawExpected === "number") && String(rawExpected).trim()) {
      westCowboyExpectedStatus = rawExpected;
    }
  }

  const usHomeProxyName =
    proxies
      .map((p) => (typeof p.name === "string" ? p.name.trim() : ""))
      .find((name) => name) ?? "";
  if (!usHomeProxyName) {
    throw new Error("Upload YAML must contain at least one proxy with a non-empty 'name'");
  }

  return {
    proxyProviderUrls,
    proxyProviders,
    proxies,
    westCowboyUrl,
    westCowboyExpectedStatus,
    usHomeProxyName,
  };
}

function dedupeProxiesByName(proxies: AnyDict[]): AnyDict[] {
  const seen = new Set<string>();
  const out: AnyDict[] = [];
  for (const proxy of proxies) {
    const name = typeof proxy.name === "string" ? proxy.name.trim() : "";
    if (!name) continue;
    if (seen.has(name)) continue;
    seen.add(name);
    out.push(proxy);
  }
  return out;
}

function normalizeProxyProviders(rawProxyProviders: Record<string, AnyDict>): [AnyDict, string[]] {
  const out: AnyDict = {};
  const names: string[] = [];
  let idx = 0;
  for (const [rawName, rawProvider] of Object.entries(rawProxyProviders)) {
    const name = rawName.trim();
    if (!name) continue;
    if (!isPlainObject(rawProvider)) continue;
    idx += 1;

    const provider = deepClone(rawProvider);
    if (provider.type === undefined) provider.type = "http";
    if (provider.interval === undefined) provider.interval = 3600;
    if (provider["health-check"] === undefined) {
      provider["health-check"] = { enable: true, url: TEST_URL, interval: 300, lazy: true };
    }

    if (typeof provider.url === "string") provider.url = provider.url.trim();

    if (typeof provider.path !== "string" || !provider.path.trim()) {
      provider.path = `./providers/sub${idx}.yaml`;
    }

    names.push(name);
    out[name] = provider;
  }
  return [out, names];
}

function buildProxyProviders(existingProxyProviders: unknown, subsUrls: string[]): [AnyDict, string[]] {
  const existing = isPlainObject(existingProxyProviders) ? existingProxyProviders : {};
  const existingNames = Object.keys(existing).filter((n) => n.trim());

  let defaultProvider: AnyDict | undefined;
  for (const name of existingNames) {
    const provider = existing[name];
    if (isPlainObject(provider)) {
      defaultProvider = provider;
      break;
    }
  }

  const out: AnyDict = {};
  const names: string[] = [];

  subsUrls.forEach((url, index) => {
    const idx = index + 1;
    const providerName = existingNames[index] ?? `订阅${idx}`;
    names.push(providerName);

    const existingBase = existing[providerName];
    const base = isPlainObject(existingBase) ? existingBase : defaultProvider ?? {};

    const provider = deepClone(base);
    if (provider.type === undefined) provider.type = "http";
    if (provider.interval === undefined) provider.interval = 3600;
    if (provider["health-check"] === undefined) {
      provider["health-check"] = { enable: true, url: TEST_URL, interval: 300, lazy: true };
    }

    provider.url = url;
    if (isPlainObject(existingBase)) {
      if (typeof provider.path !== "string" || !provider.path.trim()) {
        provider.path = `./providers/sub${idx}.yaml`;
      }
    } else {
      provider.path = `./providers/sub${idx}.yaml`;
    }

    out[providerName] = provider;
  });

  return [out, names];
}

function syncGroupUseFields(proxyGroups: unknown, providerNames: string[]): void {
  if (!Array.isArray(proxyGroups)) return;
  for (const group of proxyGroups) {
    if (!isPlainObject(group)) continue;
    if (Object.prototype.hasOwnProperty.call(group, "use")) {
      group.use = [...providerNames];
    }
  }
}

function ensureList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function findProxy(proxies: unknown[], name: string): AnyDict | undefined {
  for (const proxy of proxies) {
    if (!isPlainObject(proxy)) continue;
    if (proxy.name === name) return proxy;
  }
  return undefined;
}

function getGroup(proxyGroups: unknown[], name: string): AnyDict | undefined {
  for (const group of proxyGroups) {
    if (!isPlainObject(group)) continue;
    if (group.name === name) return group;
  }
  return undefined;
}

function buildHttpProbeUrlFromProxy(proxy: AnyDict | undefined): string | undefined {
  if (!proxy) return undefined;

  const server = proxy.server;
  if (typeof server !== "string" || !server.trim()) return undefined;
  let host = server.trim();
  if (host.includes(":") && !(host.startsWith("[") && host.endsWith("]"))) {
    host = `[${host}]`;
  }

  const portValue = proxy.port;
  let port: number | undefined;
  if (typeof portValue === "number" && Number.isInteger(portValue)) {
    port = portValue;
  } else if (typeof portValue === "string" && portValue.trim() && /^\d+$/.test(portValue.trim())) {
    port = Number.parseInt(portValue.trim(), 10);
  } else {
    return undefined;
  }

  if (!port || port <= 0 || port > 65535) return undefined;
  return `http://${host}:${port}/`;
}

function isWestCowboyNode(name: string, usHomeProxyName: string): boolean {
  if (name === usHomeProxyName) return false;
  if (name.includes("美国")) return true;
  return US_TOKEN_RE.test(name);
}

function applyProfileScript(
  config: AnyDict,
  options: {
    usHomeProxyName: string;
    westCowboyUrlOverride?: string;
    westCowboyExpectedStatusOverride?: string | number;
  },
): void {
  const { usHomeProxyName, westCowboyUrlOverride, westCowboyExpectedStatusOverride } = options;

  if (!Array.isArray(config["proxy-groups"])) config["proxy-groups"] = [];
  const proxyGroups = config["proxy-groups"] as unknown[];

  if (!Array.isArray(config.proxies)) config.proxies = [];
  const proxies = config.proxies as unknown[];

  const usHomeProxy = findProxy(proxies, usHomeProxyName);
  if (usHomeProxy) {
    usHomeProxy["dialer-proxy"] = WEST_COWBOY_GROUP_NAME;
  }
  const defaultWestCowboyUrl = buildHttpProbeUrlFromProxy(usHomeProxy);

  const manualProxyNames = uniqStrings(
    proxies
      .filter(isPlainObject)
      .map((p) => (typeof p.name === "string" && p.name.trim() ? p.name.trim() : undefined)),
  );

  const proxyProviders = config["proxy-providers"];
  const providerNames = isPlainObject(proxyProviders) ? Object.keys(proxyProviders) : [];

  const matchedManualProxyNames = manualProxyNames.filter((name) => isWestCowboyNode(name, usHomeProxyName));

  let westCowboyGroup = getGroup(proxyGroups, WEST_COWBOY_GROUP_NAME);
  if (!westCowboyGroup) {
    westCowboyGroup = { name: WEST_COWBOY_GROUP_NAME };
    proxyGroups.push(westCowboyGroup);
  }

  westCowboyGroup.type = "url-test";

  const existingUrl = westCowboyGroup.url;
  if (typeof westCowboyUrlOverride === "string" && westCowboyUrlOverride.trim()) {
    westCowboyGroup.url = westCowboyUrlOverride.trim();
  } else if (typeof existingUrl === "string" && existingUrl.trim()) {
    westCowboyGroup.url = existingUrl.trim();
  } else if (typeof defaultWestCowboyUrl === "string" && defaultWestCowboyUrl.trim()) {
    westCowboyGroup.url = defaultWestCowboyUrl;
  } else {
    westCowboyGroup.url = TEST_URL;
  }

  const existingExpectedStatus = westCowboyGroup["expected-status"];
  if (
    (typeof westCowboyExpectedStatusOverride === "string" || typeof westCowboyExpectedStatusOverride === "number") &&
    String(westCowboyExpectedStatusOverride).trim()
  ) {
    westCowboyGroup["expected-status"] = westCowboyExpectedStatusOverride;
  } else if (
    (typeof existingExpectedStatus === "string" || typeof existingExpectedStatus === "number") &&
    String(existingExpectedStatus).trim()
  ) {
    westCowboyGroup["expected-status"] = existingExpectedStatus;
  } else {
    westCowboyGroup["expected-status"] = DEFAULT_WEST_COWBOY_EXPECTED_STATUS;
  }

  if (typeof westCowboyGroup.interval !== "number" || !Number.isInteger(westCowboyGroup.interval)) {
    westCowboyGroup.interval = 300;
  }

  if (providerNames.length > 0) {
    if (matchedManualProxyNames.length > 0) {
      westCowboyGroup.proxies = uniqStrings(matchedManualProxyNames.filter((n) => n !== "DIRECT" && n !== "REJECT"));
    } else {
      delete westCowboyGroup.proxies;
    }
    westCowboyGroup.use = providerNames;
    delete westCowboyGroup.filter;
  } else if (matchedManualProxyNames.length > 0) {
    westCowboyGroup.proxies = uniqStrings(matchedManualProxyNames.filter((n) => n !== "DIRECT" && n !== "REJECT"));
    delete westCowboyGroup.use;
    delete westCowboyGroup.filter;
  } else {
    westCowboyGroup.proxies = [];
    delete westCowboyGroup.use;
    delete westCowboyGroup.filter;
  }

  for (const group of proxyGroups) {
    if (!isPlainObject(group)) continue;
    if (group.name === WEST_COWBOY_GROUP_NAME) continue;
    const groupProxies = group.proxies;
    if (!Array.isArray(groupProxies)) continue;

    group.proxies = uniqStrings(groupProxies.filter((p) => typeof p === "string"));
    if (group["include-all-proxies"] === true) continue;
    if (!(group.proxies as unknown[]).includes(usHomeProxyName)) {
      (group.proxies as unknown[]).push(usHomeProxyName);
    }
  }

  const dialerGroupStillUsed =
    proxies.some((p) => isPlainObject(p) && p["dialer-proxy"] === LEGACY_DIALER_GROUP_NAME) ||
    proxyGroups.some((g) => isPlainObject(g) && ensureList(g.proxies).includes(LEGACY_DIALER_GROUP_NAME));
  if (!dialerGroupStillUsed) {
    config["proxy-groups"] = proxyGroups.filter(
      (g) => !(isPlainObject(g) && g.name === LEGACY_DIALER_GROUP_NAME),
    );
  }
}

function toFlowSeq(values: unknown[]): YAMLSeq {
  const seq = new YAMLSeq();
  seq.flow = true;
  seq.items = values.map((v) => v as never);
  return seq;
}

function flowifyProxyGroupLists(proxyGroups: unknown): void {
  if (!Array.isArray(proxyGroups)) return;
  for (const group of proxyGroups) {
    if (!isPlainObject(group)) continue;
    for (const key of ["proxies", "use"] as const) {
      const value = group[key];
      if (Array.isArray(value)) {
        group[key] = toFlowSeq(value);
      }
    }
  }
}

export function buildConfigFromDoc(options: { templateText: string; subsDoc: unknown }): AnyDict {
  const { templateText, subsDoc } = options;
  const templateDoc = YAML.parse(templateText) ?? {};
  if (!isPlainObject(templateDoc)) {
    throw new Error("Template must be a YAML mapping");
  }

  const subsConfig = parseSubsConfig(subsDoc);
  templateDoc.proxies = dedupeProxiesByName([...subsConfig.proxies]);

  const existingProviders = templateDoc["proxy-providers"];
  const [proxyProviders, providerNames] =
    Object.keys(subsConfig.proxyProviders).length > 0
      ? normalizeProxyProviders(subsConfig.proxyProviders)
      : buildProxyProviders(existingProviders, subsConfig.proxyProviderUrls);
  templateDoc["proxy-providers"] = proxyProviders;

  syncGroupUseFields(templateDoc["proxy-groups"], providerNames);

  applyProfileScript(templateDoc, {
    usHomeProxyName: subsConfig.usHomeProxyName,
    westCowboyUrlOverride: subsConfig.westCowboyUrl,
    westCowboyExpectedStatusOverride: subsConfig.westCowboyExpectedStatus,
  });

  flowifyProxyGroupLists(templateDoc["proxy-groups"]);
  return templateDoc;
}

export function dumpYaml(doc: unknown): string {
  return YAML.stringify(doc, { sortMapEntries: false, flowCollectionPadding: false });
}
