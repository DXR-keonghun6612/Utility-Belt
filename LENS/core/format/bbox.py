"""bbox 구조 — 축에 정렬된 상자, **평탄 좌표 4개.** 표준이 하나가 아니라 style 로 갈린다.

같은 상자를 세 style 로 쓴다 — 어느 것도 표준이 아니라, `Data_Ref.format` 의 **셋째 칸이 style 이다**
(``("mask", "bbox", "xyxy")``). polygon·rle 엔 없는 축이라, style 은 이 format 에 종속이다.

| style | 좌표 | 뜻 |
|---|---|---|
| ``xyxy`` | ``[x0, y0, x1, y1]`` | 두 코너 (COCO ``segmentation`` extent · 정본 저장 규약) |
| ``xywh`` | ``[x, y, w, h]`` | 좌상단 + 크기 (COCO ``bbox`` 필드) |
| ``cxcywh`` | ``[cx, cy, w, h]`` | 중심 + 크기 (YOLO) |

**style 간 변환은 무손실이다** — 같은 차원수면 같은 정보량이라 **좌표를 재배치할 뿐**이다(폴리곤을
채우는 [`polygon.Fill`](polygon.py) 이 rasterize 라 손실인 것과 다르다). 그래서 저장은 style 하나로 하고
소비처가 필요한 style 로 `Convert` 한다 — export 가 COCO 로 낼 때 ``xyxy → xywh`` 하는 그 변환이다.

**여기는 배열로 안 간다** — bbox 는 좌표만이라 채울 캔버스 크기(``size``)를 모른다(polygon 은 자기 dict
에 든다). bbox → mask 는 그 size 를 아는 자리(gui·SAM 프롬프트 유도)의 몫이고, 애초에 필요하지도 않다
— SAM3 는 bbox 를 **좌표 프롬프트**로, export 는 **좌표**로 받는다(배열이 아니다).
"""

from __future__ import annotations

#: 저장 규약 — 서술자에 style 이 없는 옛 데이터는 이걸로 읽는다 (정본은 코너로 들어 왔다).
DEFAULT_STYLE = "xyxy"

STYLES = ("xyxy", "xywh", "cxcywh")


def To_xyxy(value, style: str) -> list[float]:
    """어떤 style 이든 코너 ``[x0, y0, x1, y1]`` 로 — 변환의 **경유지**."""
    _a, _b, _c, _d = (float(_v) for _v in value)
    if style == "xyxy":
        return [_a, _b, _c, _d]
    if style == "xywh":
        return [_a, _b, _a + _c, _b + _d]
    if style == "cxcywh":
        return [_a - _c / 2, _b - _d / 2, _a + _c / 2, _b + _d / 2]
    raise ValueError(f"알 수 없는 bbox style '{style}' (가능: {', '.join(STYLES)})")


def From_xyxy(xyxy, style: str) -> list[float]:
    """코너 ``[x0, y0, x1, y1]`` → ``style`` (`To_xyxy` 의 역)."""
    _x0, _y0, _x1, _y1 = (float(_v) for _v in xyxy)
    if style == "xyxy":
        return [_x0, _y0, _x1, _y1]
    if style == "xywh":
        return [_x0, _y0, _x1 - _x0, _y1 - _y0]
    if style == "cxcywh":
        return [(_x0 + _x1) / 2, (_y0 + _y1) / 2, _x1 - _x0, _y1 - _y0]
    raise ValueError(f"알 수 없는 bbox style '{style}' (가능: {', '.join(STYLES)})")


def Convert(value, src: str, dst: str) -> list[float]:
    """상자를 ``src`` style → ``dst`` style 로 (코너를 경유한다). 무손실."""
    return From_xyxy(To_xyxy(value, src), dst)


def Style_of(ref_format) -> str:
    """서술자 format 에서 style 을 읽는다 — 셋째 칸, 없으면 `DEFAULT_STYLE`.

    Args:
        ref_format: ``Data_Ref.format`` 튜플 (``("mask", "bbox", "xyxy")`` 또는 style 없는 옛 것).
    """
    return ref_format[2] if len(ref_format) > 2 else DEFAULT_STYLE
