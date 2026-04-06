import numpy as np
from OpenGL.GL import (
    glEnableClientState, glDisableClientState,
    glVertexPointer, glNormalPointer, glDrawElements,
    GL_VERTEX_ARRAY, GL_NORMAL_ARRAY,
    GL_TRIANGLES, GL_FLOAT, GL_UNSIGNED_INT,
)


def Draw_mesh(mesh) -> None:
    """Trimesh 지오메트리 데이터를 고정 파이프라인으로 렌더링함.

    Args:
        mesh: Trimesh 객체 (vertices, faces, vertex_normals 속성 보유).
    """
    if mesh is None or not hasattr(mesh, "vertices") or not hasattr(mesh, "faces"):
        return

    glEnableClientState(GL_VERTEX_ARRAY)
    glVertexPointer(3, GL_FLOAT, 0, mesh.vertices)

    if hasattr(mesh, "vertex_normals"):
        glEnableClientState(GL_NORMAL_ARRAY)
        glNormalPointer(GL_FLOAT, 0, mesh.vertex_normals)

    glDrawElements(GL_TRIANGLES, len(mesh.faces) * 3, GL_UNSIGNED_INT, mesh.faces)

    glDisableClientState(GL_VERTEX_ARRAY)
    if hasattr(mesh, "vertex_normals"):
        glDisableClientState(GL_NORMAL_ARRAY)
