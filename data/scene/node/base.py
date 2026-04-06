from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, ClassVar
import numpy as np

from python_toolbox.project import Base_Config


# ==========================================
# 변환 행렬 유틸리티
# ==========================================

def Build_transform(
    tx: float = 0.0, ty: float = 0.0, tz: float = 0.0,
    rx: float = 0.0, ry: float = 0.0, rz: float = 0.0
) -> np.ndarray:
    """Euler 회전(XYZ, degrees) + 이동으로 4x4 변환 행렬을 구성함.

    Args:
        tx, ty, tz: 이동량 (씬 좌표계).
        rx, ry, rz: 회전량 (degrees, XYZ Euler).

    Returns:
        np.ndarray: 4x4 변환 행렬 (float32).
    """
    _rx, _ry, _rz = np.radians(rx), np.radians(ry), np.radians(rz)

    _cx, _sx = np.cos(_rx), np.sin(_rx)
    _cy, _sy = np.cos(_ry), np.sin(_ry)
    _cz, _sz = np.cos(_rz), np.sin(_rz)

    # Rz @ Ry @ Rx (extrinsic XYZ 순서)
    _m = np.eye(4, dtype=np.float32)
    _m[0, 0] = _cy * _cz
    _m[0, 1] = _sx * _sy * _cz - _cx * _sz
    _m[0, 2] = _cx * _sy * _cz + _sx * _sz
    _m[1, 0] = _cy * _sz
    _m[1, 1] = _sx * _sy * _sz + _cx * _cz
    _m[1, 2] = _cx * _sy * _sz - _sx * _cz
    _m[2, 0] = -_sy
    _m[2, 1] = _sx * _cy
    _m[2, 2] = _cx * _cy

    _m[0, 3] = tx
    _m[1, 3] = ty
    _m[2, 3] = tz

    return _m


def Decompose_transform(matrix: np.ndarray) -> tuple[float, ...]:
    """4x4 변환 행렬에서 이동 + Euler 회전(XYZ, degrees)을 역분해함.

    Args:
        matrix: 4x4 변환 행렬.

    Returns:
        tuple: (tx, ty, tz, rx, ry, rz).
    """
    _tx, _ty, _tz = float(matrix[0, 3]), float(matrix[1, 3]), float(matrix[2, 3])

    _sy = -float(matrix[2, 0])
    _cy = np.sqrt(float(matrix[0, 0])**2 + float(matrix[1, 0])**2)

    if _cy > 1e-6:
        _rx = np.degrees(np.arctan2(float(matrix[2, 1]), float(matrix[2, 2])))
        _ry = np.degrees(np.arctan2(_sy, _cy))
        _rz = np.degrees(np.arctan2(float(matrix[1, 0]), float(matrix[0, 0])))
    else:
        # 짐벌 락 근사
        _rx = np.degrees(np.arctan2(-float(matrix[1, 2]), float(matrix[1, 1])))
        _ry = np.degrees(np.arctan2(_sy, _cy))
        _rz = 0.0

    return (_tx, _ty, _tz, _rx, _ry, _rz)


# USD의 Prim(Primitive) 스키마를 추종하는 타입 정의
PrimType = Literal[
    "Stage", "Xform", "Mesh", "Material",
    "Shader", "Camera", "PhysicsScene", "SkelRoot", "Empty"
]

@dataclass
class Scene_Node(Base_Config):
    """USD 파이프라인 및 레이아웃 편집을 위한 3D 씬 노드 코어 구조체임."""
    label: str = "obj"
    prim_type: PrimType = "Xform"
    local_matrix: np.ndarray = field(
        default_factory=lambda: np.eye(4, dtype=np.float32)
    )
    # 메시 원본 파일 경로 추적 (직렬화 시 mesh 대신 사용)
    source_path: str | None = None
    children: list[Scene_Node] = field(default_factory=list)
    visible: bool = True

    # 순환 참조 방지 및 역탐색을 위한 부모 포인터 (repr 출력 제외)
    parent: Scene_Node | None = field(default=None, repr=False)

    # 직렬화 규칙: parent는 JSON 변환 불가
    __exclude_serialize__: ClassVar[set[str]] = {"parent"}
    __custom_serializers__: ClassVar[dict] = {
        "local_matrix": lambda m: m.flatten().tolist(),
        "children": lambda ch: [c.Serialize() for c in ch],
    }

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
        if self.parent is None:
            return self.local_matrix.copy()

        # 행렬 곱셈 순서: Parent * Local (부모 좌표계 기준 변환)
        return self.parent.world_matrix @ self.local_matrix

    @property
    def prim_path(self) -> str:
        """USD 포맷 익스포트에 필요한 절대 네임스페이스 경로를 산출함.

        Returns:
            str: '/Root/Child/SubChild' 형태의 경로 문자열.
        """
        if self.parent is None:
            return f"/{self.label}"

        return f"{self.parent.prim_path}/{self.label}"

    def Set_parent(self, new_parent: Scene_Node | None) -> None:
        """안전하게 부모 참조를 갱신함.

        Note:
            이 메서드는 자식 리스트(children)를 조작하지 않으므로,
            실제 트리 구조 변경은 Scene_Tree(Manager)를 통해 수행되어야 함.
        """
        self.parent = new_parent

    def Clone(self, label_name: str | None = None) -> Scene_Node:
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
            source_path=self.source_path,
            visible=self.visible,
        )

        for _child in self.children:
            _cloned_child = _child.Clone()
            _cloned_child.Set_parent(_new_node)
            _new_node.children.append(_cloned_child)

        return _new_node
