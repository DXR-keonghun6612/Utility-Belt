"""이진 영역 합성 primitive — 두 mask 의 집합 연산 + 면적 변화 측정.

값을 보존하는 집합 연산이다(0/255 든 0/1 이든 전경 값이 그대로 남는다). 합성 결과를 **받아들일지**
판단하는 정책(스킵할지, 원본을 통과시킬지)은 여기 없다 — 호출 측이 정한다.
"""

from __future__ import annotations

import numpy as np

from ....typing import GRAY_IMAGE

MODES = ("subtract", "intersect", "union")


def Combine_regions(mask: GRAY_IMAGE, other: GRAY_IMAGE, mode: str) -> GRAY_IMAGE:
    """두 이진 영역을 ``mode`` 로 합친다.

    Args:
        mask: 기준 영역 ``(H,W)``.
        other: 상대 영역 ``(H,W)``.
        mode: ``subtract``(``mask & ~other``) / ``intersect``(``mask & other``) /
            ``union``(``mask | other``, 켜진 값은 두 값의 max).

    Returns:
        합성된 mask (전부 0 일 수 있다).

    Raises:
        ValueError: ``mode`` 가 :data:`MODES` 밖일 때.
    """
    if mode == "subtract":
        return np.where(other > 0, np.uint8(0), mask)
    if mode == "intersect":
        return np.where(other > 0, mask, np.uint8(0))
    if mode == "union":
        return np.maximum(mask, other)
    raise ValueError(f"알 수 없는 mode {mode!r} ({' / '.join(MODES)})")


def Area_change(before: GRAY_IMAGE, after: GRAY_IMAGE) -> float | None:
    """전경 면적의 변화율 ``(after - before) / before``. ``before`` 가 비면 None.

    부호가 연산 종류와 자연히 짝지어진다 — 축소(subtract/intersect)는 음수, 확대(union)는 양수.
    그래서 한계값 하나로 "너무 많이 지워짐"과 "너무 많이 커짐"을 각각 막을 수 있다.
    """
    _old = int(np.count_nonzero(before))
    if not _old:
        return None
    return (int(np.count_nonzero(after)) - _old) / _old
