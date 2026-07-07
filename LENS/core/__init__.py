"""core — LENS 계산/데이터 계층 (``core`` 자체가 pipeline binder). 설계는 README.

``__init__`` 은 config 진입점(경로 resolve + 로드)과 노출만 한다.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from python_toolbox.file import Make_dict_from

from ._base import MODEL_BUILDERS, Pipeline, Pipeline_config


# ── config 파일 기준 경로 resolve ─────────────────────────────────────────────

def _resolve(base: Path, p: str) -> str:
    """상대경로면 config 파일 위치 기준 절대경로로 변환한다."""
    _path = Path(p)
    return str(_path if _path.is_absolute() else (base / _path).resolve())


def _resolve_spec_path(base: Path, spec):
    """converter params 스펙(경로 문자열 또는 ``{pattern: path}``)의 경로를 resolve 한다."""
    if isinstance(spec, str):
        return _resolve(base, spec)
    if isinstance(spec, dict) and "pattern" in spec:
        _spec = dict(spec)
        _spec["pattern"] = _resolve(base, spec["pattern"])
        return _spec
    return spec


def _resolve_config_paths(config_path: Path, d: dict) -> dict:
    """config dict 의 경로 필드를 config 파일 위치 기준 절대경로로 변환한다."""
    _base = config_path.parent.resolve()
    if "dataset_root" in d:
        d["dataset_root"] = _resolve(_base, d["dataset_root"])
    _conv = d.get("converter", {})
    if _conv.get("sources"):
        _conv["sources"] = [_resolve(_base, _s) for _s in _conv["sources"]]
    if _conv.get("id_map"):
        _conv["id_map"] = _resolve(_base, _conv["id_map"])
    if _conv.get("params"):
        _conv["params"] = {_k: _resolve_spec_path(_base, _v) for _k, _v in _conv["params"].items()}
    return d


def Load_pipeline(config_path: str | Path) -> Pipeline:
    """config 파일을 로드하고 경로를 resolve 해 ``Pipeline`` 을 생성한다."""
    _path   = Path(config_path)
    _ok, _d = Make_dict_from(_path)
    if not _ok or not isinstance(_d, dict):
        raise ValueError(f"config 로드 실패: {config_path}")
    _d      = _resolve_config_paths(_path, _d)
    _fields = {_f.name for _f in dataclasses.fields(Pipeline_config)}
    return Pipeline(Pipeline_config(**{_k: _v for _k, _v in _d.items() if _k in _fields}))


__all__ = ["Pipeline", "Pipeline_config", "Load_pipeline", "MODEL_BUILDERS"]
