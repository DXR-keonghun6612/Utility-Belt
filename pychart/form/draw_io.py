"""Presentation Layer.

IR 데이터를 바탕으로 Base_Config 기반 템플릿을 생성하고 Draw.io XML로 직렬화함.
"""
from dataclasses import dataclass, field
from typing import ClassVar, Any
from python_toolbox.project import Base_Config

from pychart.definition import Class_Info, Arg_Info, Method_Info


def _Brackets_replace(text: str) -> str:
    return text.replace("<", "&lt;").replace(">", "&gt;")


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

    def _Format_attributes(
        self, attributes: list[Arg_Info]
    ) -> list[tuple[str, int, str]]:
        """속성(Variables) 데이터를 HTML 문자열과 높이 정보로 포맷팅함."""
        _data = []
        for _a in attributes:
            _a_name = _Brackets_replace(_a.name)
            _a_type = _Brackets_replace(_a.type_hint)
            _data.append((f"+ {_a_name}: {_a_type}", 20, "variable"))
        return _data

    def _Format_methods(
        self, methods: list[Method_Info]
    ) -> list[tuple[str, int, str]]:
        """메서드(Functions) 데이터를 줄바꿈이 적용된 HTML 문자열과 높이 정보로 포맷팅함."""
        _data = []
        for _m in methods:
            _valid_args = [a for a in _m.args if a.name != "self"]
            _m_name = _Brackets_replace(_m.name)
            _m_rt_type = _Brackets_replace(_m.return_type)
            
            if not _valid_args:
                _val = f"+ <b>{_m_name}</b>() -&gt; {_m_rt_type}"
                _h = 20
            else:
                _val = f"+ <b>{_m_name}</b>(<br>"
                for _arg in _valid_args:
                    _t = _Brackets_replace(_arg.type_hint)
                    _val += f"&nbsp;&nbsp;&nbsp;&nbsp;{_arg.name}: {_t},<br>"
                _val += f") -&gt; {_m_rt_type}"
                _h = 20 + (len(_valid_args) * 16) + 16
                
            _data.append((_Brackets_replace(_val), _h, "function"))
        return _data

    def _Render_class_node(
        self, name: str, cls_info: Class_Info, x: int, y: int
    )-> None:
        """포맷팅된 데이터를 바탕으로 실제 Draw.io 노드(Mx_Cell)를 생성함."""
        _parent_id = self._Next_id()

        # 1. 헤더 메타데이터 설정
        _stereotype = ""
        if cls_info.is_enum:
            _stereotype = "«enumeration»<br>"
        elif cls_info.is_dataclass:
            _stereotype = "«dataclass»<br>"
        _start_size = 60 if _stereotype else 40
        
        # 2. 헬퍼 함수를 통한 자식 데이터 파싱 및 총 높이 계산
        _children_data = self._Format_attributes(cls_info.attributes) + \
                         self._Format_methods(cls_info.methods)
                         
        _total_children_height = sum(h for _, h, _ in _children_data)
        _total_height = _start_size + _total_children_height

        # 3. 부모 컨테이너(헤더) 노드 생성
        _parent_style = {
            "shape": "swimlane",
            "childLayout": "stackLayout", 
            "horizontal": "1", 
            "horizontalStack": "0", 
            "startSize": str(_start_size), 
            "html": "1",
            "fontStyle": "1", 
            "align": "center",
            "verticalAlign": "top",
            "fillColor": "#dae8fc", 
            "swimlaneFillColor": "#ffffff",
            "resizeParent": "1", 
            "resizeParentMax": "0", 
            "resizeLast": "0",
            "collapsible": "1", 
            "marginBottom": "0", 
            "whiteSpace": "wrap",
            "strokeColor": "#6c8ebf"
        }
        _class_node = Mx_Cell(
            id=_parent_id,
            value=f"{_stereotype}#{name}",
            style=_parent_style,
            vertex="1",
            geometry=Mx_Geometry(x=x, y=y, width=350, height=_total_height)
        )
        self.cells.append(_class_node)

        # 4. 자식 노드 일괄 생성
        _current_y = _start_size
        for _val, _h, _type in _children_data:
            _bg_color = "#fff2cc" if _type == "variable" else "#d5e8d4"
            _child_style = {
                "text": "1",
                "html": "1",
                "align": "left",
                "verticalAlign": "top",
                "spacingTop": "2",
                "spacingLeft": "4",
                "spacingRight": "4",
                "strokeColor": "none",
                "fillColor": _bg_color,
                "overflow": "hidden",
                "whiteSpace": "wrap",
                "rotatable": "0"
            }
            _node = Mx_Cell(
                id=self._Next_id(),
                value=_val,
                style=_child_style,
                vertex="1",
                parent=_parent_id,
                geometry=Mx_Geometry(y=_current_y, width=350, height=_h)
            )
            self.cells.append(_node)
            _current_y += _h

    def Build_from_ir(
        self, ir_data: dict[str, Class_Info]
    ) -> str:
        """IR 데이터를 순회하며 좌표를 계산하고 렌더링 파이프라인을 호출함."""
        _x, _y = 40, 40

        for _n, _cls_info in ir_data.items():
            # 헬퍼 메서드 호출을 통해 단일 클래스 렌더링 위임
            self._Render_class_node(_n, _cls_info, _x, _y)

            # X축/Y축 좌표 갱신 (그리드 정렬)
            _x += 400
            if _x > 1200:
                _x = 40
                _y += 350

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
