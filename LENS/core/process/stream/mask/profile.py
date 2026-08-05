"""형상 원본 유닛 — 객체들의 mask 를 **정렬된 극좌표 밴드 배치**(``radial_rle``) 한 장으로.

사슬은 [`shape.py`](shape.py) 가 들고, 이 유닛은 **눈금을 든다** — 그 값이 flow config 에 적히므로
"무엇으로 뽑았나"의 단일 출처가 설정 파일이 된다.

무엇을 저장할지는 이미 정해져 있었다 — ``config/gauge/mask_shape.yaml`` 이 ``radial_domains: [rle]``
한 줄과 함께 *"저장하는 것은 원본 RLE 하나. 나머지 접기는 잣대가 읽을 때 접는다"* 라고 적어 뒀다.
``signed``·``outline`` 은 전부 이 하나에서 접혀 나온다(``RADIAL_FOLDS``).

## 왜 ``.analysis`` 가 아니라 정본에 두나

측정값이 표본 주소(``(stem, obj_id)``)로만 이어져 있으면 **편집이 그 연결을 끊는다** — 저장 정돈이
obj_id 를 중심 가까운 순으로 재부여하고, 병합은 흡수된 id 를 지우고, 삭제는 구멍을 낸다. 그때
``.analysis`` 는 옛 번호를 들고 있어 값이 조용히 다른 객체에 붙는다. 값이 객체와 **함께 움직이면**
그 사고가 구조적으로 불가능하다. ``.analysis`` 는 **판정**(type 배정·거리·정규화 상수)만 든다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Annotated
from functools import lru_cache

import numpy as np

from ....format import pose, rle
from ....func.cv.geom import Mask_centroid
from ....schema import Build, Data_Ref
from .. import PROCESS_REGISTRY, Base_Process, UI
from .shape import Geometry_chain

#: 정본 leaf 이름 — feature 이름과 **같게** 둔다(추출이 읽을 때 이름을 옮길 자리가 없게).
LEAF = "radial_rle"

#: 그 배열의 라우팅 spec — stem 직속 npy 한 장.
LEAF_SPEC: dict = {"to": "storage", "type": "array", "format": "npy"}

#: 눈금을 적어 두는 params leaf 이름 — 무엇으로 뽑은 배열인지 정본이 스스로 답하게.
SPEC_PARAM = "profile_spec"

#: 눈금 키 — 유닛 필드 이름과 같다.
SPEC_KEYS = ("crop", "size", "num_radial", "num_angular", "max_transitions", "threshold")


@PROCESS_REGISTRY.Register_module()
@dataclass
class Radial_profile(Base_Process, outputs=("radial_rle", "object"), category="마스크/형상"):
    """객체별 mask → stem 배열 ``(n_obj, NT, K)`` + 객체마다 ``pose``. **배열 행이 곧 obj_id 다.**

    **둘을 함께 내는 이유는 한 패스이기 때문이다.** 극좌표를 뜨려면 정준 좌표계(무게중심·주축각)를
    먼저 구해야 하는데, 그 각이 곧 자세다. 나눠 두면 같은 ``Centroid_Frame`` 을 두 번 돌리고, 더
    나쁘게는 **두 값이 갈릴 수 있다** — 사람이 적어 둔 자세와 학습이 쓰는 정렬이 다른 정면을 보게 된다.

    mask 를 안 바꾼다 — 형상을 **비교 가능한 좌표로 옮기는** 유닛이다. 무게중심과 주축각으로 정준화한
    극좌표에서 광선마다 밴드 경계를 떠 놓으므로, 표본끼리 정렬을 다시 하지 않고 바로 겹쳐 볼 수 있다
    (평균·중앙값·정합의 입력).

    **왜 객체 인라인이 아니라 stem 배열인가** — 표본 하나가 ``512×8 = 4096`` 개다. 인라인이면 사이드카가
    객체당 40 KB 라 6만 표본에서 2.5 GB 이고, 그게 전부 ``Bucket_Store.Restore`` 로 **메모리에 상주**
    한다(사이드카가 곧 트리다). 파일로 빼면 필요할 때만 실린다. 객체마다 파일을 주는 길도 있지만 그건
    "객체는 payload-free" 를 깬다(이름이 곧 경로가 되어 obj_id 재부여가 막힌다) — 그래서 **stem 당 한 장**.

    mask 가 없거나 빈 객체의 행은 **NaN** 이다. 0 으로 채우면 "반경 0 인 객체"라는 거짓말이 되고, 행을
    빼면 행 번호와 obj_id 가 어긋난다. 객체가 없거나 전부 비면 빈 dict("스킵").

    눈금 기본값은 지금 쓰는 규약이다 — 근거는 ``config/gauge/mask_shape.yaml`` 의 주석이 소유한다
    (280 → 224 축소가 왜 순손실이었는지 등). **바꾸면 옛 배열과 비교할 수 없다.**
    """

    crop:            Annotated[int, UI(label="crop 창 한 변 (px, 원본 스케일)",
                                       tip="bbox 중심 크롭. 추론 CropSilhouette 와 같아야 한다",
                                       min=32, max=1024)]                              = 280
    size:            Annotated[int, UI(label="정준 캔버스 한 변 (px)",
                                       tip="crop 과 같으면 축소 없음 — 줄이면 경계를 성긴 격자에 "
                                           "다시 얹어 손실", min=32, max=1024)]         = 280
    num_radial:      Annotated[int, UI(label="반경 눈금 수 (NR)",
                                       tip="캔버스 한 변과 같으면 1px 간격",
                                       min=32, max=1024)]                              = 280
    num_angular:     Annotated[int, UI(label="θ 토큰 수 (NT)", min=16, max=2048)]        = 512
    max_transitions: Annotated[int, UI(label="θ 당 최대 전이점 (K)",
                                       tip="광선 하나가 지나는 밴드 경계 상한",
                                       min=2, max=32)]                                 = 8
    threshold:       Annotated[float, UI(label="occupancy 임계",
                                         tip="셀을 '재료 있음' 으로 볼 분수 하한",
                                         min=0.0, max=1.0, step=0.05)]                 = 0.5

    def __post_init__(self) -> None:
        self._chain: Geometry_chain | None = None       # 무겁다 — 첫 호출에 짓고 재사용

    def Spec(self) -> dict:
        """이 유닛이 쓰는 눈금 ``{키: 값}`` — 정본 ``params/profile_spec`` 에 그대로 적힌다."""
        return {_k: _v for _k, _v in asdict(self).items() if _k in SPEC_KEYS}

    def Chain(self) -> Geometry_chain:
        """이 눈금의 사슬 (처음 부를 때 짓는다)."""
        if self._chain is None:
            self._chain = Geometry_chain(**self.Spec())
        return self._chain

    def Run(self, object: list[Data_Ref], **kwargs) -> dict:
        if not object:
            return {}
        _chain = self.Chain()
        _nt, _k = int(self.num_angular), int(self.max_transitions)
        _stack = np.full((len(object), _nt, _k), np.nan, np.float32)
        _new: list[Data_Ref] = []
        _any = False
        for _i, _o in enumerate(object):
            _m = _o.Attr("mask", None)
            _out = _chain.Profile(rle.To_mask(_m)) if isinstance(_m, dict) else None
            if _out is None:                       # mask 가 없거나 비었다 — 행은 NaN, 자세는 안 얹는다
                _new.append(_o)
                continue
            _rle, (_angle, _, _) = _out
            _stack[_i] = _rle
            _any = True
            # 자리는 **무게중심**이다 — `Mask_center` 의 규약과 같아야 "가까운 순"과 자세가 서로 다른
            # 곳을 가리키지 않는다. 정준 프레임의 중심은 crop 좌표라 원본으로 되돌릴 수 없으므로
            # 여기서 원본 mask 로 잰다.
            _c = Mask_centroid(rle.To_mask(_m))
            if _c is None:
                _new.append(_o)
                continue
            _new.append(Data_Ref(info={**dict(_o.info), **Build({
                "pose": {"format": ("pose", "quat"),
                         "info": {"value": pose.From_2d(_c, _angle)}}})}))
        return {} if not _any else {"radial_rle": _stack, "object": _new}


def Default_spec() -> dict:
    """유닛 필드 기본값으로 만든 눈금 — 정본에 ``profile_spec`` 이 없을 때의 답."""
    return {_f.name: _f.default for _f in fields(Radial_profile) if _f.name in SPEC_KEYS}


def Chain_for(spec: dict) -> Geometry_chain:
    """그 눈금의 사슬 — **눈금별로 한 번만 짓는다**(모듈 조립이 무겁다).

    유닛 밖(편집 저장 등)에서 한 표본만 다시 뽑을 때 쓰는 문이다. ``dict`` 은 해시가 안 되므로 키를
    정규화해 캐시한다.
    """
    return _chain_cached(tuple((_k, spec[_k]) for _k in SPEC_KEYS))


@lru_cache(maxsize=4)
def _chain_cached(items: tuple) -> Geometry_chain:
    return Geometry_chain(**dict(items))


def Stack(masks: list[np.ndarray | None], chain: Geometry_chain) -> np.ndarray | None:
    """객체별 mask 목록 → stem 한 장짜리 ``(n_obj, NT, K) float32``. 전부 비면 None.

    **행이 곧 obj_id 다** — 호출 측은 obj_id 가 확정된 뒤(정렬·재부여 후)에 불러야 한다. mask 가
    없거나 빈 자리는 **NaN 행**이다.

    유닛은 이걸 안 쓴다(자기 루프에서 자세와 함께 만든다) — 이미 객체가 있는 정본에 배열만 다시
    뜨는 자리(GUI 저장 정돈)가 쓴다.
    """
    _rows = [None if _m is None else chain.Radial_rle(_m) for _m in masks]
    if not any(_r is not None for _r in _rows):
        return None
    _nt = int(chain.spec["num_angular"])
    _k = int(chain.spec["max_transitions"])
    _out = np.full((len(_rows), _nt, _k), np.nan, np.float32)
    for _i, _r in enumerate(_rows):
        if _r is not None:
            _out[_i] = _r
    return _out
