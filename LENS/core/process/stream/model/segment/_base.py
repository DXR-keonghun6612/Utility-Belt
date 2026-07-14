"""segment — 프레임 객체 bbox 들을 backend 로 분할하는 모델-무관 프로세스.

**Segment** 는 backend(``model``: ``encode``/``run`` 프리미티브)를 config 로 주입받아 이미지 인코딩
1회 + box 별 디코드로 인스턴스 ``segment`` 라벨맵을 만든다. SAM3 등 특정 모델을 몰라도 되는 층 —
같은 계약(``infer_ctx``/``encode``/``run``)을 만족하는 promptable segmenter 면 backend 만 갈아끼운다.
plain box→best mask 만 하고, 영역 제거(구멍/슬릿 carve 등)는 downstream process 로 조합한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

import numpy as np

from core.schema import Build, Data_Ref
from ....func.cv.geom import Mask_to_box
from ....func.mask.instance import Paint
from ... import PROCESS_REGISTRY, Base_Process, GRAY_IMAGE, UI


def _to_binary(mask: Any) -> GRAY_IMAGE:
    """backend 출력(torch/np, 확률 또는 bool) → 0/255 GRAY_IMAGE (HxW)."""
    _a = np.squeeze(np.asarray(mask.detach().float().cpu()) if hasattr(mask, "detach")
                    else np.asarray(mask, dtype=np.float32))
    if _a.ndim == 3:
        _a = _a[0]
    return (_a > 0.5).astype(np.uint8) * np.uint8(255)


def _bbox_of(obj: Data_Ref) -> list | None:
    """object 의 ``info["bbox"]`` 인라인 값(``[x0,y0,x1,y1]``)을 꺼낸다 (없으면 None)."""
    _ref = obj.info.get("bbox")
    if _ref is None:
        return None
    _val = _ref.info.get("value")
    return list(_val) if isinstance(_val, (list, tuple)) and len(_val) == 4 else None


@PROCESS_REGISTRY.Register_module()
@dataclass
class Segment(Base_Process, outputs=("segment", "object"), category="모델/분할"):
    """프레임 객체 bbox 들을 backend 로 분할하는 정책 프로세스 (plain box→best mask).

    ``unit: frame`` — ctx 의 ``object``(프레임의 객체 목록)에서 객체별 box 를 프롬프트로 준다. backend
    이미지 인코딩은 프레임당 1회(``encode``), box 마다 가벼운 ``run`` 디코드. best mask 로 (1) 인스턴스
    라벨맵 ``segment``(픽셀=obj_id+1) 재칠 (2) bbox 재계산. ``class_id`` 는 SAM3 가 정하지 않고 기존 객체
    값을 그대로 유지한다. 결과 없으면 빈 dict("스킵").

    ``object`` 는 입력이자 출력이다 — engine 이 store 에서 seed 하고, 앞 step(``split_objects``)이 있으면
    그 출력이 ctx 에서 이긴다. 유닛은 store 를 모른다.

    영역 제거(구멍/슬릿 carve)는 여기 넣지 않고 downstream process(edge·fill·combine)로 조합한다.
    """

    # model: pipeline 이 config 의 ``{type: sam3, …}`` 스펙을 빌드해 주입한 backend.
    model:    Any                                                                       = None
    text:     Annotated[str, UI(label="text 힌트", tip="무엇을 분할할지 backend 에 주는 concept 힌트(분류 아님)")] = ""
    conf:     Annotated[float, UI(label="점수 하한", tip="0 = best mask 그대로 채택", min=0.0, max=1.0, step=0.05)] = 0.0
    min_area: Annotated[int,   UI(label="최소 면적 (px²)", min=0, max=10000)]            = 200

    def Run(self, frame: np.ndarray, object: list[Data_Ref], **kwargs) -> dict:
        _objs = object
        if not _objs:
            return {}

        # 객체마다 box 프롬프트 + 프레임 공유 text concept → 프레임 인코딩 1회 위에서 box 별 디코드.
        _masks = self._predict(frame, [_bbox_of(_o) for _o in _objs])

        _seg      = np.zeros(frame.shape[:2], dtype=np.uint8)   # 인스턴스 라벨맵 (0 = 배경)
        _new: list[Data_Ref] = []                              # obj_id = 리스트 순번(_route info key)
        for _o, _m in zip(_objs, _masks):
            if _m is None or int((_m > 0).sum()) < self.min_area:
                continue
            _oid = len(_new)                                   # 정제 후 재부여한 0-based obj_id
            Paint(_seg, _oid, _m)                              # 라벨맵에 그 객체 라벨로 도색 (규약은 func)
            _box = Mask_to_box(_m)                             # 정제 mask 기준 bbox 재계산
            if _box is None:
                continue
            _data: dict = {"bbox": {"format": ("bbox", "list"),
                                    "info": {"value": [float(_v) for _v in _box]}}}
            _cid = _o.Get("class_id")                          # 기존 class 유지 (SAM3 는 class 안 정함)
            if _cid is not None:
                _data["class_id"] = _cid
            _new.append(Data_Ref(info=Build(_data)))

        if not _new:
            return {}
        return {"segment": _seg, "object": _new}

    def _predict(self, frame_bgr: np.ndarray, boxes: list) -> list[GRAY_IMAGE | None]:
        """프레임 1장 + box 리스트 → box 별 best mask. 이미지 인코딩 1회 + box 별 ``_segment_box``.

        ``boxes`` 와 **같은 길이·순서** 의 리스트를 낸다 (box 없는 슬롯·결과 없음은 None).
        """
        _out: list[GRAY_IMAGE | None] = []
        with self.model.infer_ctx():
            _state = self.model.encode(frame_bgr, text=self.text or None, conf=self.conf)
            for _box in boxes:
                if _box is None:                               # box 없는 슬롯
                    _out.append(None)
                    continue
                _out.append(self._segment_box(
                    _state, frame_bgr, np.asarray(_box, dtype=np.float32)))
        return _out

    def _segment_box(self, state: Any, frame_bgr: np.ndarray,
                     box: np.ndarray) -> GRAY_IMAGE | None:
        """단일 box → best mask (0/255). 결과 없거나 score<conf 면 None."""
        _r = self.model.run(state, box=box, multimask_output=False)
        if _r is None:
            return None
        _masks, _sc, _ = _r
        _b = int(np.argmax(_sc))
        if float(_sc[_b]) < self.conf:                         # box 는 우리가 지목한 영역이라 보통 conf=0
            return None
        return _to_binary(_masks[_b])
