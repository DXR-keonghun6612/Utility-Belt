from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, ClassVar

from data.asset.type.base import Base_Asset


@dataclass
class Mesh_Asset(Base_Asset):
    """삼각 메시(Trimesh) 지오메트리 데이터를 보유하는 에셋.

    vertices, faces 기반의 표면 메시 데이터를 담음.
    유사도 비교는 data.asset.utils.similarity 독립 함수를 사용함.
    """
    geometry: Any | None = field(default=None, repr=False)

    __exclude_serialize__: ClassVar[set[str]] = {"geometry"}
