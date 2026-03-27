"""models.py: Draw.io XML 데이터 모델 정의."""
from dataclasses import dataclass, field
from typing import ClassVar, Any
from python_toolbox.project import Base_Config

@dataclass
class Mx_Geometry(Base_Config):
    x: int = 0
    y: int = 0
    width: int = 120
    height: int = 20
    relative: str | None = None
    as_attr: str = "geometry"
    
    __custom_keys__: ClassVar[dict[str, str]] = {"as_attr": "as"}

@dataclass
class Mx_Cell(Base_Config):
    """Draw.io 요소 기본 템플릿 모델."""
    id: str
    value: str = ""
    style: dict[str, str] = field(default_factory=dict)
    parent: str = "1"
    
    # 노드(박스)일 때는 vertex="1", 선(Edge)일 때는 edge="1"
    vertex: str | None = "0"
    edge: str | None = None
    
    # 선(Edge) 전용 속성
    source: str | None = None
    target: str | None = None
    
    geometry: Mx_Geometry | None = field(default_factory=Mx_Geometry)

    # 스타일 딕셔너리 직렬화 변환
    __custom_serializers__: ClassVar[dict[str, Any]] = {
        "style": lambda s: ";".join(
            f"{k}={v}" for k, v in s.items()) + ";" if s else ""
    }