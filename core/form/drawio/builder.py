"""builder.py: Draw.io 그래프 빌더 엔진."""
from pathlib import Path
from typing import Any
from ...definition import Arg_Info, Method_Info, Class_Info, Module_Info

from .models import Mx_Cell, Mx_Geometry
from .formatter import F_attributes, F_methods
from .utils import Escape_str_for_xml
from .style import (
    THEME_CLASS, THEME_METHOD, THEME_MODULE,
    BG_VARIABLE, BG_METHOD, DEFAULT_WIDTH,
    START_X, START_Y, MARGIN_Y,
    ROW_HEIGHT, HEADER_HEIGHT, STEREOTYPE_HEADER, MODULE_HEADER_HEIGHT,
    get_swimlane_style, get_child_style, get_edge_style,
)


class Graph_Builder:
    """사용자의 아키텍처 비전을 완벽히 시각화하는 정밀 빌더."""

    def __init__(self) -> None:
        self.cells: list[Mx_Cell] = []
        self._id_counter: int = 2
        self._port_map: dict[str, str] = {}
        self._node_heights: dict[str, int] = {}

    def _Next_id(self) -> str:
        _id = str(self._id_counter)
        self._id_counter += 1
        return _id

    def Build_from_graph(
        self, graph_data: Any, is_detailed: bool = False, current_pkg: str = ""
    ) -> str:
        """모듈 컨테이너 레이아웃과 계층 알고리즘을 결합함."""
        _module_contents: dict[str, list[str]] = {}
        _stubs: list[str] = []
        for _id, _obj in graph_data.nodes.items():
            if _id.startswith("stub:"):
                _stubs.append(_id)
            elif isinstance(_obj, (Class_Info, Method_Info)):
                _mod_path = _id.rpartition('.')[0]
                if _mod_path not in _module_contents:
                    _module_contents[_mod_path] = []
                _module_contents[_mod_path].append(_id)

        _all_ids = list(graph_data.nodes.keys())
        _global_ranks = self._Calculate_user_logic_ranks(_all_ids, graph_data.edges)

        _module_ranks: dict[str, int] = {}
        for _m, _members in _module_contents.items():
            _module_ranks[_m] = min(_global_ranks.get(m, 999) for m in _members)

        _rank_to_items = {}
        for _m, _r in _module_ranks.items():
            if _r not in _rank_to_items:
                _rank_to_items[_r] = []
            _rank_to_items[_r].append(f"mod:{_m}")
        for _s in _stubs:
            _r = _global_ranks[_s]
            if _r not in _rank_to_items:
                _rank_to_items[_r] = []
            _rank_to_items[_r].append(f"stub:{_s}")

        _current_y = START_Y
        for _r in sorted(_rank_to_items.keys()):
            _max_h_in_rank, _current_x = 0, START_X
            for _item in sorted(_rank_to_items[_r]):
                _type, _, _val = _item.partition(':')
                if _type == "mod":
                    _c_id, _w, _h = self._Render_module_container(
                        _val, _module_contents[_val], graph_data, _current_x, _current_y, is_detailed
                    )
                    _current_x += _w + 150
                    _max_h_in_rank = max(_max_h_in_rank, _h)
                else:
                    _p_id, _h = self._Render_single_node(
                        _val, graph_data.nodes[_val], _current_x, _current_y, is_detailed
                    )
                    _current_x += DEFAULT_WIDTH + 100
                    _max_h_in_rank = max(_max_h_in_rank, _h)
            _current_y += _max_h_in_rank + MARGIN_Y + 100

        for _edge in graph_data.edges:
            _src_cell = self._port_map.get(_edge.source_id)
            _tgt_cell = self._port_map.get(_edge.target_id)
            if _src_cell and _tgt_cell:
                _tgt_obj = graph_data.nodes.get(_edge.target_id)
                self._Render_precision_edge(
                    _src_cell, _tgt_cell, _edge.edge_type, _tgt_obj, _edge.target_id
                )

        return self._Generate_xml()

    def _Calculate_user_logic_ranks(
        self, members: list[str], edges: list
    ) -> dict[str, int]:
        """사용자 정의 참조 레벨 알고리즘."""
        _ranks = {m: 0 for m in members}
        _member_set = set(members)
        for _ in range(10):
            _changed = False
            for m in members:
                _parts = [
                    e.source_id for e in edges
                    if e.target_id == m and e.source_id in _member_set
                ]
                if not _parts:
                    _new_rank = 0
                elif len(_parts) == 1:
                    _new_rank = _ranks.get(_parts[0], 0)
                else:
                    _new_rank = max(_ranks.get(p, 0) for p in _parts) + 1
                if _ranks[m] != _new_rank:
                    _ranks[m] = _new_rank
                    _changed = True
            if not _changed:
                break
        return _ranks

    def _Render_module_container(
        self, mod_path: str, member_ids: list, graph_data: Any,
        x: int, y: int, is_detailed: bool
    ) -> tuple[str, int, int]:
        """모듈 상자 내부에 다중 열(Multi-Column) 배치를 구현함."""
        _container_id = self._Next_id()
        _local_ranks = self._Calculate_user_logic_ranks(member_ids, graph_data.edges)

        _rank_groups = {}
        for m in member_ids:
            r = _local_ranks[m]
            if r not in _rank_groups:
                _rank_groups[r] = []
            _rank_groups[r].append(m)

        _inner_x = 40
        _max_total_h = 0
        for _r in sorted(_rank_groups.keys()):
            _inner_y = MODULE_HEADER_HEIGHT + 20
            for _mid in sorted(_rank_groups[_r]):
                _m_obj = graph_data.nodes[_mid]
                _child_id, _actual_h = self._Render_single_node(
                    _mid, _m_obj, _inner_x, _inner_y, is_detailed, parent=_container_id
                )
                _inner_y += _actual_h + MARGIN_Y
            _max_total_h = max(_max_total_h, _inner_y)
            _inner_x += DEFAULT_WIDTH + 150

        _style = get_swimlane_style(
            MODULE_HEADER_HEIGHT, THEME_MODULE["header"], THEME_MODULE["stroke"], use_stack=False
        )
        self.cells.append(Mx_Cell(
            id=_container_id,
            value=f"«module»#{mod_path}",
            style=_style,
            vertex="1",
            parent="1",
            geometry=Mx_Geometry(x=x, y=y, width=_inner_x, height=_max_total_h + 40),
            link=f"#{mod_path.rpartition('.')[0]}.drawio",
        ))
        return _container_id, _inner_x, _max_total_h + 40

    def _Render_single_node(
        self, node_id: str, obj: Any, x: int, y: int, is_detailed: bool, parent: str = "1"
    ) -> tuple[str, int]:
        _stereotype = getattr(obj, "stereotype", "")
        if isinstance(obj, Class_Info):
            _children = F_attributes(obj.attributes) + F_methods(obj.methods, is_detailed=is_detailed)
            _theme = THEME_CLASS
        elif isinstance(obj, Method_Info):
            _children = F_methods([obj], is_detailed=is_detailed)
            _theme = THEME_METHOD
        elif isinstance(obj, Module_Info):
            _children = []
            _theme = THEME_MODULE
        else:
            return self._Next_id(), 0

        _link = f"#{node_id}"
        if node_id.startswith("stub:"):
            _fp = getattr(obj, "file_path", None)
            _link = (
                f"#{Path(_fp).as_uri()}" if _fp
                else f"#{node_id.split(':')[1].rpartition('.')[0]}.drawio"
            )

        _parent_id = self._Create_swimlane_with_ports(
            node_id, obj.name, _stereotype, _children, x, y, _theme, link=_link, parent=parent
        )
        _h = (STEREOTYPE_HEADER if _stereotype else HEADER_HEIGHT) + sum(h for _, h, _ in _children)
        self._node_heights[node_id] = _h
        return _parent_id, _h

    def _Create_swimlane_with_ports(
        self, symbol_id: str, name: str, stereotype: str, children_data: list,
        x: int, y: int, theme_colors: dict, link: str = None, parent: str = "1"
    ) -> str:
        _parent_id = self._Next_id()
        self._port_map[symbol_id] = _parent_id
        _start_size = STEREOTYPE_HEADER if stereotype else HEADER_HEIGHT
        _total_h = _start_size + sum(h for _, h, _ in children_data)

        self.cells.append(Mx_Cell(
            id=_parent_id,
            value=f"{stereotype}#{name}",
            style=get_swimlane_style(_start_size, theme_colors["header"], theme_colors["stroke"], use_stack=True),
            vertex="1",
            parent=parent,
            geometry=Mx_Geometry(x=x, y=y, width=DEFAULT_WIDTH, height=_total_h),
            link=link,
        ))

        _cur_y = _start_size
        for _val, _h, _type in children_data:
            _child_id = self._Next_id()
            _bg = BG_VARIABLE if _type == "variable" else BG_METHOD
            _clean_name = _val.split(':')[0].strip('+ ').strip('<b>').strip('</b>').split('(')[0]
            self._port_map[f"{symbol_id}.{_clean_name}"] = _child_id
            self.cells.append(Mx_Cell(
                id=_child_id,
                value=_val,
                style=get_child_style(_bg),
                vertex="1",
                parent=_parent_id,
                geometry=Mx_Geometry(y=_cur_y, width=DEFAULT_WIDTH, height=_h),
            ))
            _cur_y += _h
        return _parent_id

    def _Render_precision_edge(
        self, source_cell: str, target_cell: str, edge_type: str,
        target_obj: Any, target_id: str
    ) -> None:
        """타겟 헤더의 중앙을 정밀하게 타격하는 엣지 생성."""
        _style = get_edge_style(edge_type)
        _entry_y = 0.5
        if isinstance(target_obj, Class_Info):
            _total_h = self._node_heights.get(target_id, 100)
            _header_h = STEREOTYPE_HEADER if target_obj.stereotype else HEADER_HEIGHT
            _entry_y = (_header_h / 2) / _total_h

        _style.update({
            "perimeter": "0",
            "exitX": "1", "exitY": "0.5",
            "entryX": "0", "entryY": f"{_entry_y:.2f}",
        })
        self.cells.append(Mx_Cell(
            id=self._Next_id(),
            value="",
            style=_style,
            vertex=None,
            edge="1",
            parent="1",
            source=source_cell,
            target=target_cell,
            geometry=Mx_Geometry(x=0, y=0, width=0, height=0, relative="1", as_attr="geometry"),
        ))

    def _Generate_xml(self) -> str:
        _xml = ["<mxGraphModel><root><mxCell id='0'/><mxCell id='1' parent='0'/>"]
        for cell in self.cells:
            _d = cell.Serialize()
            _geo = _d.pop("geometry", None)
            _attrs = " ".join(
                f'{k}="{Escape_str_for_xml(str(v))}"'
                for k, v in _d.items() if v is not None
            )
            if _geo:
                _g_attrs = " ".join(
                    f'{k}="{Escape_str_for_xml(str(v))}"'
                    for k, v in _geo.items() if v is not None
                )
                _xml.append(f"<mxCell {_attrs}><mxGeometry {_g_attrs}/></mxCell>")
            else:
                _xml.append(f"<mxCell {_attrs}/>")
        _xml.append("</root></mxGraphModel>")
        return "".join(_xml)
