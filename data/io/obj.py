from __future__ import annotations
from pathlib import Path

import trimesh
import numpy as np

from data.asset.type.mesh import Mesh_Asset
from data.node.type import Base_Node
from data.node.type.mesh import Mesh_Node
from data.node.type.group import Group_Node


def load_obj_as_asset(file_path: Path) -> list[Mesh_Asset]:
    """OBJ 파일을 파싱하여 Mesh_Asset 리스트로 반환함.

    Args:
        file_path (Path): 로드할 OBJ 파일 경로.

    Returns:
        list[Mesh_Asset]: 파싱된 메시 에셋 목록.
    """
    _loaded = trimesh.load(file_path)
    _Fix_normals_recursive(_loaded)
    _source = str(file_path.resolve())
    return _Extract_assets(_loaded, label=file_path.stem, source_path=_source)


def load_obj_as_node(file_path: Path) -> Base_Node:
    """OBJ 파일을 파싱하여 Scene_Node 트리로 반환함.

    Args:
        file_path (Path): 로드할 OBJ 파일 경로.

    Returns:
        Scene_Node: 생성된 씬 노드 구조의 루트.
    """
    _loaded = trimesh.load(file_path)
    _Fix_normals_recursive(_loaded)
    _root = _Parse_trimesh_scene(_loaded, label=file_path.stem)
    _Set_source_path(_root, str(file_path.resolve()))
    return _root


# ==========================================
# 노멀 정리
# ==========================================

def _Fix_normals_recursive(source: trimesh.Geometry) -> None:
    """trimesh 객체의 winding을 일관되게 재정렬함.

    연결된 component 내부의 winding 일관성은 복구하지만, non-watertight 메시에서는
    component의 전역 "외향" 방향을 volume으로 판정할 수 없어 절반만 맞는 경우가
    있음. 궁극적으로 ROADMAP의 노멀 복구 과제에서 해결 예정이며, 그 전까지는
    양면 조명으로 시각적 증상을 우회함.
    """
    if isinstance(source, trimesh.Trimesh):
        source.merge_vertices()
        source.fix_normals()
        return

    if isinstance(source, trimesh.Scene):
        for _geo in source.geometry.values():
            if isinstance(_geo, trimesh.Trimesh):
                _geo.merge_vertices()
                _geo.fix_normals()


# ==========================================
# Asset 변환 헬퍼
# ==========================================

def _Extract_assets(
    source: trimesh.Geometry, label: str, source_path: str
) -> list[Mesh_Asset]:
    """trimesh 객체에서 Mesh_Asset 리스트를 추출함."""
    if isinstance(source, trimesh.Trimesh):
        return [Mesh_Asset(
            label=label,
            geometry=source,
            source_path=source_path,
        )]

    if isinstance(source, trimesh.Scene):
        _assets: list[Mesh_Asset] = []
        for _node_name in source.graph.nodes:
            _trans, _geo_name = source.graph.get(_node_name)
            if _geo_name is not None and _geo_name in source.geometry:
                _assets.append(Mesh_Asset(
                    label=_node_name,
                    local_matrix=np.array(_trans, dtype=np.float32),
                    geometry=source.geometry[_geo_name],
                    source_path=source_path,
                ))
        return _assets

    return []


# ==========================================
# Node 변환 헬퍼
# ==========================================

def _Set_source_path(node: Base_Node, path: str) -> None:
    """Mesh_Node에 원본 파일 경로를 기록함."""
    if isinstance(node, Mesh_Node):
        node.source_key = path
    for _child in node.children:
        _Set_source_path(_child, path)


def _Parse_trimesh_scene(
    source: trimesh.Geometry, label: str = "obj"
) -> Base_Node:
    """trimesh 객체의 평면화된 그래프 데이터를 기반으로 트리 계층을 조립함.

    Args:
        source (trimesh.Geometry): 파싱할 trimesh 지오메트리 객체.
        label (str): 루트 노드에 부여할 식별자 이름.

    Returns:
        Scene_Node: 조립이 완료된 계층 구조의 최상단 루트 노드.
    """
    if isinstance(source, trimesh.Trimesh):
        return Mesh_Node(label=label, mesh=source, prim_type="Mesh")

    if isinstance(source, trimesh.Scene):
        _nds_map: dict[str, Base_Node] = {}

        # Pass 1: 그래프 내 모든 노드를 독립된 인스턴스로 생성 및 해시맵 등록
        for _node_name in source.graph.nodes:
            _trans, _geo_name = source.graph.get(_node_name)
            _matrix = np.array(_trans, dtype=np.float32)

            # 지오메트리 매핑 확인 및 노드 타입 결정
            if _geo_name is not None and _geo_name in source.geometry:
                _nds_map[_node_name] = Mesh_Node(
                    label=_node_name,
                    local_matrix=_matrix,
                    mesh=source.geometry[_geo_name],
                    prim_type="Mesh",
                )
            else:
                _nds_map[_node_name] = Group_Node(
                    label=_node_name,
                    local_matrix=_matrix,
                    prim_type="Xform",
                )

        # Pass 2: 해시맵을 활용한 O(1) 부모 탐색 및 트리 계층(Edge) 링킹
        _root = Group_Node(label=label, prim_type="Stage")

        for _node_name in source.graph.nodes:
            _parent_name = source.graph.transforms.parents.get(_node_name)
            _node_obj = _nds_map[_node_name]

            if _parent_name is None:
                _root.children.append(_node_obj)
            else:
                _nds_map[_parent_name].children.append(_node_obj)

        return _root

    return Group_Node(label="empty")
