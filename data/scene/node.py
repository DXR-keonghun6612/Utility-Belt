from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Any
import numpy as np

# USD의 Prim(Primitive) 스키마를 추종하는 타입 정의
PrimType = Literal[
    "Stage", "Xform", "Mesh", "Material",
    "Shader", "Camera", "PhysicsScene", "SkelRoot", "Empty"
]

@dataclass
class Scene_Node:
    """USD 파이프라인 및 레이아웃 편집을 위한 3D 씬 노드 코어 구조체임."""
    label: str = "obj"
    prim_type: PrimType = "Xform"
    local_matrix: np.ndarray = field(
        default_factory=lambda: np.eye(4, dtype=np.float32)
    )
    children: list[Scene_Node] = field(default_factory=list)
    
    # 순환 참조 방지 및 역탐색을 위한 부모 포인터 (repr 출력 제외)
    parent: Scene_Node | None = field(default=None, repr=False)
    
    # Trimesh 지오메트리 데이터를 보관함 (의존성 최소화를 위해 타입 힌트는 Any 처리 가능하나 직관성을 위해 유지)
    mesh: Any | None = field(default=None, repr=False)

    # Camera_Intrinsic 인스턴스. prim_type="Camera" 노드에만 사용됨
    intrinsic: Any | None = field(default=None, repr=False)

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
        
        단, 무거운 메쉬(Mesh) 데이터는 얕은 복사(Shallow Copy)로 메모리를 공유(Instancing)함.
        
        Args:
            label_name (str | None): 복제될 노드의 새로운 식별자.
            
        Returns:
            Scene_Node: 복제된 최상위 노드.
        """
        _new_node = Scene_Node(
            label=self.label if label_name is None else label_name,
            prim_type=self.prim_type,
            local_matrix=self.local_matrix.copy(), 
            mesh=self.mesh 
        )
        
        for _child in self.children:
            _cloned_child = _child.Clone()
            _cloned_child.Set_parent(_new_node)
            _new_node.children.append(_cloned_child)
            
        return _new_node
