"""builder.py: Draw.io 그래프 빌더 엔진."""
from typing import Any
from pychart.definition import (
    Arg_Info, Global_Group_Info, Method_Info, Class_Info, Module_Info)

from .models import Mx_Cell, Mx_Geometry
from .formatter import F_attributes, F_methods
from .utils import R_brackets
from .style import (
    THEME_CLASS, THEME_METHOD, THEME_GLOBAL, THEME_MODULE,
    BG_VARIABLE, BG_METHOD, DEFAULT_WIDTH, STEP_X, STEP_Y, MAX_X,
    get_swimlane_style, get_child_style, get_edge_style
)


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

        _parent_style = get_swimlane_style(
            _start_size,
            theme_colors.get("header", "#dae8fc"),
            theme_colors.get("stroke", "#6c8ebf")
        )

        _container_node = Mx_Cell(
            id=_parent_id,
            value=f"{R_brackets(stereotype)}#{name}",
            style=_parent_style, vertex="1",
            geometry=Mx_Geometry(x=x, y=y, width=DEFAULT_WIDTH, height=_total_height)
        )
        self.cells.append(_container_node)

        _current_y = _start_size
        for _val, _h, _type in children_data:
            _bg = BG_VARIABLE if _type == "variable" else BG_METHOD
            _child_style = get_child_style(_bg)
            
            _node = Mx_Cell(
                id=self._Next_id(),
                value=R_brackets(_val),
                style=_child_style,
                vertex="1",
                parent=_parent_id,
                geometry=Mx_Geometry(y=_current_y, width=DEFAULT_WIDTH, height=_h)
            )
            self.cells.append(_node)
            _current_y += _h

        return _parent_id

    def _Render_edge(self, source_id: str, target_id: str, edge_type: str) -> None:
        """두 노드를 잇는 선(Edge)을 생성함."""
        _edge_id = self._Next_id()
        
        _style = get_edge_style(edge_type)

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

    def Build_from_graph(
        self, graph_data: Any, is_detailed: bool = False
    ) -> str:
        _x, _y = 40, 40

        _node_ids: dict[str, str] = {}

        for _name, _obj in graph_data.nodes.items():
            _stereotype = getattr(_obj, "stereotype", "")
            
            if isinstance(_obj, Class_Info):
                # is_enum, is_dataclass 조건문 완전 삭제됨!
                _children = F_attributes(
                    _obj.attributes, 20
                ) + F_methods(
                    _obj.methods, 20, is_detailed
                )
                _theme = THEME_CLASS
                
            elif isinstance(_obj, Method_Info):
                _children = F_methods([_obj], 20, is_detailed)
                _theme = THEME_METHOD
                
            elif isinstance(_obj, Global_Group_Info):
                _children = F_attributes(_obj.variables, 20)
                _theme = THEME_GLOBAL
                
            elif isinstance(_obj, Module_Info):
                _fake_attrs = [
                    Arg_Info(
                        name=sym, type_hint="Imported"
                    ) for sym in _obj.imported_symbols]
                _children = F_attributes(_fake_attrs, 20)
                _theme = THEME_MODULE
                
            else:
                continue 

            _parent_id =self._Create_swimlane_sector(
                _name, _stereotype, _children, _x, _y, _theme)
            _node_ids[_name] = _parent_id

            _x += STEP_X
            if _x > MAX_X:
                _x = 40
                _y += STEP_Y

        for _edge in graph_data.edges:
            _source_id = _node_ids.get(_edge.source_name)
            _target_id = _node_ids.get(_edge.target_name)
            if _source_id and _target_id:
                self._Render_edge(_source_id, _target_id, _edge.edge_type)

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