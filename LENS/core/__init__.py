"""core — LENS 계산/데이터 계층 (``core`` 자체가 pipeline binder). 설계는 README.

``__init__`` 은 config 진입점(경로 resolve + 로드)과 노출만 한다.

**바인더는 지연 노출한다** (PEP 562 ``__getattr__``). `from core import Pipeline` 은 그대로 되지만,
import 자체는 무거운 것(cv2·sam3)을 안 끌고 온다 — 안 그러면 ``import core.schema`` 만 하려는 소비자도
부모 패키지 실행에 걸려 전부를 들이게 되고, 순수 트리 코어를 따로 뺀 의미가 사라진다. 이 성질은
[`test_layering.py`](test_layering.py) 가 검사한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:                       # 타입 전용 — 런타임엔 안 들인다
    from ._base import Pipeline, Pipeline_config

_LAZY = ("Pipeline", "Pipeline_config", "MODEL_BUILDERS")


def __getattr__(name: str):
    """바인더 심볼을 처음 쓸 때 들인다 (import 시점이 아니라)."""
    if name in _LAZY:
        from . import _base
        return getattr(_base, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)


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
    if _conv.get("params"):
        _conv["params"] = {_k: _resolve_spec_path(_base, _v) for _k, _v in _conv["params"].items()}
    return d


def Load_pipeline(config_path: str | Path) -> "Pipeline":
    """config 파일을 로드하고 경로를 resolve 해 ``Pipeline`` 을 생성한다."""
    import dataclasses

    from python_toolbox.file import Make_dict_from

    from ._base import Pipeline, Pipeline_config

    _path   = Path(config_path)
    _ok, _d = Make_dict_from(_path)
    if not _ok or not isinstance(_d, dict):
        raise ValueError(f"config 로드 실패: {config_path}")
    _d      = _resolve_config_paths(_path, _d)
    _fields = {_f.name for _f in dataclasses.fields(Pipeline_config)}
    return Pipeline(Pipeline_config(**{_k: _v for _k, _v in _d.items() if _k in _fields}))


__all__ = ["Pipeline", "Pipeline_config", "Load_pipeline", "MODEL_BUILDERS"]
