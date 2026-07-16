"""bbox — 축에 정렬된 상자 하나. **차원을 모른다.**

`image/` 가 아니라 여기 사는 이유 — 상자는 라스터의 개념이 아니다. 2d 라벨의 bbox 든 3d points 의 바운딩
볼륨이든 "두 코너로 정해지는 축정렬 영역"은 같은 것이고, 코너·면·리사이즈·히트판정도 같다. 한때 이게
`image/_geom.py` 에 있어서, [`_base.py`](../_base.py) 가 3d 편집기를 받겠다고 선언해놓고도 정작 상자는
라스터 편집기 안에 갇혀 있었다.

**정준형은 ``(2, D)`` float 배열** — ``[lo, hi]``. ``D`` 는 좌표 차원이라 이 파일 어디에도 x·y 가 이름으로
안 나온다(3d 면 그대로 D=3). 그래서 여기엔 cv2 도 Qt 도 없고 numpy 뿐이다 — numpy 가 곧 "차원을 안
박는다"는 말의 구현이다.

**저장 표현과는 `from_flat`/`to_flat` 로만 오간다.** COCO 의 평탄 ``[x0, y0, x1, y1]`` 을 안으로 들이면
"길이가 4"라는 사실이 곳곳에 박혀 차원 무지가 거짓말이 된다 — 평탄화는 경계에서 한 번만 한다.

**세 상태를 가른다** (`is_set` 으로 묻는다 — 배열에 `if` 를 쓰면 ambiguous 로 터진다):

| 값 | 뜻 |
|---|---|
| ``None`` | 상자를 가질 수 없는 대상 (도구가 안 붙는다) |
| ``size == 0`` | 가질 수 있는데 **아직 안 그렸다** |
| ``(2, D)`` | 상자가 있다 |
"""
from __future__ import annotations

import itertools

import numpy as np


def empty() -> np.ndarray:
    """아직 안 그린 상자 — 자리는 있고 값이 없다 (`is_set` 이 False)."""
    return np.zeros((0, 0), float)


def is_set(box: np.ndarray | None) -> bool:
    """실제 상자가 들었나 — ``None``(불가)·빈 것(미작성) 둘 다 False."""
    return box is not None and box.size > 0


def dims(box: np.ndarray) -> int:
    """좌표 차원 ``D``."""
    return int(box.shape[1])


# ── 만들기 ────────────────────────────────────────────────────────────────────
def from_points(a, b) -> np.ndarray:
    """두 점을 감싸는 정규화된 상자 — 어느 방향으로 끌든 ``lo <= hi``."""
    _a, _b = np.asarray(a, float), np.asarray(b, float)
    return np.stack([np.minimum(_a, _b), np.maximum(_a, _b)])


def from_flat(values) -> np.ndarray:
    """평탄 좌표열 → 상자 — ``[x0, y0, x1, y1]`` 처럼 **lo 전부 뒤 hi 전부** 순서다 (COCO).

    Args:
        values: 길이 ``2*D`` 의 수열. 비었으면 `empty` (= 아직 안 그림).
    """
    _v = np.asarray(list(values), float)
    if _v.size == 0:
        return empty()
    return normalize(_v.reshape(2, -1))


def to_flat(box: np.ndarray | None) -> list[float]:
    """상자 → 평탄 좌표열 (저장·시그널로 나가는 유일한 형태). 빈 상자는 ``[]``."""
    return [float(_v) for _v in box.reshape(-1)] if is_set(box) else []


def normalize(box: np.ndarray) -> np.ndarray:
    """뒤집힌 상자를 바로잡는다 (``lo <= hi``) — 면을 반대쪽 너머로 끌어도 안 뒤집힌다."""
    return np.stack([np.minimum(box[0], box[1]), np.maximum(box[0], box[1])])


# ── 핸들 ──────────────────────────────────────────────────────────────────────
def corners(box: np.ndarray) -> np.ndarray:
    """모든 코너 ``(2**D, D)`` — **전 축 리사이즈** 핸들 (2d 면 4개, 3d 면 8개).

    인덱스의 비트가 축마다 lo(0)/hi(1) 라 **반대 코너는 비트 반전**이다(`opposite`) — 2d 시절의
    ``(i + 2) % 4`` 를 대신한다(같은 값을 내면서 D 를 안 박는다).
    """
    return np.array(list(itertools.product(*zip(box[0], box[1]))), float)


def opposite(box: np.ndarray, index: int) -> int:
    """코너의 맞은편 코너 인덱스 — 드래그 중 고정될 점."""
    return (1 << dims(box)) - 1 - index


def faces(box: np.ndarray) -> list[tuple[np.ndarray, int, int]]:
    """면 중심들 ``(중심, 축, 쪽)`` — **한 축만** 움직이는 핸들 (2d 면 변 중점, 3d 면 면 중심).

    ``쪽`` 은 0=lo · 1=hi. 2d 에서 ``(축0, 쪽0)`` 이 좌변, ``(축1, 쪽0)`` 이 상변이다.
    """
    _center = box.mean(axis=0)
    _out = []
    for _axis in range(dims(box)):
        for _side in (0, 1):
            _p = _center.copy()
            _p[_axis] = box[_side, _axis]
            _out.append((_p, _axis, _side))
    return _out


def resize_face(box: np.ndarray, axis: int, side: int, point) -> np.ndarray:
    """면 드래그 — 잡은 면의 좌표만 커서로 옮긴 새 상자 (나머지는 고정)."""
    _out = box.copy()
    _out[side, axis] = float(np.asarray(point, float)[axis])
    return normalize(_out)


def hit_corner(box: np.ndarray | None, point, tolerance: float) -> int | None:
    """허용 반경 안에서 가장 가까운 코너의 인덱스 (없으면 None)."""
    if not is_set(box):
        return None
    _d = np.linalg.norm(corners(box) - np.asarray(point, float), axis=1)
    _i = int(_d.argmin())
    return _i if _d[_i] <= tolerance else None


def hit_face(box: np.ndarray | None, point, tolerance: float) -> tuple[int, int] | None:
    """허용 반경 안에서 가장 가까운 면 중심의 ``(축, 쪽)`` (없으면 None)."""
    if not is_set(box):
        return None
    _p = np.asarray(point, float)
    _best, _dist = None, float(tolerance)
    for _center, _axis, _side in faces(box):
        _d = float(np.linalg.norm(_center - _p))
        if _d <= _dist:
            _best, _dist = (_axis, _side), _d
    return _best


# ── 판정 ──────────────────────────────────────────────────────────────────────
def inside(box: np.ndarray | None, point) -> bool:
    """점이 상자 안에 있나 (캔버스 클릭으로 객체를 고를 때)."""
    if not is_set(box):
        return False
    _p = np.asarray(point, float)
    return bool(np.all(box[0] <= _p) and np.all(_p <= box[1]))


def measure(box: np.ndarray | None) -> float:
    """상자의 크기 — 2d 면 넓이, 3d 면 부피. **겹친 것 중 작은 것을 먼저** 고르는 기준."""
    if not is_set(box):
        return 0.0
    return float(np.prod(np.maximum(0.0, box[1] - box[0])))


def grow(box: np.ndarray, ratio: float, minimum: float, limit) -> np.ndarray:
    """상자를 각 축 길이의 ``ratio`` 만큼 키우되 ``[0, limit]`` 안에 가둔다 (여유 맥락을 줄 때).

    Args:
        box: 키울 상자.
        ratio: 축 길이 대비 확장 비율 (0.06 = 6%).
        minimum: 축마다 최소 이만큼은 키운다 (얇은 상자가 안 커지는 것을 막는다).
        limit: 벗어날 수 없는 상한 ``(D,)`` — 하한은 0 이다 (라스터·볼륨의 크기).
    """
    _margin = np.maximum(minimum, (box[1] - box[0]) * ratio)
    return np.stack([np.maximum(0.0, box[0] - _margin),
                     np.minimum(np.asarray(limit, float), box[1] + _margin)])


class Draft:
    """그리는 중인 상자 하나 — **무엇이 고정됐고 커서가 어디냐**로 상자가 정해진다.

    상자를 만드는 손짓은 셋인데 전부 이 한 모양이다 — 그래서 도구가 다섯 개의 상태 변수를 들 이유가
    없다(한때 그랬고, 그래서 상자 도구가 폴리곤 도구보다 세 배 두꺼웠다):

    | 손짓 | 고정되는 것 | 커서가 정하는 것 |
    |---|---|---|
    | 새로 그리기 | 누른 점 | 맞은편 코너 |
    | 코너 드래그 | 맞은편 코너 | 잡은 코너 |
    | 면 드래그 | 나머지 면들 | 잡은 면 (한 축만) |

    앞의 둘은 `from_points`, 마지막은 `resize_face` 로 갈리지만 그 분기는 안에서 끝난다 — 도구는
    "잡았나(`grab`) · 어디까지 끌었나(`drag`) · 움직이긴 했나(`moved`)"만 묻는다.

    [`polygon.Draft`](polygon.py) 와 짝이다 — 확정 전 상태는 데이터가 아니므로 저장되지 않고, 확정되면
    상자 하나를 내고 사라진다.
    """

    def __init__(self) -> None:
        self._anchor: np.ndarray | None = None       # 고정된 점 (새로 그리기 · 코너 드래그)
        self._face: tuple[int, int] | None = None    # 면 드래그 중인 (축, 쪽)
        self._origin: np.ndarray | None = None       # 면 드래그의 시작 상자 = 고정 좌표원
        self._moved = False

    def __bool__(self) -> bool:
        """무언가를 잡고 있나 (= 그리거나 고치는 중인가)."""
        return self._anchor is not None or self._face is not None

    def start(self, point) -> None:
        """새로 그리기 — 누른 점을 고정한다 (커서가 맞은편 코너가 된다)."""
        self._anchor = np.asarray(point, float)
        self._face = self._origin = None
        self._moved = False

    def grab(self, box: np.ndarray | None, point, tolerance: float) -> bool:
        """기존 상자의 핸들을 잡는다 — 코너면 맞은편이, 면이면 나머지가 고정된다.

        Args:
            box: 고칠 상자 (없거나 안 그려졌으면 못 잡는다).
            point: 누른 점.
            tolerance: 핸들에 붙었다고 볼 반경 (화면 기준을 줌 보정한 값).
        """
        if box is None or box.size == 0:
            return False
        _i = hit_corner(box, point, tolerance)
        if _i is not None:
            self.start(corners(box)[opposite(box, _i)])       # 맞은편 코너를 고정 = 새로 그리기와 같다
            return True
        _face = hit_face(box, point, tolerance)
        if _face is not None:
            self._anchor = None
            self._face = _face
            self._origin = box.copy()
            self._moved = False
            return True
        return False

    def at(self, point) -> np.ndarray | None:
        """커서가 여기일 때의 상자 (아무것도 안 잡았으면 ``None``) — 미리보기용이라 상태를 안 바꾼다."""
        if self._anchor is not None:
            return from_points(self._anchor, point)
        if self._face is not None and self._origin is not None:
            return resize_face(self._origin, *self._face, point)
        return None

    def drag(self, point) -> np.ndarray | None:
        """커서까지 끈다 — `at` 과 같은 상자를 내되 **움직였다**고 표시한다."""
        _box = self.at(point)
        if _box is not None:
            self._moved = True
        return _box

    def moved(self) -> bool:
        """잡은 뒤 실제로 끌었나 — 핸들을 눌렀다 놓기만 했으면 이력에 빈 칸을 안 쌓는다."""
        return self._moved

    def clear(self) -> None:
        self._anchor = self._face = self._origin = None
        self._moved = False
