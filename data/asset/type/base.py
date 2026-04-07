from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np

from python_toolbox.project import Base_Config


@dataclass
class Base_Asset(Base_Config):
    """모든 에셋 타입의 공통 베이스 클래스.

    씬 그래프와 무관하게 파일에서 로드된 원시 데이터를 보유하며,
    label, 로컬 트랜스폼, 원본 경로를 공통 필드로 제공함.
    """
    label: str = "asset"
    local_matrix: np.ndarray = field(
        default_factory=lambda: np.eye(4, dtype=np.float32)
    )
    source_path: str | None = None

    __exclude_serialize__: ClassVar[set[str]] = set()
    __custom_serializers__: ClassVar[dict] = {
        "local_matrix": lambda m: m.flatten().tolist(),
    }
