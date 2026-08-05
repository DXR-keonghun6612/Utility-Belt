"""pose 도메인 — **강체 자세**(자리 + 방향). 좌표도 픽셀도 아니라 *변환*이다.

[`region`](region.py) 과 무엇이 다른가 — region 은 **영역의 경계**를 좌표로 긋고, pose 는 그 물체를
어디에 어떻게 **놓았나**를 든다. bbox 를 아무리 변환해도 회전이 안 나오고(축 정렬 상자에는 각이 없다),
자세를 아무리 봐도 그 물체가 덮는 픽셀이 안 나온다. 둘 사이에 닫힌 변환이 없다는 것이 곧 다른 도메인
이라는 증거다(그 판정 기준은 region 모듈이 소유한다).

**포맷은 자세의 표현이 갈리는 축이다** — 지금은 ``quat`` 하나(회전을 단위 quaternion 으로 든 dict)이고,
4×4 행렬이나 축각이 실제로 들어오면 그때 `FORMATS` 에 한 줄 더한다. 구조와 그 위의 연산(2D 로 자르기·
되돌리기)은 [`../../format/pose`](../../format/pose.py) 가 든다 — 여기는 **무엇으로 읽나**만 안다.

파일 I/O 가 없다(인라인 dict). 그래서 `INFERABLE` 은 False 이고 `Claims` 는 안 나선다 — bbox 와 같은
이유로, 값 모양만 보고 "이건 자세다"라고 집을 수 없기 때문이다(생산자가 명시한다).
"""

from __future__ import annotations

from typing import Any, ClassVar

from . import DOMAIN_REGISTRY
from ._base import Domain


@DOMAIN_REGISTRY.Register_module("pose")
class Pose_Domain(Domain):
    """강체 자세 — ``quat``(자리 + quaternion dict) / (미래: 행렬·축각)."""

    FORMATS:   ClassVar[tuple[str, ...]] = ("quat",)
    INFERABLE: ClassVar[bool]            = False   # 파일 확장자가 없다 (인라인)

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """스스로는 안 나선다 — 자세는 개념이 명시된 자리(저장 정돈)에서만 만들어진다.

        ``{"position": …, "rotation": …}`` 모양을 값에서 알아보게 하면 남의 dict 을 집을 수 있다.
        """
        return 0
