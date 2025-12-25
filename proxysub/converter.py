from __future__ import annotations

import re
from typing import Any

TEST_URL = "https://www.gstatic.com/generate_204"
WEST_COWBOY_GROUP_NAME = "西部牛仔"
LEGACY_DIALER_GROUP_NAME = "dialer-group"
DEFAULT_WEST_COWBOY_EXPECTED_STATUS = 407

_US_TOKEN_RE = re.compile(r"(^|[^A-Za-z0-9])US([^A-Za-z0-9]|$)", re.IGNORECASE)


def apply_profile_script(
    config: Any,
    *,
    us_home_proxy_name: str,
    west_cowboy_url_override: str | None = None,
    west_cowboy_expected_status_override: str | int | None = None,
) -> Any:
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
    default_west_cowboy_url = _build_http_probe_url_from_proxy(us_home_proxy)

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

    existing_url = west_cowboy_group.get("url")
    if isinstance(west_cowboy_url_override, str) and west_cowboy_url_override.strip():
        west_cowboy_group["url"] = west_cowboy_url_override.strip()
    elif isinstance(existing_url, str) and existing_url.strip():
        west_cowboy_group["url"] = existing_url.strip()
    elif isinstance(default_west_cowboy_url, str) and default_west_cowboy_url.strip():
        west_cowboy_group["url"] = default_west_cowboy_url
    else:
        west_cowboy_group["url"] = TEST_URL

    existing_expected_status = west_cowboy_group.get("expected-status")
    if (
        isinstance(west_cowboy_expected_status_override, (str, int))
        and str(west_cowboy_expected_status_override).strip()
    ):
        west_cowboy_group["expected-status"] = west_cowboy_expected_status_override
    elif isinstance(existing_expected_status, (str, int)) and str(existing_expected_status).strip():
        west_cowboy_group["expected-status"] = existing_expected_status
    else:
        west_cowboy_group["expected-status"] = DEFAULT_WEST_COWBOY_EXPECTED_STATUS

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
        west_cowboy_group.pop("filter", None)
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


def _build_http_probe_url_from_proxy(proxy: dict[str, Any] | None) -> str | None:
    if not isinstance(proxy, dict):
        return None

    server = proxy.get("server")
    if not isinstance(server, str) or not server.strip():
        return None
    host = server.strip()
    if ":" in host and not host.startswith("[") and not host.endswith("]"):
        host = f"[{host}]"

    port_value = proxy.get("port")
    if isinstance(port_value, bool):
        return None
    if isinstance(port_value, int):
        port = port_value
    elif isinstance(port_value, str) and port_value.strip().isdigit():
        port = int(port_value.strip())
    else:
        return None

    if port <= 0 or port > 65535:
        return None

    return f"http://{host}:{port}/"


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
