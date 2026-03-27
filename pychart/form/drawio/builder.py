"""builder.py: Draw.io 그래프 빌더 엔진."""
import re

from typing import Any
from pychart.definition import (
    Arg_Info, Global_Group_Info, Method_Info, Class_Info, Module_Info)

from .models import Mx_Cell, Mx_Geometry
from .formatter import F_attributes, F_methods
from .utils import R_brackets


class Graph_Builder:
    """IR 모델을 MxCell 트리로 변환하고 XML을 생성함."""
    
    def __init__(self) -> None:
        self.cells: list[Mx_Cell] = []
        self._id_counter: int = 2

    def _Next_id(self) -> str:
        _id = str(self._id_counter)
        self._id_counter += 1
        return _id

    def _Create_swimlane_sector(
        self, name: str, stereotype: str, 
        children_data: list[tuple[str, int, str]], 
        x: int, y: int, theme_colors: dict[str, str]
    ) -> str:
        _parent_id = self._Next_id()
        _start_size = 60 if stereotype else 40
        _total_height = _start_size + sum(h for _, h, _ in children_data)

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
            "fillColor": theme_colors.get("header", "#dae8fc"), 
            "swimlaneFillColor": "#ffffff",
            "resizeParent": "1",
            "resizeParentMax": "0",
            "resizeLast": "0",
            "collapsible": "1",
            "marginBottom": "0",
            "whiteSpace": "wrap",
            "strokeColor": theme_colors.get("stroke", "#6c8ebf")
        }

        _container_node = Mx_Cell(
            id=_parent_id,
            value=f"{R_brackets(stereotype)}#{name}",
            style=_parent_style, vertex="1",
            geometry=Mx_Geometry(x=x, y=y, width=350, height=_total_height)
        )
        self.cells.append(_container_node)

        _current_y = _start_size
        for _val, _h, _type in children_data:
            _bg = "#fff2cc" if _type == "variable" else "#d5e8d4"
            _child_style = {
                "text": "1",
                "html": "1",
                "align": "left",
                "verticalAlign": "top",
                "spacingTop": "2",
                "spacingLeft": "4",
                "spacingRight": "4",
                "strokeColor": "none",
                "fillColor": _bg,
                "overflow": "hidden",
                "whiteSpace": "wrap",
                "rotatable": "0"
            }
            _node = Mx_Cell(
                id=self._Next_id(),
                value=R_brackets(_val),
                style=_child_style,
                vertex="1",
                parent=_parent_id,
                geometry=Mx_Geometry(y=_current_y, width=350, height=_h)
            )
            self.cells.append(_node)
            _current_y += _h

        return _parent_id

    def _Render_edge(self, source_id: str, target_id: str, edge_type: str) -> None:
        """두 노드를 잇는 선(Edge)을 생성함."""
        _edge_id = self._Next_id()
        
        # 타입에 따른 화살표 스타일 분기
        if edge_type == "inheritance":
            # 상속: 실선, 빈 삼각형 화살촉, 직각으로 꺾이는 선
            _style = {
                "edgeStyle": "orthogonalEdgeStyle",
                "rounded": "0",
                "orthogonalLoop": "1",
                "jettySize": "auto",
                "html": "1",
                "endArrow": "block",
                "endFill": "0"
            }
        else:
            # 의존성(데이터 흐름): 실선, 열린 화살촉
            _style = {
                "edgeStyle": "orthogonalEdgeStyle",
                "rounded": "0",
                "orthogonalLoop": "1",
                "jettySize": "auto",
                "html": "1",
                "endArrow": "open"
            }

        # Mx_Geometry의 불필요한 기본값(x=0, y=0 등)을 None으로 덮어써서 XML 출력 방지
        _geo = Mx_Geometry(
            x=0, y=0, width=0, height=0, relative="1", as_attr="geometry"
        )

        _edge_node = Mx_Cell(
            id=_edge_id,
            value="",
            style=_style,
            vertex=None,  # 선이므로 vertex는 제외
            edge="1",     # 선 속성 활성화
            parent="1",
            source=source_id,
            target=target_id,
            geometry=_geo
        )
        self.cells.append(_edge_node)

    def Build_from_ir(
        self, ir_data: dict[str, Any], is_detailed: bool = False
    ) -> str:
        _x, _y = 40, 40

        _node_ids: dict[str, str] = {}

        for _name, _obj in ir_data.items():
            _stereotype = getattr(_obj, "stereotype", "")
            
            if isinstance(_obj, Class_Info):
                # is_enum, is_dataclass 조건문 완전 삭제됨!
                _children = F_attributes(
                    _obj.attributes, 20
                ) + F_methods(
                    _obj.methods, 20, is_detailed
                )
                _theme = {"header": "#dae8fc", "stroke": "#6c8ebf"}
                
            elif isinstance(_obj, Method_Info):
                _children = F_methods([_obj], 20, is_detailed)
                _theme = {"header": "#ffe6cc", "stroke": "#d79b00"}
                
            elif isinstance(_obj, Global_Group_Info):
                _children = F_attributes(_obj.variables, 20)
                _theme = {"header": "#f5f5f5", "stroke": "#666666"}
                
            elif isinstance(_obj, Module_Info):
                _fake_attrs = [
                    Arg_Info(
                        name=sym, type_hint="Imported"
                    ) for sym in _obj.imported_symbols]
                _children = F_attributes(_fake_attrs, 20)
                _theme = {"header": "#e1d5e7", "stroke": "#9673a6"}
                
            else:
                continue 

            _parent_id =self._Create_swimlane_sector(
                _name, _stereotype, _children, _x, _y, _theme)
            _node_ids[_name] = _parent_id

            _x += 400
            if _x > 1200:
                _x = 40
                _y += 400

        for _name, _obj in ir_data.items():
            if isinstance(_obj, Class_Info):
                _source_id = _node_ids.get(_name)
                if not _source_id: continue

                # 1. 상속(Inheritance) 화살표 연결
                for _base in _obj.bases:
                    _target_id = _node_ids.get(_base)
                    if _target_id: # 렌더링된 박스 중에 부모 클래스가 있으면
                        self._Render_edge(_source_id, _target_id, "inheritance")

                # 2. 데이터 흐름(Composition/HAS-A) 화살표 연결
                for _attr in _obj.attributes:
                    # 정규식으로 단어(클래스명 등) 추출 (예: list[Base_Config] -> Base_Config)
                    _words = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', _attr.type_hint)
                    
                    for _word in _words:
                        # 자기 자신을 가리키는 순환 참조 방지 & 화면에 존재하는 박스인지 확인
                        if _word != _name and _word in _node_ids:
                            _target_id = _node_ids[_word]
                            self._Render_edge(
                                _source_id, _target_id, "dependency"
                            )
                            # Union[A, B] 같은 경우 여러 번 긋게 되므로 정상 작동함

        return self._Generate_xml()

    def _Generate_xml(self) -> str:
        """직렬화된 MxCell 객체를 XML 태그로 조립함."""
        _xml = [
            "<mxGraphModel><root><mxCell id='0'/><mxCell id='1' parent='0'/>"]

        for cell in self.cells:
            _data = cell.Serialize()
            _geo: dict[str, Any] | None = _data.pop("geometry", None)

            _attrs = " ".join(
                f'{k}="{v}"' for k, v in _data.items() if v is not None)
            
            if _geo:
                # Geometry 내부 속성도 None 제외
                _geo_attrs = " ".join(
                    f'{k}="{v}"' for k, v in _geo.items() if v is not None)
                _xml.append(
                    f"<mxCell {_attrs}><mxGeometry {_geo_attrs}/></mxCell>")
            else:
                _xml.append(f"<mxCell {_attrs}/>")

        _xml.append("</root></mxGraphModel>")
        return "".join(_xml)