"""저장 시 객체별 mask → 인스턴스 segment 한 장으로 합치는 순수 함수 (obj_id 재번호)."""

from __future__ import annotations

import numpy as np

from core.schema import Data_Ref
from core.store import Dataset_Meta

from gui.meta_page.edit._helpers import _bbox_of


def _intersect_mask_bbox(mask: np.ndarray, bbox) -> np.ndarray:
    """mask 에서 bbox 사각형 밖을 0 으로 지운 교집합 mask 를 만든다 (값/dtype 보존).

    Args:
        mask: ``(H, W)`` 또는 ``(H, W, C)`` mask 배열.
        bbox: ``[x0, y0, x1, y1]`` (이미지 범위로 클램프된다).

    Returns:
        bbox 안쪽만 남긴 ``mask`` 와 동형 배열.
    """
    _h, _w = mask.shape[:2]
    _x0, _y0, _x1, _y1 = (int(round(float(_v))) for _v in bbox)
    _x0, _x1 = sorted((max(0, min(_x0, _w)), max(0, min(_x1, _w))))
    _y0, _y1 = sorted((max(0, min(_y0, _h)), max(0, min(_y1, _h))))
    _out = np.zeros_like(mask)
    _out[_y0:_y1, _x0:_x1] = mask[_y0:_y1, _x0:_x1]
    return _out


def write_segment(
    meta: Dataset_Meta, stem: str, work: Data_Ref,
    all_masks: list[tuple[Data_Ref, np.ndarray | None]],
    bbox_orig: dict, size: tuple[int, int] | None,
) -> None:
    """모든 객체 mask 를 인스턴스 라벨맵 한 장으로 합쳐 ``work`` 의 ``segment`` LEAF 로 저장한다.

    저장 시 **obj_id 를 자동 압축**한다 — mask 가 빈(지워진/안 그린) 객체는 버리고, 남은
    객체를 트리 순서대로 ``0..N-1`` 로 재부여(= info key)한 뒤 그 값 + 1 로 segment 를 칠한다.
    그래서 한 객체를 지우면(빈 mask) 그 id 가 사라지고 뒤 객체들이 당겨져 segment 값과 obj_id 가
    항상 빈틈 없이 맞는다. bbox 가 로드 이후 바뀐 객체는 새 bbox 와의 교집합으로 mask 를
    자른 뒤 칠한다(편집 중엔 보존, 저장 때만 적용). ``work`` 를 제자리에서 갱신한다.

    payload write 는 ``meta.Route`` 에 **요청**한다 — 파일이 어디 갈지는 store 가 정한다(트리 위치에서
    파생). gui 는 "이 값을 segmap 으로 담아라"만 말한다.

    Args:
        meta: 정본 store (payload write 위임).
        stem: 대상 stem.
        work: 갱신할 작업 프레임 컨테이너 ``Data_Ref`` (``segment`` LEAF·객체 entry 가 바뀐다).
        all_masks: ``(객체 Data_Ref, mask|None)`` 목록 (트리 순서 = object 순서).
        bbox_orig: ``{id(obj): bbox|None}`` 로드 직후 bbox 스냅샷 (변경 감지용).
        size: segment 캔버스 크기 ``(H, W)`` (없으면 첫 mask 에서 파생).
    """
    _size = size
    _kept: list[tuple[Data_Ref, np.ndarray]] = []
    for _obj, _mask in all_masks:
        if _mask is None or not np.any(_mask):
            continue                                    # 지워졌거나 안 그린 객체 → 정리(제외)
        _bbox = _bbox_of(_obj)
        if _bbox is not None and _bbox != bbox_orig.get(id(_obj)):
            _mask = _intersect_mask_bbox(_mask, _bbox)
            if not np.any(_mask):
                continue
        if _size is None:
            _size = _mask.shape[:2]
        _kept.append((_obj, _mask))

    _new_objs: dict[str, Data_Ref] = {}
    if _size is not None and _kept:
        _seg = np.zeros(_size, dtype=np.uint8)
        for _i, (_obj, _mask) in enumerate(_kept):
            _seg[_mask > 0] = np.uint8(_i + 1)          # 그 값 + 1 로 segment 칠함
            _new_objs[str(_i)] = _obj                   # obj_id 압축 (0..N-1) = info key
        _path = meta.Item_path(stem)
        work.Push("segment", meta.Route(                # 경로는 store 가 파생 (kind-major)
            _path, "segment", {"to": "storage", "type": "segmap", "format": "png"}, _seg))
    else:
        work.Pop("segment")                             # 남은 mask 없음 → segment 제거

    # work 재구성 — LEAF(segment 등) 보존 + 정리된 객체(mask 없는 객체 제외)
    work.info = {**work.Leaves(), **_new_objs}
