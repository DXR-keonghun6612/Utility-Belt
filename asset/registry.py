from pathlib import Path
from scene.node import Scene_Node
from asset.io.loader import load_file


class Asset_Registry:
    """3D 에셋의 디스크 I/O 최소화 및 메모리 재사용을 관리하는 캐시 레지스트리임."""

    def __init__(self):
        """절대 경로를 키로 사용하는 내부 캐시 딕셔너리를 초기화함."""
        self._cache: dict[Path, Scene_Node] = {}

    def Get(self, file_path: str | Path) -> Scene_Node:
        """파일을 파싱하거나 이미 적재된 캐시에서 복제본을 반환함.

        Args:
            file_path (str | Path): 로드할 에셋의 상대 또는 절대 경로.

        Returns:
            Scene_Node: 무거운 지오메트리 데이터를 공유하는 인스턴스화된 씬 노드.
        """
        _path = Path(file_path).resolve()

        # 캐시 히트(Cache Hit): I/O 및 파싱 비용 Zero
        if _path in self._cache:
            return self._cache[_path].Clone()

        # 캐시 미스(Cache Miss): 물리적 파일 로드 및 캐시 등록
        _new_node = load_file(_path)
        self._cache[_path] = _new_node

        # 원본 보호를 위해 복제본 반환
        return _new_node.Clone()

    def Remove(self, register_key: str | Path) -> bool:
        """특정 에셋을 메모리 캐시에서 명시적으로 해제함."""
        _path = Path(register_key).resolve()
        if _path in self._cache:
            del self._cache[_path]
            return True
        return False

    def Clear_cache(self) -> None:
        """모든 에셋 캐시를 비워 메모리를 반환함."""
        self._cache.clear()