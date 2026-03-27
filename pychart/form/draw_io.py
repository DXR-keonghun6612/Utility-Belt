"""Presentation Layer.

IR 데이터를 바탕으로 Base_Config 기반 템플릿을 생성하고 Draw.io XML로 직렬화함.
"""
from dataclasses import dataclass, field
from typing import ClassVar, Any
from python_toolbox.project import Base_Config

from pychart.definition import Class_Info


@dataclass
class Mx_Geometry(Base_Config):
    """Draw.io 지오메트리 정보 데이터 모델.

    Attributes:
        x: X 좌표.
        y: Y 좌표.
        width: 너비.
        height: 높이.
        as_attr: XML 속성명 (기본값: geometry).
    """
    x: int = 0
    y: int = 0
    width: int = 120
    height: int = 20
    as_attr: str = "geometry"
    
    __custom_keys__: ClassVar[dict[str, str]] = {"as_attr": "as"}


@dataclass
class Mx_Cell(Base_Config):
    """Draw.io 요소 기본 템플릿 모델.

    Attributes:
        id: 요소 고유 ID.
        value: 표시 텍스트 또는 HTML.
        style: 스타일 속성 딕셔너리.
        parent: 부모 요소 ID.
        vertex: 노드 여부 식별자.
        geometry: 위치 및 크기 객체.
    """
    id: str
    value: str = ""
    style: dict[str, str] = field(default_factory=dict)
    parent: str = "1"
    vertex: str = "0"
    geometry: Mx_Geometry = field(default_factory=Mx_Geometry)

    # 스타일 딕셔너리 직렬화 변환
    __custom_serializers__: ClassVar[dict[str, Any]] = {
        "style": lambda s: ";".join(
            f"{k}={v}" for k, v in s.items()) + ";" if s else ""
    }

class Drawio_Graph_Builder:
    """IR 모델을 MxCell 트리로 변환하고 XML을 생성함.
    
    Attributes:
        cells: 렌더링 대기 중인 MxCell 객체 리스트.
        _id_counter: 고유 ID 발급기.
    """
    def __init__(self) -> None:
        """초기화."""
        self.cells: list[Mx_Cell] = []
        self._id_counter: int = 2

    def _Next_id(self) -> str:
        """순차적 고유 ID 발급.

        Returns:
            str: 문자열 형태의 고유 ID.
        """
        _id = str(self._id_counter)
        self._id_counter += 1
        return _id

    def Build_from_ir(self, ir_data: dict[str, Class_Info]) -> str:
        """IR 데이터를 Draw.io 포맷으로 렌더링함.
        
        Args:
            ir_data: 파싱된 클래스 정보 딕셔너리.
            
        Returns:
            str: 직렬화가 완료된 XML 문자열.
        """
        _x, _y = 40, 40

        # 클래스 순회
        for _n, _cls_info in ir_data.items():
            _parent_id = self._Next_id()
            _height = 60 + (
                len(_cls_info.attributes) + len(_cls_info.methods)) * 20

            # Enum 여부에 따른 색상 및 스테레오타입 분기
            _fill_color = "#d5e8d4" if _cls_info.is_enum else "#dae8fc"

            # 타입별 색상 및 스테레오타입 분기 처리
            if _cls_info.is_enum:
                _fill_color = "#d5e8d4" # 녹색
                _stereotype = "&lt;&lt;enumeration&gt;&gt;&lt;br&gt;"
            elif _cls_info.is_dataclass:
                _fill_color = "#e1d5e7" # 보라색 (DTO/Data 객체용)
                _stereotype = "&lt;&lt;dataclass&gt;&gt;&lt;br&gt;"
            else:
                _fill_color = "#dae8fc" # 파란색 (일반 클래스)
                _stereotype = ""

            # 2. 헤더 크기 및 총 높이 수치 동기화
            _start_size = 60 if _stereotype else 40
            _current_y = _start_size
            _item_count = len(_cls_info.attributes) + len(_cls_info.methods)
            _total_height = _start_size + (_item_count * 20)

            # 3. 레이아웃 붕괴 방지용 제약 조건 추가 
            _style = {
                "swimlane": "1", 
                "childLayout": "stackLayout", 
                "horizontal": "1", 
                "startSize": str(_start_size), # 동적 헤더 높이 반영
                "html": "1",
                "fontStyle": "1",          
                "fillColor": _fill_color,  
                "swimlaneFillColor": "#ffffff",
                # --- 리사이즈 깨짐 방지 안전망 ---
                "resizeParent": "1",
                "resizeParentMax": "0",
                "resizeLast": "0",
                "collapsible": "1",
                "marginBottom": "0"
            }

            _parent_value = f"{_stereotype}#{_n}"
            _class_node = Mx_Cell(
                id=_parent_id,
                value=_parent_value,
                style=_style,
                vertex="1",
                geometry=Mx_Geometry(
                    x=_x, y=_y, width=300, height=_total_height
                )
            )
            self.cells.append(_class_node)

            # 속성 자식 노드 생성
            for attr in _cls_info.attributes:
                _attr_node = Mx_Cell(
                    id=self._Next_id(),
                    value=f"+ {attr.name}: {attr.type_hint}",
                    style={
                        "text": "1",
                        "align": "left",
                        "html": "1",
                        "spacingLeft": "4"
                    },
                    vertex="1",
                    parent=_parent_id,
                    geometry=Mx_Geometry(
                        y=_current_y, width=300, height=20)
                )
                self.cells.append(_attr_node)
                _current_y += 20
                
            for method in _cls_info.methods:
                _method_node = Mx_Cell(
                    id=self._Next_id(),
                    value=method.To_uml_signature().replace(
                        "<", "&lt;"
                    ).replace(
                        ">", "&gt;"
                    ),
                    style={
                        "text": "1",
                        "align": "left",
                        "html": "1",
                        "spacingLeft": "4"
                    },
                    vertex="1",
                    parent=_parent_id,
                    geometry=Mx_Geometry(y=_current_y, width=300, height=20)
                )
                self.cells.append(_method_node)
                _current_y += 20
            # X축 좌표 갱신 및 줄바꿈
            _x += 350
            if _x > 1200:
                _x = 40
                _y += 300

        return self._Generate_xml()

    def _Generate_xml(self) -> str:
        """직렬화된 MxCell 객체를 XML 태그로 조립함.

        Returns:
            str: 최종 Draw.io XML 문서.
        """
        _xml = [
            "<mxGraphModel><root><mxCell id='0'/><mxCell id='1' parent='0'/>"
        ]

        # 셀 데이터 순회 및 조립
        for cell in self.cells:
            _data = cell.Serialize()
            _geo_data: dict[str, Any] = _data.pop("geometry", None)

            _attrs = " ".join(f'{k}="{v}"' for k, v in _data.items())
            if _geo_data:
                _geo_attrs = " ".join(
                    f'{k}="{v}"' for k, v in _geo_data.items())
                _xml.append(
                    f"<mxCell {_attrs}><mxGeometry {_geo_attrs}/></mxCell>")
            else:
                _xml.append(f"<mxCell {_attrs}/>")

        _xml.append("</root></mxGraphModel>")
        return "".join(_xml)
