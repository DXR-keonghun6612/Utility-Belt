"""batch process 단위 체크포인트 — 출력 저장/복원."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

from core.process.utils.color import HS_stats


_MANIFEST = "context.json"

_SCHEMA_TYPES: dict[str, type] = {
    "HS_stats": HS_stats,
}


def Hash(parts: list[Any]) -> str:
    _blob = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(_blob.encode("utf-8")).hexdigest()[:16]


class Checkpoint:
    """고정 캐시 루트 아래에서 batch process 출력의 저장/복원을 담당한다."""

    def __init__(self, cache_root: Path) -> None:
        self.root = cache_root

    def Dir(self, index: int, name: str, h: str) -> Path:
        return self.root / f"{index:02d}_{name}_{h}"

    def Exists(self, ckpt_dir: Path) -> bool:
        return (ckpt_dir / _MANIFEST).exists()

    def Save(self, ckpt_dir: Path, output: dict) -> None:
        """batch process 출력 dict 를 체크포인트로 저장한다.

        ndarray 등 직렬화 불가 값은 제외한다. dataclass 는 schema 로 저장해 복원한다.
        """
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        _manifest: dict[str, dict] = {"scalars": {}, "schemas": {}}

        for _key, _val in output.items():
            if dataclasses.is_dataclass(_val) and not isinstance(_val, type):
                _manifest["schemas"][_key] = {
                    "__type__": type(_val).__name__,
                    "data":     dataclasses.asdict(_val),
                }
            else:
                try:
                    json.dumps(_val)
                    _manifest["scalars"][_key] = _val
                except (TypeError, ValueError):
                    pass

        (ckpt_dir / _MANIFEST).write_text(
            json.dumps(_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def Load(self, ckpt_dir: Path) -> dict:
        """체크포인트를 읽어 context 로 복원한다."""
        _manifest = json.loads((ckpt_dir / _MANIFEST).read_text(encoding="utf-8"))
        _ctx: dict = {}
        _ctx.update(_manifest.get("scalars", {}))

        for _key, _s in _manifest.get("schemas", {}).items():
            _cls = _SCHEMA_TYPES.get(_s["__type__"])
            _ctx[_key] = _cls(**_s["data"]) if _cls else _s["data"]

        return _ctx
