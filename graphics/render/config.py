from __future__ import annotations
from dataclasses import dataclass, field

from python_toolbox.project import Base_Config


@dataclass
class Render_Config(Base_Config):
    """렌더 파이프라인 실행 옵션."""

    width: int = 1920
    height: int = 1080

    # 실행할 렌더 패스 이름 목록 (pass_registry에 등록된 키와 일치해야 함)
    passes: list = field(default_factory=lambda: ["rgb", "depth", "segmentation", "normal"])

    output_dir: str = "./result"

    # 배경색 (RGB, 0.0~1.0)
    bg_color: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
