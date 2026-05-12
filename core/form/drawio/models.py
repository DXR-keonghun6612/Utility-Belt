"""models.py: Draw.io XML 데이터 모델 정의."""
from dataclasses import dataclass, field
from typing import ClassVar, Any

from python_toolbox import Base_Config


@dataclass
class Mx_Geometry(Base_Config):
    """Draw.io 요소의 기하학적 정보(위치, 크기)를 정의하는 모델."""
    x: int = 0
    y: int = 0
    width: int = 120
    height: int = 20
    relative: str | None = None
    as_attr: str = "geometry"

    __custom_keys__: ClassVar[dict[str, str]] = {"as_attr": "as"}


@dataclass
class Mx_Cell(Base_Config):
    """Draw.io XML의 mxCell 요소를 나타내는 기본 모델."""
    id: str = ""
    value: str = ""
    style: dict[str, str] = field(default_factory=dict)
    parent: str = "1"

    vertex: str | None = "0"
    edge: str | None = None

    source: str | None = None
    target: str | None = None

    geometry: Mx_Geometry | None = field(default_factory=Mx_Geometry)
    link: str | None = None

    __custom_serializers__: ClassVar[dict[str, Any]] = {
        "style": lambda s: ";".join(
            f"{k}={v}" for k, v in s.items()) + ";" if s else ""
    }
