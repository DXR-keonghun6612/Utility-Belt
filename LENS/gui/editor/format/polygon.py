"""polygon — 꼭짓점 목록과 그리는 손짓. **차원도, 쓰일 곳도 모른다.**

같은 폴리곤이 두 곳에서 산다 — 그리고 그 둘은 **다른 일**이다:

- [`image/tool/_polygon.py`](../image/tool/_polygon.py) 는 폴리곤을 **데이터로** 든다 (좌표가 곧 산출물).
- [`image/tool/_pixel.py`](../image/tool/_pixel.py) 의 올가미는 폴리곤을 **픽셀 영역으로** 소비하고 버린다.

손짓(꼭짓점 찍기 · 첫 점 근처로 닫기 · 우클릭 취소)은 둘이 똑같아야 하므로 여기 한 곳에 둔다. 데이터
**생성**과 그 **활용**을 가르는 경계가 이 파일이다 — 여기는 좌표만 알고, 그 좌표를 저장할지 픽셀로
찍을지는 소비하는 도구가 정한다.

**그래서 여기엔 래스터화가 없다.** 폴리곤 → 픽셀은 [`image/_region.py`](../image/_region.py) 가 든다 —
좌표가 자기를 픽셀로 바꾸는 법을 알면 그 순간 이 파일은 올가미 편이 되고, 저장되는 쪽(폴리곤 데이터)과
찍히는 쪽(region) 양쪽에 같이 설 수 없다. 이 모듈에 cv2 가 없는 것이 그 경계의 증거다.

정준형은 [`bbox`](bbox.py) 와 같은 결 — 꼭짓점 ``(N, D)`` float 배열이라 x·y 를 이름으로 안 쓴다.
저장 표현(COCO ``segmentation`` 의 평탄 ``[x0, y0, x1, y1, …]``)과는 `from_flat`/`to_flat` 로만 오간다.
"""
from __future__ import annotations

import numpy as np

from . import bbox


def empty(dims: int = 2) -> np.ndarray:
    """꼭짓점이 없는 폴리곤 ``(0, D)``."""
    return np.zeros((0, dims), float)


def from_flat(values, dims: int = 2) -> np.ndarray:
    """평탄 좌표열 ``[x0, y0, x1, y1, …]`` → 꼭짓점 ``(N, D)`` (COCO ``segmentation``)."""
    _v = np.asarray(list(values), float)
    return _v.reshape(-1, dims) if _v.size else empty(dims)


def to_flat(points: np.ndarray) -> list[float]:
    """꼭짓점 → 평탄 좌표열 (저장으로 나가는 유일한 형태)."""
    return [float(_v) for _v in np.asarray(points, float).reshape(-1)]


def bounds(points: np.ndarray) -> np.ndarray:
    """꼭짓점들을 감싸는 상자 — 폴리곤과 상자가 **같은 정준형**으로 만나는 지점.

    폴리곤을 그려 상자를 얻는 일(SAM3 프롬프트)이 여기서 나온다 — 두 데이터가 서로를 알 필요 없이
    [`bbox`](bbox.py) 정준형 하나로 통한다.
    """
    _p = np.asarray(points, float)
    if _p.size == 0:
        return bbox.empty()
    return np.stack([_p.min(axis=0), _p.max(axis=0)])


class Draft:
    """그리는 중인 폴리곤 하나 — 꼭짓점 목록 + 닫기 판정 (좌표만 안다).

    확정 전의 상태라 도구가 든다. 확정되면 좌표는 `to_flat` 으로 데이터가 되거나
    (`image/tool/_polygon.py`) region 으로 찍히고 버려진다 (`image/tool/_pixel.py`).
    """

    def __init__(self, dims: int = 2) -> None:
        """Args:
            dims: 좌표 차원 — 2d 캔버스면 2.
        """
        self._dims = dims
        self._points: list[np.ndarray] = []

    def __bool__(self) -> bool:
        """꼭짓점이 하나라도 있나 (= 그리는 중인가)."""
        return bool(self._points)

    def __len__(self) -> int:
        return len(self._points)

    def points(self) -> np.ndarray:
        """찍힌 꼭짓점들 ``(N, D)``."""
        return np.array(self._points, float) if self._points else empty(self._dims)

    def add(self, point) -> None:
        """꼭짓점 하나를 찍는다."""
        self._points.append(np.asarray(point, float))

    def undo(self) -> None:
        """마지막 꼭짓점만 취소 (우클릭) — 그리던 것 전체를 버리지 않는다."""
        if self._points:
            self._points.pop()

    def clear(self) -> None:
        self._points = []

    def closes_at(self, point, tolerance: float) -> bool:
        """이 점을 찍으면 폴리곤이 닫히나 — 3점 이상 + 첫 점의 허용 반경 안.

        Args:
            point: 찍으려는 점.
            tolerance: 첫 점에 붙었다고 볼 반경 (화면 기준을 줌 보정한 값).
        """
        if len(self._points) < 3:
            return False
        return bool(np.linalg.norm(self._points[0] - np.asarray(point, float)) <= tolerance)

    def trace(self, cursor=None) -> np.ndarray:
        """미리보기용 꼭짓점 — 커서가 있으면 다음 변을 거기까지 늘려 보인다."""
        if cursor is None:
            return self.points()
        return np.array(self._points + [np.asarray(cursor, float)], float)
