"""detect — 프레임을 ONNX 전경-분할 모델로 통째 분할해 인스턴스를 만든다.

**SAM3([`../segment`](../segment/__init__.py))와 다르다.** SAM3 는 객체 bbox 를 프롬프트로 하나씩
분할하지만, 이 정책은 프롬프트 없이 프레임 한 장을 backend([`Onnx_segmenter`](../onnx/segment.py))에
통째로 넣어 **전경 mask logits 한 장**을 받는다. 인스턴스 분리는 그 logits 를 sigmoid·threshold 로
이진화한 뒤 connected-components([`Split_components`](../../../../func/mask/instance.py))로 한다 —
[`Split_objects`](../../mask/separate.py) 와 같은 후처리이되, 입력이 파일 mask 가 아니라 모델 출력이다.

**모델 출력은 원본보다 작다** — 588×798 이 600×800 의 안쪽이다. 모델이 **중앙 crop** 을 그래프에 내장한
결과다(patch 14 백본에 맞추려고 resize 대신 crop 을 골랐다 — 배경은 [`../README.md`](../README.md)).
그래서 되돌리는 것도 중앙이고, 그 offset 은 **프레임과 출력의 크기 차이의 절반**이라 상수가 아니다
(onnx 가 바뀌어 crop 폭이 달라져도 따라온다). 원본 크기 canvas 에 그렇게 앉힌 뒤 분리하면 bbox·라벨맵이
자연히 원본 좌표로 나온다. class 는 안 정한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

import numpy as np

from .....constant import UNCLASSIFIED_ID
from .....schema import Build, Data_Ref
from .....format import rle
from .....func.cv.geom import Roi_to_mask
from .....func.mask.instance import Mask_of, Split_components
from ... import PROCESS_REGISTRY, Base_Process, UI, BBOX, GRAY_IMAGE

#: detection 은 전경만 내고 class 를 모른다 — 미분류 번호(0)로 낸다.


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))       # clip: 큰 음수 logit 의 exp 오버플로 방지


@PROCESS_REGISTRY.Register_module()
@dataclass
class Detect_instances(Base_Process, outputs=("object",), category="모델/분할"):
    """ONNX 전경-분할 → **객체별 mask(rle) + bbox** 리스트 (plain frame→instances).

    ``unit: frame`` — 프레임 픽셀만 있으면 된다(객체 seed 불필요). backend 는 config 의
    ``{type: onnx_seg, …}`` 를 pipeline 이 빌드해 주입한다. 각 객체가 자기 mask 를 rle 로 들므로(정본
    모델), 라벨맵 ``segment`` 는 내부 계산에만 쓰고 저장하지 않는다. 객체가 없으면 빈 dict("스킵").

    **``roi`` 는 연결요소를 세기 전에 픽셀로 끊는다** — 인스턴스가 된 뒤 거르는
    [`Filter_by_roi`](../../mask/roi.py) 와 순서가 다르고, 그 순서가 결과를 가른다. 이 모델의 전경은
    "벨트가 아닌 것"이라 프레임 테두리(벨트 밖 구조물)도 전경인데, 관심 영역 가장자리에 걸친 객체는 그
    테두리 전경과 **픽셀이 이어져** 한 컴포넌트가 된다. 그대로 두면 그 거대 컴포넌트가 roi 겹침비 미달로
    떨어지면서 **부품까지 함께** 버려진다(실측: 정본 대비 항상 하나씩 적게 나왔다 — 150 stem 중 일치
    57%). 픽셀 단계에서 끊으면 부품이 독립 컴포넌트로 서고 일치율이 98% 가 된다. ``roi`` 는 producer
    없이 엔진이 params 에서 ctx 로 얹고, 없으면 프레임 전체를 쓴다.

    roi 경계에 걸친 객체의 mask 는 그 선에서 **잘린 채** 저장된다 — 관심 영역 밖은 애초에 판단 대상이
    아니라는 전제다.
    """

    model:     Any = None
    threshold: Annotated[float, UI(label="전경 임계 (sigmoid)",
                                   tip="logits 를 sigmoid 한 뒤 이 값 초과를 전경으로", min=0.0, max=1.0, step=0.05)] = 0.5
    min_area:  Annotated[int,   UI(label="최소 객체 면적 (px²)", min=0, max=100000)]                = 200
    merge_gap: Annotated[int,   UI(label="bbox 중심 병합 거리 (px, 0=끄기)",
                                   tip="bbox 중심점 거리가 이 값 이하면 한 객체로 묶음", min=0, max=999)] = 0
    bbox_gap:  Annotated[float, UI(label="bbox 확대/축소 비율 (-1~1)",
                                   tip="원본 대비 (0.1=10% 확대, -0.1=축소)", min=-1.0, max=1.0, step=0.05)] = 0.0

    def Run(self, frame: np.ndarray, class_id: int | None = None,
            roi: BBOX | GRAY_IMAGE | None = None, **kwargs) -> dict:
        _fg = _sigmoid(self.model.Infer_logits(frame)) > self.threshold   # (H', W') 전경 bool
        _canvas = np.zeros(frame.shape[:2], np.uint8)              # 원본 크기 (600×800)
        _h, _w = _fg.shape
        _top  = (frame.shape[0] - _h) // 2                         # 모델이 중앙 crop 했으므로 중앙으로
        _left = (frame.shape[1] - _w) // 2
        _canvas[_top:_top + _h, _left:_left + _w] = _fg            # offset 으로 원본 좌표에 앉힌다
        _sel = Roi_to_mask(roi, _canvas.shape[:2])                 # roi 밖 전경을 **분리 전에** 끊는다
        if _sel is not None:
            _canvas &= _sel.astype(np.uint8)
        _seg, _boxes = Split_components(
            _canvas, min_area=self.min_area, merge_gap=self.merge_gap, bbox_gap=self.bbox_gap)
        if not _boxes:
            return {}

        _cls = class_id or UNCLASSIFIED_ID
        _objs = [Data_Ref(info=Build({
            "class_id": {"format": ("", "int"),                "info": {"value": _cls}},
            "bbox":     {"format": ("region", "bbox", "xyxy"), "info": {"value": [float(_v) for _v in _b]}},
            "mask":     {"format": ("mask", "rle"),
                         "info": {"value": rle.From_mask(Mask_of(_seg, _i))}},   # 객체별 mask (정본)
        })) for _i, _b in enumerate(_boxes)]
        return {"object": _objs}
