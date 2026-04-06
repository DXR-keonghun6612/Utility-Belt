import numpy as np
from OpenGL.GL import (
    glEnableClientState, glDisableClientState,
    glVertexPointer, glNormalPointer, glDrawElements,
    GL_VERTEX_ARRAY, GL_NORMAL_ARRAY,
    GL_TRIANGLES, GL_FLOAT, GL_UNSIGNED_INT,
)

def Draw_mesh(mesh, res_manager=None) -> None:
    """Trimesh 지오메트리 데이터를 고정 파이프라인으로 렌더링함.
    
    GPU_Resource_Manager가 제공된 경우 VBO를 사용하여 대역폭을 최적화함.

    Args:
        mesh: Trimesh 객체 (vertices, faces, vertex_normals 속성 보유).
        res_manager: VBO 캐싱을 처리하는 관리자 객체 (선택).
    """
    if mesh is None or not hasattr(mesh, "vertices") or not hasattr(mesh, "faces"):
        return

    # 1. VBO 기반 렌더링 파이프라인 (고속)
    if res_manager is not None:
        _vbos = res_manager.Sync_mesh(mesh)
        if _vbos is None:
            return

        glEnableClientState(GL_VERTEX_ARRAY)
        _vbos['vertices'].bind()
        glVertexPointer(3, GL_FLOAT, 0, _vbos['vertices'])

        _has_normals = 'normals' in _vbos
        if _has_normals:
            glEnableClientState(GL_NORMAL_ARRAY)
            _vbos['normals'].bind()
            glNormalPointer(GL_FLOAT, 0, _vbos['normals'])

        _vbos['faces'].bind()
        glDrawElements(GL_TRIANGLES, _vbos['face_count'], GL_UNSIGNED_INT, None)
        _vbos['faces'].unbind()

        glDisableClientState(GL_VERTEX_ARRAY)
        _vbos['vertices'].unbind()
        
        if _has_normals:
            glDisableClientState(GL_NORMAL_ARRAY)
            _vbos['normals'].unbind()
        return

    # 2. 클라이언트 배열 기반 렌더링 파이프라인 (폴백/저속)
    glEnableClientState(GL_VERTEX_ARRAY)
    glVertexPointer(3, GL_FLOAT, 0, mesh.vertices)

    if hasattr(mesh, "vertex_normals") and mesh.vertex_normals is not None:
        glEnableClientState(GL_NORMAL_ARRAY)
        glNormalPointer(GL_FLOAT, 0, mesh.vertex_normals)

    glDrawElements(GL_TRIANGLES, len(mesh.faces) * 3, GL_UNSIGNED_INT, mesh.faces)

    glDisableClientState(GL_VERTEX_ARRAY)
    if hasattr(mesh, "vertex_normals") and mesh.vertex_normals is not None:
        glDisableClientState(GL_NORMAL_ARRAY)
