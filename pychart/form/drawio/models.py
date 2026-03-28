"""models.py: Draw.io XML 데이터 모델 정의."""
from dataclasses import dataclass, field
from typing import ClassVar, Any
from python_toolbox.project import Base_Config

@dataclass
class Mx_Geometry(Base_Config):
    """Draw.io 요소의 기하학적 정보(위치, 크기)를 정의하는 모델.

    Attributes:
        x: X 좌표.
        y: Y 좌표.
        width: 너비.
        height: 높이.
        relative: 상대적 위치 여부.
        as_attr: XML 속성명 (기본값 "geometry").
    """
    x: int = 0
    y: int = 0
    width: int = 120
    height: int = 20
    relative: str | None = None
    as_attr: str = "geometry"

    __custom_keys__: ClassVar[dict[str, str]] = {"as_attr": "as"}

@dataclass
class Mx_Cell(Base_Config):
    """Draw.io XML의 mxCell 요소를 나타내는 기본 모델.

    Attributes:
        id: 고유 식별자.
        value: 표시될 텍스트 값.
        style: 스타일 속성 딕셔너리.
        parent: 부모 요소 ID (기본값 "1").
        vertex: 노드 여부 ("1"이면 노드).
        edge: 선 여부 ("1"이면 선).
        source: 선의 시작점 ID.
        target: 선의 끝점 ID.
        geometry: 기하학적 정보 객체.
    """
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