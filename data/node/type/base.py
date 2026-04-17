from __future__ import annotations
from dataclasses import dataclass, field, InitVar
from typing import Literal, ClassVar
import numpy as np

from python_toolbox.project import Base_Config


# USD의 Prim(Primitive) 스키마를 추종하는 타입 정의
PrimType = Literal[
    "Stage", "Xform", "Mesh", "Material",
    "Shader", "Camera", "PhysicsScene", "SkelRoot", "Empty"
]

@dataclass
class Base_Node(Base_Config):
    """USD 파이프라인 및 레이아웃 편집을 위한 3D 씬 노드 코어 구조체임."""
    label: str = "obj"
    prim_type: PrimType = "Xform"
    local_matrix: np.ndarray = field(
        default_factory=lambda: np.eye(4, dtype=np.float32)
    )
    local_matrix_meta: InitVar[list | None] = None
    source_key: str | None = None
    children: list[Base_Node] = field(default_factory=list)
    visible: bool = True

    # 순환 참조 방지 및 역탐색을 위한 부모 포인터 (repr 출력 제외)
    parent: Base_Node | None = field(default=None, repr=False)

    # 직렬화: local_matrix → local_matrix_meta 키로 flat list 출력
    __exclude_serialize__: ClassVar[set[str]] = {
        "parent", "_matrix_cache", "_is_dirty"}
    __custom_keys__: ClassVar[dict[str, str]] = {
        "local_matrix": "local_matrix_meta",
    }
    __custom_serializers__: ClassVar[dict] = {
        "local_matrix": lambda m: m.flatten().tolist(),
        "children": lambda ch: [c.Serialize() for c in ch],
    }

    _matrix_cache: np.ndarray | None = field(
        default=None, init=False, repr=False)
    _is_dirty: bool = field(default=True, init=False, repr=False)

    def __post_init__(self, local_matrix_meta: list | None):
      if local_matrix_meta is not None:
          self.local_matrix = np.asarray(
              local_matrix_meta, dtype=np.float32
          ).reshape(4, 4)

    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        if key in ("local_matrix", "parent"):
            self._Mark_dirty()

    def _Mark_dirty(self) -> None:
        """현재 노드 및 자식 노드의 행렬 캐시를 무효화함."""
        self._is_dirty = True
        if hasattr(self, "children"):
            for _child in self.children:
                if hasattr(_child, "_Mark_dirty"):
                    _child._Mark_dirty()

    @property
    def is_renderable(self) -> bool:
        """부모 체인 전체가 visible일 때만 렌더링 대상으로 판정함.

        Returns:
            bool: 렌더링 참가 여부.
        """
        if not self.visible:
            return False
        if self.parent is None:
            return True
        return self.parent.is_renderable

    @property
    def world_matrix(self) -> np.ndarray:
        """루트부터 현재 노드까지 누적된 월드 변환 행렬을 계산하여 반환함.

        Returns:
            np.ndarray: 4x4 월드 변환 행렬 (Float32).
        """
        if not self._is_dirty and self._matrix_cache is not None:
            return self._matrix_cache

        if self.parent is None:
            self._matrix_cache = self.local_matrix.copy()
        else:
            # 행렬 곱셈 순서: Parent * Local (부모 좌표계 기준 변환)
            self._matrix_cache = self.parent.world_matrix @ self.local_matrix

        self._is_dirty = False
        return self._matrix_cache

    @property
    def prim_path(self) -> str:
        """USD 포맷 익스포트에 필요한 절대 네임스페이스 경로를 산출함.

        Returns:
            str: '/Root/Child/SubChild' 형태의 경로 문자열.
        """
        if self.parent is None:
            return f"/{self.label}"

        return f"{self.parent.prim_path}/{self.label}"

    def Set_parent(self, new_parent: Base_Node | None) -> None:
        """안전하게 부모 참조를 갱신함.

        Note:
            이 메서드는 자식 리스트(children)를 조작하지 않으므로,
            실제 트리 구조 변경은 Scene_Tree(Manager)를 통해 수행되어야 함.
        """
        self.parent = new_parent

    def Clone(self, label_name: str | None = None) -> Base_Node:
        """자신과 하위 노드들을 깊은 복사(Deep Copy)하여 독립된 인스턴스를 생성함.

        Args:
            label_name (str | None): 복제될 노드의 새로운 식별자.

        Returns:
            Scene_Node: 복제된 최상위 노드.
        """
        _new_node = self.__class__(
            label=self.label if label_name is None else label_name,
            prim_type=self.prim_type,
            local_matrix=self.local_matrix.copy(),
            source_key=self.source_key,
            visible=self.visible,
        )

        for _child in self.children:
            _cloned_child = _child.Clone()
            _cloned_child.Set_parent(_new_node)
            _new_node.children.append(_cloned_child)

        return _new_node


