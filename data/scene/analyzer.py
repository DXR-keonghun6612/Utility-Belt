import numpy as np
import trimesh
from data.scene.node import Scene_Node
from data.scene.node.mesh import Mesh_Node
from data.scene.node.base import walk_nodes

class Scene_Analyzer:
    """씬 트리 내부의 메쉬 데이터 중복 및 기하학적 일치율을 분석하는 유틸리티 클래스."""
    
    @staticmethod
    def _Is_mesh_node(node: Scene_Node) -> bool:
        """노드가 메쉬 객체를 포함하고 있는지 검사합니다."""
        return isinstance(node, Mesh_Node) and node.mesh is not None

    @classmethod
    def Find_exact_duplicates(cls, root: Scene_Node, tol: float = 1e-5) -> dict[int, list[Mesh_Node]]:
        """정점과 면 배열이 허용 오차 내에서 완벽히 일치하는 메쉬들을 그룹화함.
        
        서로 다른 경로(Key)로 로드되었거나 독립적으로 생성되었더라도, 
        실제 기하학적 데이터가 완벽하게 동일한(Exact Match) 객체들을 식별합니다.

        Args:
            root: 탐색을 시작할 씬 루트 노드.
            tol: 부동소수점 비교를 위한 허용 오차.

        Returns:
            dict: 첫 번째로 발견된 원본 메쉬의 id()를 키로 하고, 동일한 메쉬 노드들의 리스트를 값으로 가짐.
        """
        _mesh_nodes = list(walk_nodes(root, cls._Is_mesh_node))
        _duplicates: dict[int, list[Mesh_Node]] = {}
        _visited: set[int] = set()

        for i, _node_a in enumerate(_mesh_nodes):
            _id_a = id(_node_a.mesh)
            
            # 이미 다른 그룹에 편입된 메쉬면 건너뜀
            if _id_a in _visited:
                continue

            _group = [_node_a]
            _visited.add(_id_a)

            # A 이후의 다른 노드들과 비교
            for j in range(i + 1, len(_mesh_nodes)):
                _node_b = _mesh_nodes[j]
                _id_b = id(_node_b.mesh)
                
                # B가 이미 처리된 노드라면 비교할 필요 없음
                if _id_b in _visited:
                    continue

                # 동일한 파이썬 객체를 참조하는 인스턴스거나 배열이 완전히 같으면 그룹화
                if _id_a == _id_b or cls.Is_exact_match(_node_a.mesh, _node_b.mesh, tol):
                    _group.append(_node_b)
                    _visited.add(_id_b)

            # 중복된 항목이 1개 이상 있을 때만 결과 딕셔너리에 추가
            if len(_group) > 1:
                _duplicates[_id_a] = _group

        return _duplicates

    @staticmethod
    def Is_exact_match(mesh_a, mesh_b, tol: float = 1e-5) -> bool:
        """두 메쉬의 배열 값이 완벽히 일치하는지 빠른 기각을 포함하여 검사함."""
        if mesh_a is None or mesh_b is None:
            return False

        # 1. 개수 비교 (빠른 기각)
        if len(mesh_a.vertices) != len(mesh_b.vertices) or len(mesh_a.faces) != len(mesh_b.faces):
            return False
            
        # 2. 형상 바운딩 박스 비교 (빠른 기각)
        if not np.allclose(mesh_a.extents, mesh_b.extents, atol=tol):
            return False
            
        # 3. 정점 및 인덱스 배열 전수 비교
        return (np.allclose(mesh_a.vertices, mesh_b.vertices, atol=tol) and 
                np.array_equal(mesh_a.faces, mesh_b.faces))

    @classmethod
    def Calculate_match_rate(cls, mesh_a, mesh_b, num_samples: int = 5000, threshold: float = 0.01) -> float:
        """표면 샘플링(Point Cloud)을 통한 두 메쉬의 시각적/기하학적 형상 일치율을 계산함.
        
        토폴로지(면의 구성)가 다르거나 3D 툴 익스포트 시 정점 순서가 뒤섞여 저장되었더라도,
        실제 3D 공간상의 '외형'이 얼마나 동일하게 겹치는지 평가할 수 있습니다.
        
        Args:
            mesh_a, mesh_b: 비교할 Trimesh 객체.
            num_samples: 표면에서 추출할 무작위 점의 개수.
            threshold: '같은 표면에 있다'고 간주할 최대 거리 오차(미터 단위).
            
        Returns:
            float: 0.0(완전 다름) ~ 1.0(완벽 일치) 사이의 비율.
        """
        if mesh_a is None or mesh_b is None:
            return 0.0
            
        # 1. 두 메쉬 표면에서 점을 무작위로 샘플링
        pts_a, _ = trimesh.sample.sample_surface(mesh_a, num_samples)
        pts_b, _ = trimesh.sample.sample_surface(mesh_b, num_samples)
        
        # 2. 각 샘플링된 점들에서 반대쪽 메쉬 표면까지의 가장 가까운 최단 거리를 측정
        # on_surface()는 (closest_points, distances, face_indices)를 반환함
        _, dist_a_to_b, _ = mesh_b.nearest.on_surface(pts_a)
        _, dist_b_to_a, _ = mesh_a.nearest.on_surface(pts_b)
        
        # 3. 지정된 오차(threshold) 이내로 가까운 점들의 비율 계산
        match_a = np.sum(dist_a_to_b < threshold) / num_samples
        match_b = np.sum(dist_b_to_a < threshold) / num_samples
        
        # 조화 평균 또는 산술 평균으로 최종 일치율 점수 반환
        return float((match_a + match_b) / 2.0)
