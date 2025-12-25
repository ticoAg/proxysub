// Define main function (script entry)

function main(config, profileName) {
  if (!config || typeof config !== "object") return config;

  const TEST_URL = "https://www.gstatic.com/generate_204";
  const WEST_COWBOY_GROUP_NAME = "西部牛仔";
  const US_HOME_PROXY_NAME = "US-Home";
  const LEGACY_DIALER_GROUP_NAME = "dialer-group";

  const safeRequire = (mod) => {
    try {
      // eslint-disable-next-line no-undef
      return require(mod);
    } catch (_) {
      return null;
    }
  };

  const fs = safeRequire("fs");
  const path = safeRequire("path");

  const proxyGroupsKey = "proxy-groups";
  if (!Array.isArray(config[proxyGroupsKey])) config[proxyGroupsKey] = [];

  const proxyGroups = config[proxyGroupsKey];

  const getGroup = (name) =>
    proxyGroups.find((g) => g && typeof g === "object" && g.name === name);

  const ensureArray = (value) => (Array.isArray(value) ? value : []);

  const proxiesKey = "proxies";
  if (!Array.isArray(config[proxiesKey])) config[proxiesKey] = [];
  const proxies = config[proxiesKey];

  // Ensure US-Home uses 西部牛仔 as its dialer-proxy (avoid using legacy dialer-group).
  const usHomeProxy = proxies.find(
    (p) => p && typeof p === "object" && p.name === US_HOME_PROXY_NAME
  );
  if (usHomeProxy) {
    usHomeProxy["dialer-proxy"] = WEST_COWBOY_GROUP_NAME;
  }

  const readTextFile = (filePath) => {
    if (!fs || typeof fs.readFileSync !== "function") return null;
    if (typeof filePath !== "string" || filePath.trim() === "") return null;

    const candidates = [];
    candidates.push(filePath);
    if (filePath.startsWith("./")) candidates.push(filePath.slice(2));
    if (path && typeof path.resolve === "function") candidates.push(path.resolve(filePath));

    for (const p of candidates) {
      try {
        return fs.readFileSync(p, "utf8");
      } catch (_) {
        // ignore
      }
    }
    return null;
  };

  const extractProxyNamesFromYaml = (yamlText) => {
    if (typeof yamlText !== "string" || yamlText.trim() === "") return [];

    const lines = yamlText.split(/\r?\n/);
    let inProxies = false;
    let proxiesIndent = 0;
    const out = [];

    for (const line of lines) {
      const proxiesStart = line.match(/^(\s*)(proxies|payload)\s*:\s*$/);
      if (!inProxies && proxiesStart) {
        inProxies = true;
        proxiesIndent = proxiesStart[1].length;
        continue;
      }

      if (!inProxies) continue;
      if (/^\s*(#.*)?$/.test(line)) continue;

      const indent = (line.match(/^(\s*)/) || ["", ""])[1].length;
      if (indent <= proxiesIndent && /^[A-Za-z0-9_-]+\s*:/.test(line.trim())) {
        break;
      }

      const nameMatch = line.match(/\bname\s*:\s*([^,}#]+)/);
      if (!nameMatch) continue;

      let name = nameMatch[1].trim();
      name = name.replace(/^['"]|['"]$/g, "");
      if (name) out.push(name);
    }

    return out;
  };

  const uniq = (arr) => {
    const seen = new Set();
    const out = [];
    for (const item of arr) {
      if (typeof item !== "string") continue;
      if (seen.has(item)) continue;
      seen.add(item);
      out.push(item);
    }
    return out;
  };

  const isWestCowboyNode = (name) => {
    if (typeof name !== "string") return false;
    if (name === US_HOME_PROXY_NAME) return false;
    if (name.includes("美国")) return true;
    return /(^|[^A-Za-z0-9])US([^A-Za-z0-9]|$)/i.test(name);
  };

  const manualProxyNames = uniq(
    proxies
      .map((p) => (p && typeof p === "object" ? p.name : undefined))
      .filter((name) => typeof name === "string")
  );

  const proxyProviders = config["proxy-providers"];
  const providerNames =
    proxyProviders && typeof proxyProviders === "object" && !Array.isArray(proxyProviders)
      ? Object.keys(proxyProviders)
      : [];

  let providerFilesRead = 0;
  const providerProxyNames = [];
  for (const providerName of providerNames) {
    const provider = proxyProviders[providerName];
    if (!provider || typeof provider !== "object") continue;

    const providerPath = provider.path;
    const yamlText = readTextFile(providerPath);
    if (!yamlText) continue;
    providerFilesRead += 1;

    providerProxyNames.push(...extractProxyNamesFromYaml(yamlText));
  }

  const matchedManualProxyNames = manualProxyNames.filter(isWestCowboyNode);
  const matchedProviderProxyNames = uniq(providerProxyNames).filter(isWestCowboyNode);
  const matchedProxyNames = uniq([...matchedManualProxyNames, ...matchedProviderProxyNames]);

  // 1) Ensure "西部牛仔" (url-test) exists and is populated by matching proxies.
  let westCowboyGroup = getGroup(WEST_COWBOY_GROUP_NAME);
  if (!westCowboyGroup) {
    westCowboyGroup = { name: WEST_COWBOY_GROUP_NAME };
    proxyGroups.push(westCowboyGroup);
  }

  westCowboyGroup.type = "url-test";
  westCowboyGroup.url = TEST_URL;
  if (typeof westCowboyGroup.interval !== "number") westCowboyGroup.interval = 300;

  if (providerNames.length > 0 && providerFilesRead === 0) {
    // If we can't read provider files, fall back to using providers with a filter (supported by mihomo).
    if (matchedManualProxyNames.length > 0) {
      westCowboyGroup.proxies = uniq(matchedManualProxyNames).filter(
        (name) => name !== "DIRECT" && name !== "REJECT"
      );
    } else {
      delete westCowboyGroup.proxies;
    }
    westCowboyGroup.use = providerNames;
    westCowboyGroup.filter = "美国|US";
  } else if (matchedProxyNames.length > 0) {
    westCowboyGroup.proxies = matchedProxyNames.filter(
      (name) => name !== "DIRECT" && name !== "REJECT"
    );
    delete westCowboyGroup.use;
    delete westCowboyGroup.filter;
  } else {
    westCowboyGroup.proxies = [];
    delete westCowboyGroup.use;
    delete westCowboyGroup.filter;
  }

  // 2) Add US-Home as an option to all other groups (exclude 西部牛仔).
  for (const group of proxyGroups) {
    if (!group || typeof group !== "object") continue;
    if (group.name === WEST_COWBOY_GROUP_NAME) continue;
    if (!Array.isArray(group.proxies)) continue;

    group.proxies = uniq(ensureArray(group.proxies));
    if (!group.proxies.includes(US_HOME_PROXY_NAME)) {
      group.proxies.push(US_HOME_PROXY_NAME);
    }
  }

  // 3) Remove legacy dialer-group if nothing references it anymore.
  const dialerGroupStillUsed =
    proxies.some(
      (p) => p && typeof p === "object" && p["dialer-proxy"] === LEGACY_DIALER_GROUP_NAME
    ) ||
    proxyGroups.some((g) => {
      if (!g || typeof g !== "object") return false;
      return ensureArray(g.proxies).includes(LEGACY_DIALER_GROUP_NAME);
    });

  if (!dialerGroupStillUsed) {
    for (let i = proxyGroups.length - 1; i >= 0; i -= 1) {
      const group = proxyGroups[i];
      if (group && typeof group === "object" && group.name === LEGACY_DIALER_GROUP_NAME) {
        proxyGroups.splice(i, 1);
      }
    }
  }

  return config;
}