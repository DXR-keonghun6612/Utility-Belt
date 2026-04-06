import numpy as np
from OpenGL.GL import GL_ELEMENT_ARRAY_BUFFER
from OpenGL.arrays import vbo


class GPU_Resource_Manager:
    """CPU 상의 Trimesh 데이터를 GPU VBO 버퍼로 매핑하고 재사용을 관리함."""

    def __init__(self):
        self._cache: dict[int, dict] = {}

    def Sync_mesh(self, mesh) -> dict | None:
        """메시의 정점, 법선, 인덱스 데이터를 VBO로 업로드하거나 이미 적재된 캐시를 반환함.

        Args:
            mesh: Trimesh 객체.

        Returns:
            dict: 생성된 VBO들을 포함하는 딕셔너리.
        """
        if mesh is None or not hasattr(mesh, "vertices") or not hasattr(mesh, "faces"):
            return None

        _mesh_id = id(mesh)
        if _mesh_id in self._cache:
            return self._cache[_mesh_id]

        _vbos = {}
        
        # 1. 정점 데이터 (Float32)
        _vbos['vertices'] = vbo.VBO(np.ascontiguousarray(mesh.vertices, dtype=np.float32))

        # 2. 법선 데이터 (Float32)
        if hasattr(mesh, "vertex_normals") and mesh.vertex_normals is not None:
            _vbos['normals'] = vbo.VBO(np.ascontiguousarray(mesh.vertex_normals, dtype=np.float32))

            # Normal Pass 전용 인코딩 색상 (Uint8) 계산 및 업로드
            _colors = np.ascontiguousarray(
                ((mesh.vertex_normals + 1.0) * 127.5).clip(0, 255).astype(np.uint8)
            )
            _vbos['normal_colors'] = vbo.VBO(_colors)

        # 3. 인덱스 데이터 (Uint32)
        _vbos['faces'] = vbo.VBO(np.ascontiguousarray(mesh.faces, dtype=np.uint32), target=GL_ELEMENT_ARRAY_BUFFER)
        _vbos['face_count'] = len(mesh.faces) * 3

        self._cache[_mesh_id] = _vbos
        return _vbos

    def Clear(self) -> None:
        """모든 VBO 캐시를 비우고 GPU 메모리를 반환함."""
        for _vbos in self._cache.values():
            for _v in _vbos.values():
                if hasattr(_v, "delete"):
                    _v.delete()
        self._cache.clear()
