from pathlib import Path
import trimesh
import numpy as np
from scene.node import Scene_Node, PrimType

def load_obj(file_path: Path) -> Scene_Node:
    """OBJ 파일을 파싱하여 Scene_Node 트리로 반환함.
    
    Args:
        file_path (Path): 로드할 OBJ 파일 경로.
        
    Returns:
        Scene_Node: 생성된 씬 노드 구조의 루트.
    """
    _loaded = trimesh.load(file_path)
    return _parse_trimesh_scene(_loaded, label=file_path.stem)


def _parse_trimesh_scene(
    source: trimesh.Geometry, label: str = "obj"
) -> Scene_Node:
    """trimesh 객체의 평면화된 그래프 데이터를 기반으로 트리 계층을 조립함.

    Args:
        source (trimesh.Geometry): 파싱할 trimesh 지오메트리 객체.
        label (str): 루트 노드에 부여할 식별자 이름.

    Returns:
        Scene_Node: 조립이 완료된 계층 구조의 최상단 루트 노드.
    """
    if isinstance(source, trimesh.Trimesh):
        return Scene_Node(label=label, mesh=source, prim_type="Mesh")

    if isinstance(source, trimesh.Scene):
        _nds_map: dict[str, Scene_Node] = {}

        # Pass 1: 그래프 내 모든 노드를 독립된 인스턴스로 생성 및 해시맵 등록
        for _node_name in source.graph.nodes:
            _trans, _geo_name = source.graph.get(_node_name)
            _matrix = np.array(_trans, dtype=np.float32)

            _current_mesh = None
            _p_type: PrimType = "Xform"

            # 지오메트리 매핑 확인 및 노드 타입 결정
            if _geo_name is not None and _geo_name in source.geometry:
                _current_mesh = source.geometry[_geo_name]
                _p_type = "Mesh"

            _nds_map[_node_name] = Scene_Node(
                label=_node_name,
                local_matrix=_matrix,
                mesh=_current_mesh,
                prim_type=_p_type
            )

        # Pass 2: 해시맵을 활용한 O(1) 부모 탐색 및 트리 계층(Edge) 링킹
        _root = Scene_Node(label=label, prim_type="Stage")
        
        for _node_name in source.graph.nodes:
            _parent_name = source.graph.transforms.parents.get(_node_name)
            _node_obj = _nds_map[_node_name]

            # 최상단 노드 분기
            if _parent_name is None:
                _root.children.append(_node_obj)
            # 하위 노드 링킹 분기
            else:
                _nds_map[_parent_name].children.append(_node_obj)

        return _root

    return Scene_Node(label="empty")