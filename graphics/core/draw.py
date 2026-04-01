from OpenGL.GL import (
    glPushMatrix, glPopMatrix, glMultMatrixf,
    glEnableClientState, glDisableClientState,
    glVertexPointer, glNormalPointer, glDrawElements,
    GL_VERTEX_ARRAY, GL_NORMAL_ARRAY,
    GL_TRIANGLES, GL_FLOAT, GL_UNSIGNED_INT,
)

from data.scene.node import Scene_Node


def Draw_mesh(mesh) -> None:
    """Trimesh 지오메트리 데이터를 고정 파이프라인으로 렌더링함."""
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


def Walk_scene(node: Scene_Node) -> None:
    """씬 트리를 재귀 순회하며 메쉬를 그림 (기본 패스)."""
    glPushMatrix()
    glMultMatrixf(node.local_matrix.T)

    if node.mesh:
        Draw_mesh(node.mesh)

    for _child in node.children:
        Walk_scene(_child)

    glPopMatrix()
