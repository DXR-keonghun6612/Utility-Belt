"""process 패키지 — process 유닛 레지스트리 + flow 조립.

``__init__`` 이 레지스트리(``PROCESS_REGISTRY``)와 조립 팩토리(``Build_process``/``Build_flow``)를
소유한다. 기본 구조(``Flow``/``Base_Process``)는 ``_base.py``, process 구현은 하위 패키지
(preprocess/mask/edge/chroma/model/utils)에 있다. flow 종류는 코드 preset이 아니라 **config가 직접 기술**한다
(복붙용 템플릿: ``presets.example.yaml``).
"""

from __future__ import annotations

import dataclasses

from python_toolbox.registry import Registry

from ._base import Flow, Stage, Base_Process, UI, BBOX, GRAY_IMAGE

PROCESS_REGISTRY = Registry[type]("process", Base_Process)


def Build_process(name: str, param: dict | None = None) -> Base_Process:
    """이름과 파라미터로 process 인스턴스를 생성한다.

    config dict에 process가 모르는 키(흐름-공유 ``space`` 등)가 섞여 있어도 되도록 선언된
    dataclass 필드만 추려 넘긴다.
    리소스 스펙(``model: {type: sam3, …}``)은 pipeline 이 미리 객체로 치환해 주므로 여기선
    이미 만들어진 모델 객체가 그대로 필드로 들어온다.
    """
    _cls    = PROCESS_REGISTRY.Get(name)
    _fields = {_f.name for _f in dataclasses.fields(_cls)}
    return _cls(**{_k: _v for _k, _v in (param or {}).items() if _k in _fields})


# 유닛 등록 트리거 (PROCESS_REGISTRY 정의 후 import) — 각 모듈이 @PROCESS_REGISTRY.Register_module.
from .chroma     import Convert_to_Chroma, Accumulate_Chroma_histogram, Robust_Chroma_Stats, Chroma_distance  # noqa: E402
from .preprocess import Frame_crop, Normalize_color  # noqa: E402
from .mask       import Threshold_score, Normalize_mask, Morph_mask, Combine_mask, Split_objects  # noqa: E402
from .edge       import Detect_edge, Close_edge, Fill_edge, Edge_blob, Remove_edge_holes  # noqa: E402
from .model      import Segment_with_hole  # noqa: E402
from .select     import Center_distance, Attr_gate  # noqa: E402


def Build_flow(cfg: dict) -> Flow:
    """flow config(dict)로 ``Flow`` 를 구성한다.

    ``object_type`` 은 진행 표시 라벨로만 쓰고 나머지 키는 ``Flow`` 필드(``processes``/
    ``finalize_processes``/``unit``/``shared``/``carry``/``cacheable`` …)로 그대로 넘긴다.
    flow 종류는 코드 preset이 아니라 **config가 직접 기술**한다 — 복붙용 템플릿은
    ``presets.example.yaml`` 참조.
    """
    _name = cfg.get("object_type")
    return Flow(object_type=_name or "flow",
                **{_k: _v for _k, _v in cfg.items() if _k != "object_type"})


__all__ = [
    # 기본 구조
    "Flow", "Stage", "Base_Process", "UI", "BBOX", "GRAY_IMAGE",
    # 레지스트리·조립
    "PROCESS_REGISTRY", "Build_process", "Build_flow",
    # process 유닛
    "Convert_to_Chroma", "Accumulate_Chroma_histogram", "Robust_Chroma_Stats",
    "Chroma_distance",
    "Segment_with_hole",
    "Frame_crop", "Normalize_mask", "Normalize_color", "Split_objects",
    "Threshold_score", "Morph_mask", "Detect_edge", "Close_edge", "Fill_edge",
    "Edge_blob", "Remove_edge_holes", "Combine_mask",
    "Center_distance", "Attr_gate",
]
