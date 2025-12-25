from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class FlowSeq(list):
    """A list that should be emitted in YAML flow style (e.g. [a, b, c])."""


class _CustomDumper(yaml.SafeDumper):
    pass


def _represent_flow_seq(dumper: yaml.Dumper, data: FlowSeq) -> yaml.Node:  # type: ignore[name-defined]
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


_CustomDumper.add_representer(FlowSeq, _represent_flow_seq)


def load_yaml_file(path: Any) -> Any:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    return yaml.safe_load(text)


def dump_yaml(data: Any) -> str:
    return yaml.dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        Dumper=_CustomDumper,
    )


def write_yaml_atomic(data: Any, path: Any) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(dump_yaml(data), encoding="utf-8")
    tmp_path.replace(output_path)
    return output_path
