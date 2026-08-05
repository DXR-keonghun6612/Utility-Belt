"""mask 픽셀마다 magic-wand 를 눌러 넓히거나 걷어낸다 — ``func.mask.refine`` 의 배선.

각 유닛은 **한 방향만** 한다: ``Refine_*`` 넓힘 · ``Cut_objects`` 좁힘. 이 층이 하는 일은
``roi``/``bbox`` 를 영역 bool 로 풀고 선택적 ``edge`` 벽을 넘긴 뒤 결과를 ``Data_Ref`` 로 되싸는
것뿐이고, 알고리즘·근거는 ``func.mask.refine`` 이 갖는다. 벽(``edge``)은 변화량 기반 producer
(``Detect_log_edge`` · ``Detect_edge``)가 프레임 전체에서 생성해 흘리고, 색 기준은 func 안쪽이 소유한다.

``Refine_mask`` 는 mask 한 장을, ``*_objects`` 는 프레임의 객체마다 **제 색**으로 처리한다(frame
단위에서 obj별 기준색) — 프레임 하나의 단일 평균이 색이 다른 객체를 뭉개는 것을 피한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import numpy as np

from .. import PROCESS_REGISTRY, Base_Process, UI, BBOX, GRAY_IMAGE
from ....schema import Data_Ref
from ....func.cv.geom import Roi_to_mask
from ....func.mask import refine as _refine   # 유닛 이름이 func 이름을 가리지 않게 모듈 참조
from ._objects import map_objects              # 객체별 mask 변형 공용 순회 (refine·cut 공유)


@PROCESS_REGISTRY.Register_module()
@dataclass
class Refine_mask(Base_Process, outputs=("mask",), category="마스크/정리"):
    """기존 ``mask`` 의 픽셀마다 magic-wand 를 눌러 ``roi``(bbox) 안에서 **넓힌다** — 확장 전용.

    경계에서 ``seed_margin`` px 안쪽이고 평균색에서 ``seed_tolerance`` 이내인 자리를 seed 로 삼아, 그
    **seed 자신의** 색 ±``tolerance`` 인 이웃으로 번진다(``edge`` 벽·``roi`` 에서 멈춤).
    **아무것도 깎지 않는다** — 결과는 언제나 입력 mask 의 상위집합이다. 걷어내기는 ``cut_objects`` 가
    맡는다. ``edge`` 는 변화량 producer 가 낸 벽(선택 입력, 없으면 색만으로 번짐). ``roi`` 없으면 프레임
    전체. 결과가 비면 스킵(``{}``). 인자 의미는 ``func.mask.refine.Refine_by_color``.
    """

    tolerance:  Annotated[int,   UI(label="번짐 허용", tip="seed 색 ± 이 값만큼 이웃으로 번진다 (FIXED_RANGE)", min=0, max=255)]                  = 10
    seed_tolerance: Annotated[int, UI(label="seed 자격", tip="평균색에서 이 값 이내인 자리만 seed 로 찍는다", min=0, max=255)]          = 20
    bright_margin: Annotated[int, UI(label="반사광 제외", tip="평균 + 이 값 이상은 기준색 평균 표본에서 뺀다", min=0, max=255)] = 40
    fill_radius:Annotated[int,   UI(label="번짐 반경", tip="mask 에서 이 거리 안만 번진다 (px, 0=끄기 → bbox 전체)", min=0, max=500)] = 30
    grow:       Annotated[int,   UI(label="되붙임", tip="번진 뒤 벽 띠만큼 경계에 되붙임 (반경 px)", min=0, max=20)]          = 3
    seed_margin:Annotated[int,   UI(label="seed 시작 깊이", tip="경계에서 안쪽 이만큼부터 seed (px, 0=경계도)", min=0, max=20)]            = 5
    close_size: Annotated[int,   UI(label="틈 메움", tip="번진 영역의 작은 틈을 CLOSE 로 메움 (px, 0=끄기)", min=0, max=31)]           = 3
    min_area:   Annotated[int,   UI(label="최소 면적", tip="새로 덮은 조각 중 이보다 작으면 버린다 (px², 0=끄기)", min=0, max=100000)]      = 0

    def Run(
        self, frame: np.ndarray, mask: GRAY_IMAGE,
        roi: BBOX | GRAY_IMAGE | None = None, edge: GRAY_IMAGE | None = None, **kwargs,
    ) -> dict:
        _out = _refine.Refine_by_color(
            frame, mask, Roi_to_mask(roi, frame.shape[:2]),     # None = 프레임 전체
            wall=edge,
            tolerance=self.tolerance, seed_tolerance=self.seed_tolerance,
            bright_margin=self.bright_margin,
            seed_margin=self.seed_margin, fill_radius=self.fill_radius, grow=self.grow,
            close_size=self.close_size, min_area=self.min_area)
        return {"mask": _out} if _out is not None else {}


@PROCESS_REGISTRY.Register_module()
@dataclass
class Refine_objects(Base_Process, outputs=("object",), category="마스크/정리"):
    """프레임의 객체마다 mask 픽셀에서 magic-wand 를 눌러 **넓힌다** (frame 단위, obj별 기준색).

    각 객체의 ``mask``(rle) 안쪽을 seed 자리로, ``bbox`` 를 ``bbox_gap`` 만큼 넓힌 사각을 번질 수 있는
    영역으로 ``func.mask.refine.Refine_by_color`` 를 돌린다. 기준색이 **객체마다 제 색**이라 색이 다른
    객체가 섞여도 안 뭉개고, 번짐 기준은 평균이 아니라 **각 seed 자신의 색**이라 얼룩덜룩한 객체도 제
    색으로 뻗는다. **아무것도 깎지 않는다**(결과 ⊇ 입력). 걷어내기는 ``cut_objects`` 가 맡는다.
    ``edge`` 는 변화량 producer 가 낸 벽(선택 입력, 없으면 색만으로 번짐). bbox 는 결과에서 다시 잰다.
    실패한 객체는 원본을 유지한다. 객체가 없으면 스킵(``{}``).
    """

    tolerance:  Annotated[int,   UI(label="번짐 허용", tip="seed 색 ± 이 값만큼 이웃으로 번진다 (FIXED_RANGE)", min=0, max=255)]                  = 10
    seed_tolerance: Annotated[int, UI(label="seed 자격", tip="평균색에서 이 값 이내인 자리만 seed 로 찍는다", min=0, max=255)]          = 20
    bright_margin: Annotated[int, UI(label="반사광 제외", tip="평균 + 이 값 이상은 기준색 평균 표본에서 뺀다", min=0, max=255)] = 40
    fill_radius:Annotated[int,   UI(label="번짐 반경", tip="mask 에서 이 거리 안만 번진다 (px, 0=끄기 → bbox 전체)", min=0, max=500)] = 30
    grow:       Annotated[int,   UI(label="되붙임", tip="번진 뒤 벽 띠만큼 경계에 되붙임 (반경 px)", min=0, max=20)]          = 3
    seed_margin:Annotated[int,   UI(label="seed 시작 깊이", tip="경계에서 안쪽 이만큼부터 seed (px, 0=경계도)", min=0, max=20)]            = 5
    bbox_gap:   Annotated[float, UI(label="번짐 영역", tip="bbox 를 이 비율로 확대해 번질 수 있는 영역", min=0.0, max=1.0, step=0.05)]  = 0.2
    close_size: Annotated[int,   UI(label="틈 메움", tip="번진 영역의 작은 틈을 CLOSE 로 메움 (px, 0=끄기)", min=0, max=31)]           = 3
    min_area:   Annotated[int,   UI(label="최소 면적", tip="새로 덮은 조각 중 이보다 작으면 버린다 (px², 0=끄기)", min=0, max=100000)]      = 0

    def Run(
        self, object: list[Data_Ref], frame: np.ndarray,
        edge: GRAY_IMAGE | None = None, **kwargs,
    ) -> dict:
        if not object or frame is None:
            return {}
        _new = map_objects(object, frame, self.bbox_gap, lambda _f, _m, _r: _refine.Refine_by_color(
            _f, _m, _r, wall=edge,
            tolerance=self.tolerance, seed_tolerance=self.seed_tolerance,
            bright_margin=self.bright_margin,
            seed_margin=self.seed_margin, fill_radius=self.fill_radius, grow=self.grow,
            close_size=self.close_size, min_area=self.min_area))
        return {"object": _new} if _new else {}


@PROCESS_REGISTRY.Register_module()
@dataclass
class Cut_objects(Base_Process, outputs=("object",), category="마스크/정리"):
    """객체마다 mask 안에서 **평균색 밖으로 뜨는 자리**를 magic-wand 로 걷어낸다 — 축소 전용.

    ``refine_objects`` 의 거울상이다: 거기서는 평균색 이내인 안쪽 픽셀을 눌러 밖으로 넓혔고, 여기서는
    평균색에서 ``cut_tolerance`` 를 넘게 벗어난 mask 안 픽셀을 눌러 그 자리를 뺀다(삐져나간 과칠,
    물린 배경 조각). **반사광은 벽으로 막아 보호**하고, 번짐은 mask 안에 갇힌다. 전부 걷어내질 객체는
    손대지 않는다. bbox 는 다시 잰다. 근거·인자는 ``func.mask.refine.Cut_by_color``.
    """

    tolerance:  Annotated[int,   UI(label="번짐 허용", tip="seed 색 ± 이 값만큼 이웃으로 번진다 (FIXED_RANGE)", min=0, max=255)]                  = 12
    cut_tolerance: Annotated[int, UI(label="걷어낼 seed 자격", tip="평균색에서 이 값을 넘게 벗어난 mask 안 자리만 seed", min=0, max=255)]      = 40
    bright_margin: Annotated[int, UI(label="반사광 보호", tip="평균 + 이 값 이상은 벽으로 심어 보호한다 (안 지움)", min=0, max=255)]   = 40
    seed_margin:Annotated[int,   UI(label="평균색 표본 깊이", tip="기준색 표본으로 쓸 안쪽 침식 — 경계 혼합색을 뺀다 (px)", min=0, max=20)]          = 3
    grow:       Annotated[int,   UI(label="걷어내기 확대", tip="걷어낸 영역 팽창 — 남은 벽 띠까지 (반경 px)", min=0, max=20)]      = 0
    close_size: Annotated[int,   UI(label="틈 메움", tip="걷어낸 영역을 CLOSE 로 한 덩어리 (px, 0=끄기)", min=0, max=31)]                = 0
    min_area:   Annotated[int,   UI(label="최소 면적", tip="이보다 작은 걷어내기는 무시한다 (px², 0=끄기)", min=0, max=100000)]    = 0

    def Run(self, object: list[Data_Ref], frame: np.ndarray,
            edge: GRAY_IMAGE | None = None, **kwargs) -> dict:
        if not object or frame is None:
            return {}
        _new = map_objects(object, frame, 0.0, lambda _f, _m, _r: _refine.Cut_by_color(
            _f, _m, wall=edge,
            tolerance=self.tolerance, cut_tolerance=self.cut_tolerance,
            bright_margin=self.bright_margin, seed_margin=self.seed_margin,
            grow=self.grow, close_size=self.close_size, min_area=self.min_area))
        return {"object": _new} if _new else {}
