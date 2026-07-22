"""process 패키지 — process 유닛 레지스트리 + flow 조립.

``__init__`` 이 레지스트리(``PROCESS_REGISTRY``)와 조립 팩토리(``Build_process``/``Build_flow``)를
소유한다. 기본 구조(``Base_Process``/``Stage``/``Flow``)는 ``_base.py``, 유닛 구현은 ``stream/`` 하위
(preprocess·filter·mask·chroma·model·select)에 있다. flow 종류는 코드 preset 이 아니라
**config 가 직접 기술**한다 — 종류마다 클래스를 만들면 종류가 늘 때마다 코드가 는다.
"""

from __future__ import annotations

import dataclasses

from python_toolbox.registry import Registry

from ._base import Flow, Stage, Base_Process, UI, BBOX, IMAGE, GRAY_IMAGE

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
from .stream.chroma     import Convert_to_Chroma, Accumulate_Chroma_histogram, Robust_Chroma_Stats, Chroma_distance  # noqa: E402
from .stream.preprocess import Frame_crop, Normalize_color, Normalize_histogram, Downscale, Upscale  # noqa: E402
from .stream.mask       import Threshold_score, Intensity_band, Normalize_mask, Morph_mask, Combine_mask, Split_objects, Radial_thickness, Flood_background, Fill_edge, Edge_blob, Remove_edge_holes  # noqa: E402
from .stream.filter     import Detect_edge, Close_edge  # noqa: E402
from .stream.model      import Segment, Detect_instances  # noqa: E402
from .stream.select     import Center_distance, Attr_gate  # noqa: E402


from .sample import Sample_stage  # noqa: E402  (Stage 서브클래스 — _base 이후)


def Build_flow(cfg: dict) -> Flow:
    """flow config(dict)로 ``Flow`` 를 구성한다.

    ``object_type`` 은 진행 표시 라벨로만 쓰고 나머지 키는 ``Flow`` 필드(``processes``/
    ``finalize_processes``/``unit``/``shared``/``carry``/``cacheable`` …)로 그대로 넘긴다.
    flow 종류는 코드 preset 이 아니라 **config 가 직접 기술**한다 (설계는 ``README.md``).
    """
    _name = cfg.get("object_type")
    return Flow(object_type=_name or "flow",
                **{_k: _v for _k, _v in cfg.items() if _k != "object_type"})


__all__ = [
    # 기본 구조
    "Flow", "Stage", "Sample_stage", "Base_Process", "UI", "BBOX", "IMAGE", "GRAY_IMAGE",
    # 레지스트리·조립
    "PROCESS_REGISTRY", "Build_process", "Build_flow",
    # process 유닛
    "Convert_to_Chroma", "Accumulate_Chroma_histogram", "Robust_Chroma_Stats",
    "Chroma_distance",
    "Segment",
    "Frame_crop", "Normalize_mask", "Normalize_color", "Normalize_histogram",
    "Downscale", "Upscale", "Split_objects",
    "Threshold_score", "Intensity_band", "Morph_mask", "Detect_edge", "Close_edge", "Fill_edge",
    "Edge_blob", "Remove_edge_holes", "Combine_mask", "Radial_thickness",
    "Flood_background",
    "Center_distance", "Attr_gate",
]
