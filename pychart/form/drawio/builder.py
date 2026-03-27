"""builder.py: Draw.io 그래프 빌더 엔진."""
from typing import Any
from pychart.definition import Class_Info, Method_Info

from .models import Mx_Cell, Mx_Geometry
from .formatter import F_attributes, F_methods
from .utils import replace_brackets


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
    ) -> None:
        # (기존 코드와 완전히 동일)
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
            value=f"{replace_brackets(stereotype)}#{name}",
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
                value=_val,
                style=_child_style,
                vertex="1",
                parent=_parent_id,
                geometry=Mx_Geometry(y=_current_y, width=350, height=_h)
            )
            self.cells.append(_node)
            _current_y += _h

    def Build_from_ir(
        self, ir_data: dict[str, Any], is_detailed: bool = False
    ) -> str:
        _x, _y = 40, 40

        for _name, _obj in ir_data.items():
            if isinstance(_obj, Class_Info):
                if _obj.is_enum:
                    _type = "«enumeration»<br>"
                elif _obj.is_dataclass:
                    _type = "«dataclass»<br>"
                else:
                    _type = ""

                _children = F_attributes(
                    _obj.attributes, 20
                ) + F_methods(
                    _obj.methods, 20, is_detailed
                )
                _theme = {"header": "#dae8fc", "stroke": "#6c8ebf"}

            elif isinstance(_obj, Method_Info):
                _type = "«function»<br>"
                _children = F_methods([_obj], 20, is_detailed)
                _theme = {"header": "#ffe6cc", "stroke": "#d79b00"}

            else:
                continue 

            self._Create_swimlane_sector(
                _name, _type, _children, _x, _y, _theme)

            _x += 400
            if _x > 1200:
                _x = 40
                _y += 400

        return self._Generate_xml()

    def _Generate_xml(self) -> str:
        # (기존 코드와 완전히 동일)
        _xml = [
            "<mxGraphModel><root><mxCell id='0'/><mxCell id='1' parent='0'/>"]
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