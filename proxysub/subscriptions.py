from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

import yaml

from proxysub.yamlio import load_yaml_file


@dataclass(frozen=True)
class SubsConfig:
    subs: list[str]
    proxies: list[dict[str, Any]]

    @property
    def us_home_proxy_name(self) -> str:
        for proxy in self.proxies:
            name = proxy.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        raise ValueError("subs.yaml must contain at least one proxy with a non-empty 'name'")


def load_subs_config(path: Any) -> SubsConfig:
    doc = load_yaml_file(path)
    if doc is None:
        doc = {}
    if not isinstance(doc, dict):
        raise ValueError(f"subs.yaml must be a YAML mapping, got {type(doc).__name__}")

    raw_subs = doc.get("subs") or []
    subs = [s.strip() for s in raw_subs if isinstance(s, str) and s.strip()]

    raw_proxies = doc.get("proxies") or []
    proxies = [p for p in raw_proxies if isinstance(p, dict)]

    return SubsConfig(subs=subs, proxies=proxies)


def fetch_subscription_proxies(urls: list[str], *, timeout_s: int = 25) -> list[dict[str, Any]]:
    proxies: list[dict[str, Any]] = []
    errors: list[str] = []

    for url in urls:
        try:
            text = _fetch_text(url, timeout_s=timeout_s)
            doc = yaml.safe_load(text)
            proxies.extend(_extract_proxies(doc))
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    if not proxies and errors:
        preview = "\n".join(errors[:5])
        more = "" if len(errors) <= 5 else f"\n... ({len(errors) - 5} more)"
        raise RuntimeError(f"All subscription fetches failed:\n{preview}{more}")

    return proxies


def _fetch_text(url: str, *, timeout_s: int) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("subscription url must be a non-empty string")
    url = url.strip()

    req = Request(
        url,
        headers={
            "User-Agent": "proxysub/0.1",
            "Accept": "application/yaml,text/yaml,text/plain,*/*",
        },
    )
    with urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
    return data.decode("utf-8", errors="replace")


def _extract_proxies(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, dict):
        candidates = doc.get("proxies") or doc.get("payload") or []
    elif isinstance(doc, list):
        candidates = doc
    else:
        candidates = []

    if not isinstance(candidates, list):
        return []

    out: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        out.append(item)
    return out
