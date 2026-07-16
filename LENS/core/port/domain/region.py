"""region 도메인 — **좌표로 경계 지은 영역.** 픽셀이 아니라 꼭짓점·코너로 든다.

[`mask`](mask.py) 와 무엇이 다른가 — **자족적으로 변환되느냐**로 갈린다. region 안의 format(bbox·
polygon)끼리는 좌표만으로 오간다(bbox → 4점, polygon → extent). 그런데 region → mask 는 채울
**캔버스 크기(size)**가 있어야 하고, mask → region 은 외곽선 근사라 **손실**이다. 그 변환이 안 닫히는
것이 곧 둘이 **다른 도메인**이라는 증거다 — 같은 것의 다른 표현이면 format 만으로 왕복이 닫힌다.

그래서 bbox 를 mask 도메인에 넣으려던 걸 접었다: bbox 를 배열로 채우려면 size 가 필요했는데, 그 size
부재는 "아직 안 만든 기능"이 아니라 **경계 신호**였다. region↔mask 변환(rasterize/vectorize)은 도메인을
넘는 별도 연산이라, 그 size 와 손실을 아는 자리(gui·SAM 프롬프트 유도)가 든다.

**지금은 bbox 하나뿐이다.** polygon 도 좌표 경계라 여기 속하지만(편집기가 꼭짓점을 truth 로 들 때),
실측상 polygon 데이터가 0 이라 그때 `FORMATS` 에 한 줄 더한다 — 없는 것을 미리 짓지 않는다.

**style 은 format 종속이라 `format` 셋째 칸이다** — ``("region", "bbox", "xyxy")``. 변환은
[`../../format/bbox`](../../format/bbox.py) 가 든다(xyxy↔xywh↔cxcywh, 무손실 재배치).
"""

from __future__ import annotations

from typing import Any, ClassVar

from . import DOMAIN_REGISTRY
from ._base import Domain


@DOMAIN_REGISTRY.Register_module("region")
class Region_Domain(Domain):
    """좌표로 경계 지은 영역 — bbox(코너·크기 style) / (미래: polygon)."""

    FORMATS:   ClassVar[tuple[str, ...]] = ("bbox",)
    INFERABLE: ClassVar[bool]            = False   # 파일 확장자가 없다 (인라인)

    @classmethod
    def Claims(cls, value: Any, *, storage: bool, params: bool) -> int:
        """스스로는 안 나선다 — bbox 는 개념이 명시된 자리(편집·detection)에서만 만들어진다.

        길이 4 짜리 list 를 전부 bbox 로 볼 수는 없다(그냥 4-list 일 수 있다) — 그래서 `Claims` 로
        값에서 추정하지 않고, 생산자가 ``type: region`` 을 명시한다.
        """
        return 0
