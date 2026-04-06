"""바이너리 3D 포맷(OBJ, USD 등)의 로드를 확장자 기반으로 라우팅하는 모듈.

JSON 직렬화 파일(.json)은 data.scene.scene_file에서 처리함.
"""
from pathlib import Path
from data.scene.node import Scene_Node
from data.io.obj import load_obj
# from data.io.gltf import load_gltf  # 향후 확장 예시

# 확장자별 파싱 함수 매핑 딕셔너리
_LOADER_REGISTRY = {
    ".obj": load_obj,
}

def load_file(file_path: str | Path) -> Scene_Node:
    """확장자를 분석하여 적절한 파서 모듈로 라우팅함.
    
    Args:
        file_path (str | Path): 로드할 3D 파일 경로.
        
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
    _parser = _LOADER_REGISTRY.get(_ext)

    if not _parser:
        raise ValueError(f"지원하지 않는 파일 형식임: {_ext}")

    return _parser(_path)