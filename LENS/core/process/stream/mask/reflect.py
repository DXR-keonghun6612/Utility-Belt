from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from ....func.cv.filter import Band_threshold, Lowpass_bright_mask
from ....func.cv.geom import Mask_within_roi
from ....func.mask.combine import Combine_regions
from .. import PROCESS_REGISTRY, Base_Process, UI, BBOX, IMAGE, GRAY_IMAGE


@PROCESS_REGISTRY.Register_module()
@dataclass
class Reflection_gate(Base_Process, outputs=("mask",), category="마스크/이진화"):
    """물체 표면 반사 띠만 남긴다 — 밝은 밴드에서 직접 광원(저주파 밝은 영역)을 빼서.

    무채색 씬에서 직접 광원(맞은편의 촬영된 조명)과 물체에 반사된 광은 둘 다 밝고 포화(255)해
    밝기·연결성만으로는 못 가른다. 다른 것은 **공간 주파수**다 — 직접 광원은 크고 균일한 저주파
    영역이고, 반사는 곡면 위 국소 하이라이트다. 그래서 강한 저주파 통과 후 밝게 남는 영역
    (``Lowpass_bright_mask``)을 그 프레임의 광원 **가변 ROI** 로 잡아, 밝은 밴드(``Band_threshold``)
    에서 빼면(``Combine_regions`` subtract) 반사만 남는다. 물체가 광원 앞을 지나 광원이 프레임마다
    달리 가려져도 저주파 ROI 가 매 프레임 적응하므로 고정 ROI 로는 못 하는 배제를 한다.

    잡티 제거·성분 분리는 이 유닛의 일이 아니다 — 뒤에 ``morph_mask``(OPEN)·``split_objects`` 를
    잇는다. ``roi`` 는 다른 도메인(top-view crop 등)의 포함 한정이고 광원 배제와 별개다. 결과가 비면
    빈 dict("스킵"). 근거는 ``func.cv.filter.Lowpass_bright_mask``.

    **공간 파라미터는 이미지 크기 상대값**이다(``*_frac`` = ``min(H,W)`` 대비 비율) — 원본 해상도에서
    바로 돌아도(축소 없이) 저주파 커널이 프레임 크기에 맞춰지므로 4000px 든 1000px 든 같은 효과를 낸다.
    밝기·정규화 임계는 강도값이라 해상도 무관이라 절대값 그대로 둔다.
    """

    sigma_frac:  Annotated[float, UI(label="저주파 sigma (min(H,W) 비율, 클수록 국소광 더 씻김)", min=0.005, max=0.3, step=0.005)] = 0.06
    source_thr:  Annotated[int,   UI(label="광원 임계 (정규화 저주파 하한)", min=0, max=255)]                    = 130
    close_frac:  Annotated[float, UI(label="광원 ROI CLOSE (min(H,W) 비율)", min=0.0, max=0.1, step=0.002)]     = 0.02
    bright_low:  Annotated[int,   UI(label="반사 하단 밝기 (이보다 어두우면 버림)", min=0, max=255)]              = 90
    bright_high: Annotated[int,   UI(label="반사 상단 밝기 (이보다 밝으면 버림, 255=코어 유지)", min=0, max=255)] = 255

    def Run(self, frame: IMAGE, roi: BBOX | GRAY_IMAGE | None = None, **kwargs) -> dict:
        _s = min(frame.shape[:2])                          # 공간 파라미터의 기준 = 짧은 변
        _bright = Band_threshold(frame, low=self.bright_low, high=self.bright_high)
        _source = Lowpass_bright_mask(
            frame, sigma=max(1.0, self.sigma_frac * _s), thr=self.source_thr,
            close=int(self.close_frac * _s))
        _refl = Combine_regions(_bright, _source, "subtract")

        if roi is not None:
            _refl = Mask_within_roi(_refl, roi)
            if _refl is None:
                return {}

        return {"mask": _refl} if _refl.any() else {}
