from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from proxysub.converter import apply_profile_script
from proxysub.subscriptions import (
    SubsConfig,
    load_subs_config,
    parse_subs_config,
)
from proxysub.yamlio import FlowSeq, load_yaml_file, write_yaml_atomic


@dataclass(frozen=True)
class BuildResult:
    config: dict[str, Any]
    output_path: Path
    subs_config: SubsConfig


def build_config(*, template_path: Path, subs_path: Path) -> tuple[dict[str, Any], SubsConfig]:
    template_doc = load_yaml_file(template_path)
    if template_doc is None:
        template_doc = {}
    if not isinstance(template_doc, dict):
        raise ValueError(f"Template must be a YAML mapping, got {type(template_doc).__name__}")

    subs_config = load_subs_config(subs_path)

    _apply_subs_config(template_doc, subs_config)

    return template_doc, subs_config


def build_config_from_doc(
    *,
    template_path: Path,
    subs_doc: Any,
) -> tuple[dict[str, Any], SubsConfig]:
    template_doc = load_yaml_file(template_path)
    if template_doc is None:
        template_doc = {}
    if not isinstance(template_doc, dict):
        raise ValueError(f"Template must be a YAML mapping, got {type(template_doc).__name__}")

    subs_config = parse_subs_config(subs_doc)
    _apply_subs_config(template_doc, subs_config)
    return template_doc, subs_config


def build_and_write_yaml(
    *,
    template_path: Path,
    subs_path: Path,
    output_path: Path,
) -> BuildResult:
    config, subs_config = build_config(template_path=template_path, subs_path=subs_path)
    write_yaml_atomic(config, output_path)
    return BuildResult(config=config, output_path=output_path, subs_config=subs_config)


def build_and_write_yaml_from_doc(
    *,
    template_path: Path,
    subs_doc: Any,
    output_path: Path,
) -> BuildResult:
    config, subs_config = build_config_from_doc(template_path=template_path, subs_doc=subs_doc)
    write_yaml_atomic(config, output_path)
    return BuildResult(config=config, output_path=output_path, subs_config=subs_config)


def _apply_subs_config(template_doc: dict[str, Any], subs_config: SubsConfig) -> None:
    template_doc["proxies"] = _dedupe_proxies_by_name(list(subs_config.proxies))

    proxy_providers, provider_names = _resolve_proxy_providers(template_doc.get("proxy-providers"), subs_config)
    template_doc["proxy-providers"] = proxy_providers
    _sync_group_use_fields(template_doc.get("proxy-groups"), provider_names)

    apply_profile_script(
        template_doc,
        us_home_proxy_name=subs_config.us_home_proxy_name,
        west_cowboy_url_override=subs_config.west_cowboy_url,
        west_cowboy_expected_status_override=subs_config.west_cowboy_expected_status,
    )
    _flowify_proxy_group_lists(template_doc.get("proxy-groups"))


def _dedupe_proxies_by_name(proxies: list[Any]) -> list[dict[str, Any]]:
    seen_names: set[str] = set()
    out: list[dict[str, Any]] = []
    for proxy in proxies:
        if not isinstance(proxy, dict):
            continue
        name = proxy.get("name")
        if not isinstance(name, str):
            continue
        name = name.strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        out.append(proxy)
    return out


def _build_proxy_providers(
    existing_proxy_providers: Any,
    subs: list[str],
) -> tuple[dict[str, Any], list[str]]:
    existing = existing_proxy_providers if isinstance(existing_proxy_providers, dict) else {}
    existing_names = [name for name in existing.keys() if isinstance(name, str) and name.strip()]

    default_provider: dict[str, Any] | None = None
    for name in existing_names:
        provider = existing.get(name)
        if isinstance(provider, dict):
            default_provider = provider
            break

    out: dict[str, Any] = {}
    provider_names: list[str] = []

    for idx, url in enumerate(subs, start=1):
        provider_name = existing_names[idx - 1] if idx - 1 < len(existing_names) else f"订阅{idx}"
        provider_names.append(provider_name)

        base = existing.get(provider_name)
        if not isinstance(base, dict):
            base = default_provider if isinstance(default_provider, dict) else {}

        provider = deepcopy(base)
        provider.setdefault("type", "http")
        provider.setdefault("interval", 3600)
        provider.setdefault(
            "health-check",
            {
                "enable": True,
                "url": "https://www.gstatic.com/generate_204",
                "interval": 300,
                "lazy": True,
            },
        )

        provider["url"] = url
        if provider_name in existing and isinstance(existing.get(provider_name), dict):
            if not isinstance(provider.get("path"), str) or not provider.get("path", "").strip():
                provider["path"] = f"./providers/sub{idx}.yaml"
        else:
            provider["path"] = f"./providers/sub{idx}.yaml"
        out[provider_name] = provider

    return out, provider_names


def _resolve_proxy_providers(
    existing_proxy_providers: Any,
    subs_config: SubsConfig,
) -> tuple[dict[str, Any], list[str]]:
    if subs_config.proxy_providers:
        return _normalize_proxy_providers(subs_config.proxy_providers)
    return _build_proxy_providers(existing_proxy_providers, subs_config.proxy_provider_urls)


def _normalize_proxy_providers(
    raw_proxy_providers: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    out: dict[str, Any] = {}
    provider_names: list[str] = []

    for idx, (raw_name, raw_provider) in enumerate(raw_proxy_providers.items(), start=1):
        if not isinstance(raw_name, str):
            continue
        name = raw_name.strip()
        if not name:
            continue

        if not isinstance(raw_provider, dict):
            continue

        provider = deepcopy(raw_provider)
        provider.setdefault("type", "http")
        provider.setdefault("interval", 3600)
        provider.setdefault(
            "health-check",
            {
                "enable": True,
                "url": "https://www.gstatic.com/generate_204",
                "interval": 300,
                "lazy": True,
            },
        )

        url = provider.get("url")
        if isinstance(url, str):
            provider["url"] = url.strip()

        if not isinstance(provider.get("path"), str) or not provider.get("path", "").strip():
            provider["path"] = f"./providers/sub{idx}.yaml"

        provider_names.append(name)
        out[name] = provider

    return out, provider_names


def _sync_group_use_fields(proxy_groups: Any, provider_names: list[str]) -> None:
    if not isinstance(proxy_groups, list):
        return
    for group in proxy_groups:
        if not isinstance(group, dict):
            continue
        if "use" in group:
            group["use"] = list(provider_names)


def _flowify_proxy_group_lists(proxy_groups: Any) -> None:
    if not isinstance(proxy_groups, list):
        return
    for group in proxy_groups:
        if not isinstance(group, dict):
            continue
        for key in ("proxies", "use"):
            value = group.get(key)
            if isinstance(value, list) and not isinstance(value, FlowSeq):
                group[key] = FlowSeq(value)
