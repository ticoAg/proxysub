from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from proxysub.converter import apply_profile_script
from proxysub.subscriptions import (
    SubsConfig,
    fetch_subscription_proxies,
    load_subs_config,
)
from proxysub.yamlio import load_yaml_file, write_yaml_atomic


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

    subscription_proxies = fetch_subscription_proxies(subs_config.subs)
    merged_proxies = _dedupe_proxies_by_name([*subs_config.proxies, *subscription_proxies])

    template_doc["proxies"] = merged_proxies

    template_doc.pop("proxy-providers", None)
    _remove_group_use_fields(template_doc.get("proxy-groups"))

    apply_profile_script(template_doc, us_home_proxy_name=subs_config.us_home_proxy_name)

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


def _remove_group_use_fields(proxy_groups: Any) -> None:
    if not isinstance(proxy_groups, list):
        return
    for group in proxy_groups:
        if not isinstance(group, dict):
            continue
        group.pop("use", None)
