"""pose 구조 — 자리(``position``) + 방향(``rotation``, 단위 quaternion). **3D 로 들고, 2D 는 잘라 쓴다.**

저장 표현은 **이름 붙은 dict** 다::

    {"position": [x, y, z], "rotation": [qx, qy, qz, qw]}

지금 데이터는 전부 평면(이미지 한 장 위의 객체)이지만 **구조는 3D 로 둔다** — 자세를 각도 하나로
시작하면 축이 늘 때 표현을 통째로 갈아야 하고(각 → 축각 → quaternion), 그 순간 이미 저장된 값이 전부
옛 표현이 된다. 3D 로 들고 잘라 쓰는 쪽은 **평면 자세가 3D 자세의 부분집합**이라 갈아탈 일이 없다:
``z = 0``, ``qx = qy = 0``.

## 왜 평탄 7-list 가 아니라 dict 인가

셋은 자리고 넷은 방향이라는 걸 **값 스스로 말한다** — 사이드카를 연 사람이 인덱스를 세지 않아도 되고,
소비처가 ``pose[3]`` 같은 산수를 하지 않는다. 그리고 **키는 늘어날 수 있다**: 주축각의 신뢰도
(``anisotropy``·``flip_margin``)나 스케일을 나중에 한 칸 더 붙일 수 있는데, 평탄 7-list 는 길이가 곧
계약이라 늘리는 순간 옛 값이 전부 깨진다. (지금 안 넣는 이유는 [`gui/TODO.md`](../../gui/TODO.md) 참조.)

``rle`` 이 같은 자리의 선례다 — 인라인 codec 은 스칼라만이 아니라 **구조**(dict)를 그대로 든다.

## 좌표계 — 이미지 좌표에 맞춘 오른손계

``x`` 는 오른쪽, ``y`` 는 **아래**(이미지 행 방향), ``z`` 는 그 둘의 외적이라 **화면 안쪽**이다.
평면 회전은 그 ``z`` 축 회전이고, 각이 양수면 ``+x`` 가 ``+y`` 쪽으로 — 즉 **화면에서 시계방향**이다.
``bbox`` 가 이미 이미지 좌표(y 아래)라, 자세만 수학 좌표(y 위)로 두면 같은 사이드카 안에서 부호
규약이 둘이 된다.

## quaternion 순서는 ``xyzw`` 하나다 (지금은)

실수부가 **뒤**다 — ROS·scipy(``Rotation.as_quat``)·PyBullet 규약. Eigen·Blender 는 ``wxyz`` 라 실제로
갈리는 축이지만, [`bbox`](bbox.py) 처럼 style 칸을 지금 만들지는 않는다: 생산자도 소비처도 하나뿐이라
고를 것이 없다. 둘째 규약이 실제로 들어오면 그때 ``format`` 셋째 칸이 되면 되고, 이 모듈의 함수
시그니처는 안 바뀐다(``style`` 인자가 붙을 뿐).

**정규화는 여기서 하지 않는다** — :func:`From_2d` 는 단위 quaternion 을 만들고, :func:`To_2d` 는 크기를
안 보고 위상만 읽는다(``atan2`` 는 스케일 불변). 손으로 고친 값이 단위가 아니어도 각은 그대로 나온다.
"""

from __future__ import annotations

import math

#: 자리 키 — ``[x, y, z]`` (이미지 픽셀 좌표, y 아래).
POSITION = "position"
#: 방향 키 — ``[qx, qy, qz, qw]`` (단위 quaternion, 실수부 마지막).
ROTATION = "rotation"

#: 평면으로 자를 수 있다고 볼 ``qx``·``qy`` 상한. 평면 자세는 이 둘이 **정확히 0** 이라
#: (:func:`From_2d` 가 그렇게 만든다) 여유는 부동소수 왕복분이면 된다.
PLANAR_TOL = 1e-6


def From_2d(center: tuple[float, float], angle: float) -> dict:
    """평면 자세(중심 + 각) → 저장 표현. ``z = 0``, 회전은 **z 축 하나**.

    Args:
        center: 이미지 좌표 ``(x, y)`` — 픽셀. 보통 mask 무게중심이다.
        angle: z 축 회전각(rad). 양수면 화면에서 시계방향 (위 좌표계 참조).

    Returns:
        ``{"position": [x, y, 0], "rotation": [0, 0, qz, qw]}`` — 단위 quaternion.
    """
    _half = angle / 2.0
    return {POSITION: [float(center[0]), float(center[1]), 0.0],
            ROTATION:  [0.0, 0.0, math.sin(_half), math.cos(_half)]}


def To_2d(pose, *, tol: float = PLANAR_TOL) -> tuple[float, float, float] | None:
    """저장 표현 → 평면 자세 ``(x, y, angle)``. **평면 밖 회전이면 None.**

    ``qx``·``qy`` 가 0 이 아니면 이 자세는 화면 안팎으로 기울어 있다는 뜻이라, 세 값으로 줄이면 그
    기울기가 조용히 사라진다. 그래서 자르지 않고 **부재를 돌려준다** — 3개로 못 줄이는 값을 어떻게
    보일지(7개를 그대로 드러낼지, 투영할지)는 호출 측이 정한다.

    Args:
        pose: :func:`From_2d` 가 낸 dict.
        tol: 평면으로 볼 ``qx``·``qy`` 상한 (:data:`PLANAR_TOL`).

    Returns:
        ``(x, y, angle)`` — ``angle`` 은 ``[-π, π]`` 로 감긴 rad. 평면 밖이면 None.

    Raises:
        ValueError: 키가 없거나 원소 수가 틀릴 때 (모양이 어긋난 값을 0 으로 메우지 않는다).
    """
    _x, _y, _ = Position(pose)
    _qx, _qy, _qz, _qw = Rotation(pose)
    if abs(_qx) > tol or abs(_qy) > tol:
        return None
    return _x, _y, _wrap(2.0 * math.atan2(_qz, _qw))


def Position(pose) -> tuple[float, float, float]:
    """자리 ``(x, y, z)``.

    Raises:
        ValueError: ``position`` 키가 없거나 셋이 아닐 때.
    """
    return tuple(_floats(pose, POSITION, 3))               # type: ignore[return-value]


def Rotation(pose) -> tuple[float, float, float, float]:
    """방향 ``(qx, qy, qz, qw)`` — 실수부가 마지막.

    Raises:
        ValueError: ``rotation`` 키가 없거나 넷이 아닐 때.
    """
    return tuple(_floats(pose, ROTATION, 4))               # type: ignore[return-value]


def _floats(pose, key: str, size: int) -> list[float]:
    """``pose[key]`` 를 float ``size`` 개로 — 없거나 개수가 다르면 실패한다."""
    if not isinstance(pose, dict) or key not in pose:
        raise ValueError(f"pose 에 '{key}' 가 없다 (받은 것: {pose!r})")
    _v = [float(_x) for _x in pose[key]]
    if len(_v) != size:
        raise ValueError(f"pose['{key}'] 는 {size} 개여야 한다 (받은 것: {len(_v)}개)")
    return _v


def _wrap(angle: float) -> float:
    """각을 ``[-π, π]`` 로 감는다.

    ``q`` 와 ``-q`` 는 같은 회전이지만 ``2·atan2(qz, qw)`` 는 그 둘에 ``2π`` 다른 값을 낸다 — 감지
    않으면 같은 자세가 저장 왕복만으로 다른 숫자로 보인다.
    """
    return math.remainder(angle, 2.0 * math.pi)
