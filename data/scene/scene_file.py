"""장면 트리의 직렬화(Save) 및 역직렬화(Load) 처리 모듈.

Scene_Node가 Base_Config을 상속하므로 직렬화는 Serialize()로 자동 처리됨.
역직렬화는 재귀 트리 복원 + 메시 재로드 + intrinsic 복원이 필요하여 커스텀 빌더를 사용함.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np

from python_toolbox.file import Utils as File_Utils
from python_toolbox.project import Build_from_args

from data.scene.node import Scene_Node
from data.scene.node.mesh import Mesh_Node
from data.scene.node.camera import Camera_Intrinsic, Camera_Node


def save_scene(root: Scene_Node, file_path: Path) -> None:
    """장면 트리를 JSON 파일로 저장함.

    Args:
        root: 저장할 장면 트리의 루트 노드.
        file_path: 저장 대상 JSON 파일 경로.
    """
    _data = root.Serialize()
    _base_dir = file_path.parent.resolve()
    _Convert_to_relative_paths(_data, _base_dir)
    File_Utils.Write_to(file_path, _data)


def load_scene(file_path: Path) -> Scene_Node:
    """JSON 파일에서 장면 트리를 복원함.

    Args:
        file_path: 로드할 JSON 파일 경로.

    Returns:
        Scene_Node: 복원된 장면 트리의 루트 노드.

    Raises:
        ValueError: 파일 읽기 또는 파싱 실패 시.
    """
    _is_ok, _data = File_Utils.Read_from(file_path)

    if not _is_ok or not isinstance(_data, dict):
        raise ValueError(f"장면 파일 읽기 실패: {file_path}")

    _base_dir = file_path.parent.resolve()
    return _Build_node(_data, _base_dir, parent=None)


# ==========================================
# 내부 헬퍼
# ==========================================

def _Build_node(
    data: dict, base_dir: Path, parent: Scene_Node | None
) -> Scene_Node:
    """딕셔너리 데이터에서 prim_type에 따라 적절한 노드 타입을 재귀 복원함."""
    _matrix_raw = data.get("local_matrix")
    if _matrix_raw is not None:
        _matrix = np.array(_matrix_raw, dtype=np.float32).reshape(4, 4)
    else:
        _matrix = np.eye(4, dtype=np.float32)

    _prim_type = data.get("prim_type", "Xform")
    _label = data.get("label", "obj")
    _source = data.get("source_path")
    _visible = data.get("visible", True)

    # source_path → 절대 경로 복원 및 메시 로드
    _mesh = None
    if _source is not None:
        _abs_path = (base_dir / _source).resolve()
        _source = str(_abs_path)
        if _abs_path.exists():
            from data.io.loader import load_file
            _loaded = load_file(_abs_path)
            _mesh = _Collect_mesh(_loaded)

    # prim_type에 따른 노드 타입 분기
    if _prim_type == "Camera":
        _intrinsic_raw = data.get("intrinsic")
        _intrinsic = None
        if _intrinsic_raw is not None and isinstance(_intrinsic_raw, dict):
            _intrinsic = Build_from_args(Camera_Intrinsic, _intrinsic_raw)

        _node = Camera_Node(
            label=_label, prim_type=_prim_type,
            local_matrix=_matrix, source_path=_source,
            visible=_visible, parent=parent,
            intrinsic=_intrinsic,
        )

    elif _prim_type == "Mesh" or _mesh is not None:
        _node = Mesh_Node(
            label=_label, prim_type=_prim_type,
            local_matrix=_matrix, source_path=_source,
            visible=_visible, parent=parent,
            mesh=_mesh,
        )

    else:
        _node = Scene_Node(
            label=_label, prim_type=_prim_type,
            local_matrix=_matrix, source_path=_source,
            visible=_visible, parent=parent,
        )

    # 자식 노드 재귀 복원
    for _child_data in data.get("children", []):
        _child = _Build_node(_child_data, base_dir, parent=_node)
        _node.children.append(_child)

    return _node


def _Collect_mesh(node: Scene_Node):
    """로드된 Scene_Node 트리에서 첫 번째 메시를 추출함."""
    if isinstance(node, Mesh_Node) and node.mesh is not None:
        return node.mesh
    for _child in node.children:
        _found = _Collect_mesh(_child)
        if _found is not None:
            return _found
    return None


def _Convert_to_relative_paths(data: dict, base_dir: Path) -> None:
    """직렬화된 딕셔너리 내 source_path를 상대 경로로 변환함 (in-place)."""
    _source = data.get("source_path")
    if _source is not None:
        try:
            _rel = Path(_source).relative_to(base_dir)
            data["source_path"] = str(_rel)
        except ValueError:
            pass

    for _child in data.get("children", []):
        _Convert_to_relative_paths(_child, base_dir)
