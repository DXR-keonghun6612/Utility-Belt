"""바이너리 3D 포맷(OBJ, USD 등)의 로드를 확장자 기반으로 라우팅하는 모듈.

asset 모드: Mesh_Asset 리스트 반환 (순수 지오메트리 데이터).
node 모드: Scene_Node 트리 반환 (씬 그래프 계층 구조).
JSON 직렬화 파일(.json)은 data.node.stage.Stage_Controller에서 처리함.
"""
from __future__ import annotations
from pathlib import Path

from data.asset.cache import ASSET_CACHE
from data.asset.type.mesh import Mesh_Asset
from data.node.type import Base_Node
from data.node.utils.traversal import walk_nodes
from data.io.obj import load_obj_as_asset, load_obj_as_node

# 확장자별 파싱 함수 매핑
_ASSET_LOADER = {
    ".obj": load_obj_as_asset,
}

_NODE_LOADER = {
    ".obj": load_obj_as_node,
}


def load_as_asset(file_path: str | Path) -> list[Mesh_Asset]:
    """파일을 파싱하여 Mesh_Asset 리스트로 반환함.

    Args:
        file_path: 로드할 3D 파일 경로.

    Returns:
        list[Mesh_Asset]: 파싱된 에셋 목록.

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때.
        ValueError: 지원하지 않는 확장자일 때.
    """
    _path = Path(file_path)
    if not _path.exists():
        raise FileNotFoundError(f"경로를 찾을 수 없음: {_path}")

    _ext = _path.suffix.lower()
    _parser = _ASSET_LOADER.get(_ext)

    if not _parser:
        raise ValueError(f"지원하지 않는 파일 형식임: {_ext}")

    return _parser(_path)


def load_as_node(file_path: str | Path) -> Base_Node:
    """파일을 파싱하여 Scene_Node 트리로 반환함.

    Args:
        file_path: 로드할 3D 파일 경로.

    Returns:
        Scene_Node: 생성된 씬 노드 루트.

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때.
        ValueError: 지원하지 않는 확장자일 때.
    """
    _path = Path(file_path)
    if not _path.exists():
        raise FileNotFoundError(f"경로를 찾을 수 없음: {_path}")

    _ext = _path.suffix.lower()
    _parser = _NODE_LOADER.get(_ext)

    if not _parser:
        raise ValueError(f"지원하지 않는 파일 형식임: {_ext}")

    return _parser(_path)


# 하위 호환: stage.py의 _Build_node에서 load_file로 참조
load_file = load_as_node


def Resolve_meshes(root: Base_Node, strict: bool = True) -> None:
    """root 하위 Mesh 노드의 source_key로 지오메트리를 1회 로드 후 공유 주입함.

    전역 ASSET_CACHE를 통해 디스크 I/O를 1회로 줄이고, share=True 모드로
    조회하여 동일 source_key를 참조하는 모든 노드가 같은 trimesh 인스턴스를
    공유하도록 보장함 (GPU VBO 캐시 단일화 직결).

    Args:
        root: 순회 시작 노드.
        strict: True면 source_key 누락/로드 실패 시 예외 전파.
                False면 해당 노드는 mesh=None 유지하고 계속 진행.

    Raises:
        ValueError: strict=True 이며 source_key가 None이거나 추출 실패 시.
        FileNotFoundError: strict=True 이며 source_key 파일이 존재하지 않을 때.
    """
    _is_unresolved = (
        lambda n: n.prim_type == "Mesh" and getattr(n, "mesh", None) is None
    )

    for _node in walk_nodes(root, _is_unresolved):
        _key = _node.source_key

        if _key is None:
            if strict:
                raise ValueError(
                    f"Mesh 노드 '{_node.prim_path}'의 source_key가 None임."
                )
            continue

        _cached = ASSET_CACHE.Get(_key, share=True)
        if _cached is None:
            try:
                _assets = load_as_asset(_key)
            except (FileNotFoundError, ValueError):
                if strict:
                    raise
                continue
            ASSET_CACHE.Register(_key, _assets)
            _cached = ASSET_CACHE.Get(_key, share=True)

        _mesh_asset = next(
            (_a for _a in (_cached or []) if isinstance(_a, Mesh_Asset)),
            None,
        )
        if _mesh_asset is None:
            if strict:
                raise ValueError(
                    f"source_key '{_key}'에서 Mesh_Asset을 추출하지 못함."
                )
            continue

        _node.mesh = _mesh_asset.geometry
