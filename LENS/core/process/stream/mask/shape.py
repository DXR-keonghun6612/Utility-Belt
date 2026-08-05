"""형상 feature 연산 — crop → resize → geometry 사슬의 **조립과 실행**.

``core/analysis`` 에 있던 계산을 여기로 뺐다. 그쪽이 드는 것은 **계약**(무엇을 저장하고 무엇으로 재나 —
``Extract_Spec``·``Gauge_Spec``·``Fold``)이고, 여기가 드는 것은 **계산**(마스크 한 장을 어떤 사슬에
태우나)이다. 같은 파일에 있는 동안은 "형상을 뽑는다"는 일이 판정 계층에 묶여 있어서, flow 로 그 값을
만들 수가 없었다 — 유닛이 부를 수 있는 자리에 계산이 없었기 때문이다.

**모듈 자체는 ``torch_toolbox`` 가 소유한다** (``modules/transform/mask``). 학습과 같은 그래프를 태워야
"여기서 본 형상 = 학습이 보는 형상" 이 성립하므로, 여기서는 **조립만** 한다 — 순서를 잇고 배치축을
떼는 것까지가 이 모듈의 일이다.

## 눈금은 인자다

``crop``·``size``·``num_radial``·``num_angular``·``max_transitions``·``threshold`` 를 상수로 박지
않는다. 박으면 flow config 로 못 바꾸고, 바꾸려면 코드를 고쳐야 한다. 기본값은 이것을 돌리는 유닛
([`profile.py`](profile.py))의 필드가 들고, flow 설정이 그 위를 덮는다 — 즉 **"무엇으로 뽑았나"의
단일 출처가 그 flow 설정**이다.

**눈금이 다른 배열은 같은 자 위에 있지 않다** — 그래서 값을 저장하는 쪽은 쓴 눈금을 함께 적어야 한다.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch

from torch_toolbox import CFGS
from torch_toolbox.modules import MODELS
from torch_toolbox.modules.build import Build_from_registry
# 등록 부작용 — crop/resize/geometry 및 그 descriptor 를 CFGS/MODELS 에 올린다.
# **순서가 있다**: silhouette 을 먼저 들여야 geometry 하위가 순환 import 로 안 터진다(extract 와 같다).
import torch_toolbox.modules.transform.mask.silhouette   # noqa: F401
import torch_toolbox.modules.transform.mask.geometry     # noqa: F401

#: 사슬을 이루는 등록 모듈 — 조립이 여기 하나라 이름도 여기 하나다.
_CFG_CROP   = "center_crop_Config"
_CFG_RESIZE = "resize_binarize_Config"
_CFG_GEOM   = "geometry_embedding_Config"


def Bbox_center(mask: np.ndarray) -> tuple[int, int]:
    """이진 mask 의 bbox 중심 ``(col, row)`` — **crop 창의 중심**.

    학습 ``_prepare_binary`` 의 중심과 같다. ``Centroid_Frame`` 이 안에서 다시 무게중심으로 재중심
    하므로 이 중심의 1px 오차는 실루엣을 바꾸지 않는다(객체가 crop 창 안에 다 들어오는 한).
    """
    _ys, _xs = np.nonzero(mask)
    return (int((_xs.min() + _xs.max()) // 2), int((_ys.min() + _ys.max()) // 2))


class Geometry_chain:
    """이진 mask → 도메인별 native feature. **조립된 사슬 하나** (무겁다 — 재사용해서 쓴다).

    ``crop`` 은 bbox 중심으로 고정 창을 떼고, ``resize`` 는 정준 캔버스로 맞추고, ``geometry`` 는
    무게중심·주축각으로 정준화한 극좌표에서 값을 뜬다. 그래서 나온 값은 **이미 정렬돼 있다** — 표본
    끼리 정렬을 다시 하지 않고 겹쳐 볼 수 있다.

    Attributes:
        spec: 이 사슬의 눈금 ``{crop, size, num_radial, num_angular, max_transitions, threshold}``.
    """

    def __init__(self, *, crop: int, size: int, num_radial: int, num_angular: int,
                 max_transitions: int, threshold: float,
                 radial_domains: tuple[str, ...] = ("rle",), device: str = "cpu") -> None:
        """Args:
            crop: bbox 중심 크롭 창 한 변(px, 원본 스케일).
            size: 정준 캔버스 한 변(px). ``crop`` 과 같으면 축소 없음.
            num_radial: 반경 눈금 수. 캔버스 한 변과 같으면 1px 간격.
            num_angular: θ 토큰 수 ``NT``.
            max_transitions: θ 당 최대 전이점 ``K``.
            threshold: 셀을 "재료 있음" 으로 볼 occupancy 분수 하한.
            radial_domains: 낼 radial 도메인 (``RADIAL_FOLDS`` 의 key). 저장하는 것은 ``rle`` 하나면
                충분하다 — 나머지는 잣대가 읽을 때 접는다.
            device: 모델을 올릴 device. 입력도 여기서 만드므로 불일치가 생길 자리가 없다.
        """
        self.spec = {"crop": int(crop), "size": int(size), "num_radial": int(num_radial),
                     "num_angular": int(num_angular), "max_transitions": int(max_transitions),
                     "threshold": float(threshold)}
        self.device = device
        _hw = (int(size), int(size))
        self.crop = Build_from_registry(
            CFGS.Get(_CFG_CROP)(crop_size=int(crop)), MODELS).to(device).eval()
        self.resize = Build_from_registry(
            CFGS.Get(_CFG_RESIZE)(target_size=_hw, thresh=float(threshold)),
            MODELS).to(device).eval()
        self.geometry = Build_from_registry(
            CFGS.Get(_CFG_GEOM)(
                size=_hw, num_radial=int(num_radial), num_angular=int(num_angular),
                max_transitions=int(max_transitions), occupancy_threshold=float(threshold),
                radial_domains=tuple(radial_domains)), MODELS).to(device).eval()

    @property
    def domain_kinds(self) -> dict[str, str]:
        """도메인 → 성질 (``FEATURE`` 순서 없음 / ``TOKEN`` 순서 있음)."""
        return self.geometry.domain_kinds

    def Canvas(self, mask: np.ndarray) -> torch.Tensor:
        """정렬 전 정준 실루엣 ``(1, 1, S, S)`` — crop → resize 까지. 사슬의 중간 지점."""
        _m = np.asarray(mask)
        _t = torch.from_numpy((_m > 0).astype(np.float32))[None, None].to(self.device)
        _c = torch.tensor([Bbox_center(_m)], dtype=torch.long, device=self.device)
        with torch.no_grad():
            return self.resize(self.crop(_t, _c))

    def Features(self, mask: np.ndarray) -> dict[str, np.ndarray]:
        """프레임-스케일 이진 mask → ``{도메인: 값}`` (배치축 없음). 빈 mask 면 ``{}``.

        빈 dict 은 **대상이 아니라는 뜻**이다 — 0 배열로 메우면 "반경 0 인 객체"라는 거짓말이 된다.
        """
        if not np.asarray(mask).any():
            return {}
        with torch.no_grad():
            _feats = self.geometry.Features(self.Canvas(mask))
        return {_d: _v[0].cpu().numpy() for _d, _v in _feats.items()}

    def Radial_rle(self, mask: np.ndarray) -> np.ndarray | None:
        """이진 mask → 정렬된 ``(NT, K) float32`` 밴드 배치. 전경이 없으면 None.

        슬롯 뜻은 안쪽부터 ``[시작r, 살1, 구멍1, 살2, …]`` — 짝수 자리가 빈 공간, 홀수가 살이다
        (``RADIAL_FOLDS`` 가 이 규약으로 접는다). ``Features`` 의 ``radial_rle`` 하나만 필요할 때
        쓰는 지름길이라, 스칼라 descriptor 를 계산하지 않는다.
        """
        _out = self.Profile(mask)
        return None if _out is None else _out[0]

    def Profile(self, mask: np.ndarray
                ) -> tuple[np.ndarray, tuple[float, float, float]] | None:
        """이진 mask → ``(밴드 배치 (NT,K), 자세 (angle, anisotropy, flip_margin))``. 빈 mask 면 None.

        **둘을 한 패스로 낸다** — 극좌표를 뜨려면 정준 좌표계(무게중심·주축각)를 먼저 구해야 하고,
        그 각이 곧 자세다. 따로 부르면 같은 ``Centroid_Frame`` 을 두 번 돌린다.

        ``angle`` 은 **이미지 좌표(y 아래) 기준**이라 양수면 화면에서 시계방향이다 — 자세를 담는
        [`core/format/pose`](../../../format/pose.py) 도 같은 좌표계라 그대로 얹힌다. crop 은 평행이동,
        resize 는 등방 스케일이라 **각을 안 바꾼다**(정준 캔버스에서 재도 원본의 각이다).

        **각은 신뢰도와 한 벌이다.** ``anisotropy`` 가 0 이면 주축이 없고(원환·n≥3 회전대칭에서
        **정확히** 0) 그때 각은 노이즈가 정한 값이다. ``flip_margin`` 이 0 이면 180° 확정이 픽셀
        노이즈로 뒤집힌다(2회 대칭에서 정확히 0). 근거는 ``Centroid_Frame`` 의 docstring 이 소유한다.
        """
        if not np.asarray(mask).any():
            return None
        with torch.no_grad():
            _canvas = self.Canvas(mask)
            _frame = self.geometry.frame(_canvas)
            _rle = self.geometry.rle(self.geometry.polar(_canvas, _frame))
        _angle = float(np.remainder(float(_frame.angle[0]) + np.pi, 2.0 * np.pi) - np.pi)
        return (_rle[0].cpu().numpy().astype(np.float32),
                (_angle, float(_frame.anisotropy[0]), float(_frame.flip_margin[0])))
