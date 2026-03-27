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
    as_attr: str = "geometry"
    
    __custom_keys__: ClassVar[dict[str, str]] = {"as_attr": "as"}

@dataclass
class Mx_Cell(Base_Config):
    id: str
    value: str = ""
    style: dict[str, str] = field(default_factory=dict)
    parent: str = "1"
    vertex: str = "0"
    geometry: Mx_Geometry = field(default_factory=Mx_Geometry)

    __custom_serializers__: ClassVar[dict[str, Any]] = {
        "style": lambda s: ";".join(
            f"{k}={v}" for k, v in s.items()) + ";" if s else ""
    }