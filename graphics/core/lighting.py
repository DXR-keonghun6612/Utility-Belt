"""고정 파이프라인 Phong 조명 GL 상태 구성 헬퍼.

viewport 실시간 렌더러와 RGB_Pass가 공유함. 호출자는 인자만 다르게 주입함.
"""
from __future__ import annotations

from typing import Sequence

from OpenGL.GL import (
    glEnable, glLightfv, glLightModeli, glMaterialfv, glMaterialf,
    GL_LIGHTING, GL_LIGHT0, GL_COLOR_MATERIAL, GL_NORMALIZE,
    GL_LIGHT_MODEL_TWO_SIDE,
    GL_POSITION, GL_DIFFUSE, GL_AMBIENT, GL_SPECULAR,
    GL_FRONT_AND_BACK, GL_SHININESS,
)


# 기본값 — viewport/오프라인 렌더 양쪽에서 무난한 값
DEFAULT_LIGHT_POSITION:    Sequence[float] = (0.0, 1.0, 0.0, 0.0)
DEFAULT_LIGHT_DIFFUSE:     Sequence[float] = (1.0, 1.0, 1.0, 1.0)
DEFAULT_LIGHT_AMBIENT:     Sequence[float] = (0.15, 0.15, 0.15, 1.0)
DEFAULT_LIGHT_SPECULAR:    Sequence[float] = (1.0, 1.0, 1.0, 1.0)
DEFAULT_MATERIAL_SPECULAR: Sequence[float] = (0.6, 0.6, 0.6, 1.0)
DEFAULT_MATERIAL_SHININESS: float = 96.0


def Apply_phong_lighting(
    light_position:    Sequence[float] = DEFAULT_LIGHT_POSITION,
    light_diffuse:     Sequence[float] = DEFAULT_LIGHT_DIFFUSE,
    light_ambient:     Sequence[float] = DEFAULT_LIGHT_AMBIENT,
    light_specular:    Sequence[float] = DEFAULT_LIGHT_SPECULAR,
    material_specular: Sequence[float] = DEFAULT_MATERIAL_SPECULAR,
    material_shininess: float = DEFAULT_MATERIAL_SHININESS,
) -> None:
    """Phong 조명 파라미터를 GL 상태에 적용함.

    주의: glLightfv(GL_POSITION)은 호출 시점의 modelview 행렬로 변환되어
    eye space에 저장됨. 호출부가 어떤 공간 기준을 원하는지에 따라
    modelview 상태를 맞춰둔 뒤 호출해야 함
    (월드 고정광: view 행렬 로드 후 호출 / 헤드라이트: identity 상태에서 호출).

    GL_COLOR_MATERIAL 기본 모드(GL_AMBIENT_AND_DIFFUSE)는 specular를 추적하지
    않으므로 머티리얼 specular는 glMaterialfv로 직접 지정함.
    """
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    # 스케일 변환이 섞인 노드의 노멀도 정상 동작하도록 강제 정규화
    glEnable(GL_NORMALIZE)
    # 양면 조명 — non-watertight 메시의 노멀 외향 판정 불가로 발생하는 반전
    # 증상을 우회함. ROADMAP의 노멀 복구 과제 완료 시 제거 예정.
    glLightModeli(GL_LIGHT_MODEL_TWO_SIDE, 1)

    glLightfv(GL_LIGHT0, GL_POSITION, light_position)
    glLightfv(GL_LIGHT0, GL_DIFFUSE, light_diffuse)
    glLightfv(GL_LIGHT0, GL_AMBIENT, light_ambient)
    glLightfv(GL_LIGHT0, GL_SPECULAR, light_specular)

    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, material_specular)
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, material_shininess)


def Set_light_position(light_position: Sequence[float]) -> None:
    """GL_LIGHT0의 위치만 갱신함 (호출 시점 modelview 기준으로 eye space 변환됨)."""
    glLightfv(GL_LIGHT0, GL_POSITION, light_position)
