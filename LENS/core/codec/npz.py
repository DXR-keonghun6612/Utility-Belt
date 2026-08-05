"""npz codec — **이름 붙은 배열 묶음** ↔ ``{이름: ndarray}``. np.load/np.savez.

배열 하나는 ``npy`` 가 든다. 여기는 **함께 갈리고 함께 쓰이는 배열 여럿**이 한 파일이어야 할 때다 —
class 하나의 충분통계가 도메인마다 ``sum``·``sqsum`` 으로 나뉘는 것처럼. 쪼개면 파일이 도메인 수만큼
늘고, 합치면 한 번에 실려 온다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from . import CODEC_REGISTRY
from ._base import File_Codec


@CODEC_REGISTRY.Register_module("npz")
class Npz_Codec(File_Codec):

    @classmethod
    def Formats(cls) -> tuple[str, ...]:
        return ("npz",)

    @classmethod
    def _Read(cls, path: Path) -> Any:
        """``{이름: ndarray}`` 로 푼다 — ``NpzFile`` 을 그대로 주면 파일 핸들이 산 채로 샌다."""
        with np.load(str(path), allow_pickle=False) as _z:
            return {_k: _z[_k] for _k in _z.files}

    @classmethod
    def _Write(cls, data: Any, path: Path) -> None:
        """``{이름: 배열}`` 을 한 파일로.

        Raises:
            TypeError: dict 가 아닐 때 (배열 하나면 ``npy`` 를 쓴다 — 이름이 없으면 되읽을 때
                key 를 지어내야 한다).
        """
        if not isinstance(data, dict):
            raise TypeError(f"npz 는 {{이름: 배열}} 을 받는다 (배열 하나면 npy): {type(data).__name__}")
        np.savez(str(path), **{str(_k): np.asarray(_v) for _k, _v in data.items()})
