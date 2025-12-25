from __future__ import annotations

import re
from typing import Any

TEST_URL = "https://www.gstatic.com/generate_204"
WEST_COWBOY_GROUP_NAME = "西部牛仔"
LEGACY_DIALER_GROUP_NAME = "dialer-group"

_US_TOKEN_RE = re.compile(r"(^|[^A-Za-z0-9])US([^A-Za-z0-9]|$)", re.IGNORECASE)


def apply_profile_script(config: Any, *, us_home_proxy_name: str) -> Any:
    """Python port of `ref_scripts/scripts.js`.

    Mutates and returns `config` (a Clash/Mihomo config dict).
    """
    if not isinstance(config, dict):
        return config

    if not isinstance(us_home_proxy_name, str) or not us_home_proxy_name.strip():
        raise ValueError("us_home_proxy_name must be a non-empty string")
    us_home_proxy_name = us_home_proxy_name.strip()

    proxy_groups_key = "proxy-groups"
    if not isinstance(config.get(proxy_groups_key), list):
        config[proxy_groups_key] = []
    proxy_groups: list[Any] = config[proxy_groups_key]

    proxies_key = "proxies"
    if not isinstance(config.get(proxies_key), list):
        config[proxies_key] = []
    proxies: list[Any] = config[proxies_key]

    us_home_proxy = _find_proxy(proxies, us_home_proxy_name)
    if us_home_proxy is not None:
        us_home_proxy["dialer-proxy"] = WEST_COWBOY_GROUP_NAME

    manual_proxy_names = _uniq_strings(
        [
            p.get("name")
            for p in proxies
            if isinstance(p, dict) and isinstance(p.get("name"), str) and p.get("name").strip()
        ]
    )

    proxy_providers = config.get("proxy-providers")
    provider_names = (
        list(proxy_providers.keys())
        if isinstance(proxy_providers, dict) and not isinstance(proxy_providers, list)
        else []
    )

    matched_manual_proxy_names = [name for name in manual_proxy_names if _is_west_cowboy_node(name, us_home_proxy_name)]

    west_cowboy_group = _get_group(proxy_groups, WEST_COWBOY_GROUP_NAME)
    if west_cowboy_group is None:
        west_cowboy_group = {"name": WEST_COWBOY_GROUP_NAME}
        proxy_groups.append(west_cowboy_group)

    west_cowboy_group["type"] = "url-test"
    west_cowboy_group["url"] = TEST_URL
    if not isinstance(west_cowboy_group.get("interval"), int):
        west_cowboy_group["interval"] = 300

    if provider_names:
        if matched_manual_proxy_names:
            west_cowboy_group["proxies"] = _uniq_strings(
                [name for name in matched_manual_proxy_names if name not in {"DIRECT", "REJECT"}]
            )
        else:
            west_cowboy_group.pop("proxies", None)
        west_cowboy_group["use"] = provider_names
        west_cowboy_group["filter"] = "美国|US"
    elif matched_manual_proxy_names:
        west_cowboy_group["proxies"] = _uniq_strings(
            [name for name in matched_manual_proxy_names if name not in {"DIRECT", "REJECT"}]
        )
        west_cowboy_group.pop("use", None)
        west_cowboy_group.pop("filter", None)
    else:
        west_cowboy_group["proxies"] = []
        west_cowboy_group.pop("use", None)
        west_cowboy_group.pop("filter", None)

    for group in proxy_groups:
        if not isinstance(group, dict):
            continue
        if group.get("name") == WEST_COWBOY_GROUP_NAME:
            continue
        group_proxies = group.get("proxies")
        if not isinstance(group_proxies, list):
            continue
        group["proxies"] = _uniq_strings([p for p in group_proxies if isinstance(p, str)])
        if us_home_proxy_name not in group["proxies"]:
            group["proxies"].append(us_home_proxy_name)

    dialer_group_still_used = any(
        isinstance(p, dict) and p.get("dialer-proxy") == LEGACY_DIALER_GROUP_NAME for p in proxies
    ) or any(
        isinstance(g, dict) and LEGACY_DIALER_GROUP_NAME in _ensure_list(g.get("proxies")) for g in proxy_groups
    )
    if not dialer_group_still_used:
        proxy_groups[:] = [
            g
            for g in proxy_groups
            if not (isinstance(g, dict) and g.get("name") == LEGACY_DIALER_GROUP_NAME)
        ]

    return config


def _get_group(proxy_groups: list[Any], name: str) -> dict[str, Any] | None:
    for group in proxy_groups:
        if isinstance(group, dict) and group.get("name") == name:
            return group
    return None


def _find_proxy(proxies: list[Any], name: str) -> dict[str, Any] | None:
    for proxy in proxies:
        if isinstance(proxy, dict) and proxy.get("name") == name:
            return proxy
    return None


def _ensure_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _uniq_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _is_west_cowboy_node(name: str, us_home_proxy_name: str) -> bool:
    if name == us_home_proxy_name:
        return False
    if "美国" in name:
        return True
    return bool(_US_TOKEN_RE.search(name))
