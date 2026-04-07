from __future__ import annotations
from pathlib import Path
from copy import deepcopy

from data.asset.type.base import Base_Asset


class Asset_Cache:
    """Base_Asset의 디스크 I/O 최소화 및 메모리 재사용을 관리하는 캐시.

    에셋 타입별로 분리 저장하여 타입 기반 조회 시 전수 순회를 회피함.
    캐시 히트 시 deepcopy로 독립된 인스턴스를 반환하여 원본 보호.
    """

    def __init__(self):
        # { asset_type: { resolved_path: [asset, ...] } }
        self._cache: dict[type[Base_Asset], dict[Path, list[Base_Asset]]] = {}

    def Get(self, file_path: str | Path) -> list[Base_Asset] | None:
        """캐시에서 해당 경로의 모든 타입 에셋을 조회하여 복제본을 반환함.

        Args:
            file_path: 조회할 에셋의 절대 또는 상대 경로.

        Returns:
            list[Base_Asset] | None: 캐시 히트 시 복제된 에셋 목록, 미스 시 None.
        """
        _path = Path(file_path).resolve()
        _result: list[Base_Asset] = []

        for _bucket in self._cache.values():
            if _path in _bucket:
                _result.extend(_bucket[_path])

        return deepcopy(_result) if _result else None

    def Get_all(self) -> list[Base_Asset]:
        """캐시 내 모든 에셋을 단일 리스트로 반환함.

        Returns:
            list[Base_Asset]: 전체 에셋 목록 (원본 참조).
        """
        _all: list[Base_Asset] = []
        for _bucket in self._cache.values():
            for _assets in _bucket.values():
                _all.extend(_assets)
        return _all

    def Get_by_type(self, asset_type: type[Base_Asset]) -> list[Base_Asset]:
        """특정 에셋 타입에 해당하는 모든 에셋을 반환함.

        Args:
            asset_type: 조회할 에셋 클래스 (예: Mesh_Asset, PointCloud_Asset).

        Returns:
            list[Base_Asset]: 해당 타입의 전체 에셋 목록 (원본 참조).
        """
        _bucket = self._cache.get(asset_type)
        if _bucket is None:
            return []

        _all: list[Base_Asset] = []
        for _assets in _bucket.values():
            _all.extend(_assets)
        return _all

    def Register(self, file_path: str | Path, assets: list[Base_Asset]) -> None:
        """에셋 목록을 타입별로 분류하여 캐시에 등록함.

        Args:
            file_path: 등록할 에셋의 파일 경로.
            assets: 캐시할 에셋 목록.
        """
        _path = Path(file_path).resolve()

        # 타입별 분류
        _grouped: dict[type[Base_Asset], list[Base_Asset]] = {}
        for _asset in assets:
            _key = type(_asset)
            _grouped.setdefault(_key, []).append(_asset)

        for _type, _typed_assets in _grouped.items():
            if _type not in self._cache:
                self._cache[_type] = {}
            self._cache[_type][_path] = deepcopy(_typed_assets)

    def Remove(self, file_path: str | Path) -> bool:
        """특정 경로의 에셋을 모든 타입 버킷에서 해제함.

        Returns:
            bool: 제거 성공 여부.
        """
        _path = Path(file_path).resolve()
        _removed = False

        for _bucket in self._cache.values():
            if _path in _bucket:
                del _bucket[_path]
                _removed = True

        return _removed

    def Clear(self) -> None:
        """모든 에셋 캐시를 비움."""
        self._cache.clear()
