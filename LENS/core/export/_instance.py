"""프레임 단위 export 공통 base — 이미지 + 인스턴스(bbox·class·±mask) 중간표현.

detection 과 segmentation 이 **같은 프레임 빌드**(``unit=frame``)에서 나오고, 차이는 딱 하나 —
segmentation 은 인스턴스마다 **mask** 를 더 싣는다. 그래서 둘은 serializer(``coco``/``yolo``/``mask``)를
공유하고, ``Frame_exporter`` 가 그 공유 지점이다: sample 을 순회해 :class:`Frame_record` 목록으로
정규화하고, serializer 는 그 중간표현만 쓴다.

**mask 는 [`mask` 도메인](../port/domain/mask.py)에서 온다 — 객체가 자기 mask 를 든다.** 각 객체가
``mask`` 를 rle·polygon·png 어느 포맷으로든 들고, 그게 곧 그 인스턴스의 픽셀이다(정본). export 는
포맷을 손으로 풀지 않고 ``store.Decode`` 로 배열을 받는다(binder 는 port 직접 호출 금지 — store 창구).

**mask 를 켜는 건 task 다** — ``TASKS[task].needs_mask``. 같은 ``Coco_exporter`` 가 ``detection`` 이면
bbox 만, ``segmentation`` 이면 annotation 에 ``segmentation`` 필드까지 낸다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..format import bbox as _bbox_fmt
from ..format import rle as _rle_fmt
from ..schema import Data_Ref
from ._base import Exporter


@dataclass
class Instance:
    """프레임 안 객체 하나 — export 중간표현.

    좌표는 **정본 규약 그대로** 든다(bbox = ``xyxy`` 코너). COCO/YOLO 변환은 serializer 몫이다 —
    중간표현이 특정 포맷 규약을 미리 먹으면 다른 serializer 가 되돌려야 한다.

    Attributes:
        obj_id:   프레임 안 객체 순번(=라벨맵 값 -1).
        class_id: class 이름. ``None`` 이면 class-agnostic (serializer 가 class 를 생략).
        bbox:     ``[x0, y0, x1, y1]`` 코너 (없으면 None).
        mask:     obj 이진 mask ``(H, W)`` — **segmentation task 에서만** 채워진다(아니면 None).
    """

    obj_id:   str
    class_id: str | None
    bbox:     list[float] | None
    mask:     np.ndarray | None = None


@dataclass
class Frame_record:
    """프레임 하나 = 원본 이미지 + 그 인스턴스들 — serializer(coco/yolo/mask)의 입력 단위.

    ``size_hw`` 는 COCO ``images`` 의 width/height 이자 YOLO 좌표 정규화의 분모다 — 즉 **좌표를 읽는
    쪽이 반드시 필요로 하는 값**이라 중간표현이 든다(serializer 가 파일을 다시 열지 않게).
    """

    stem:      str
    image_src: Path | None            # 정본 프레임 원본 파일 (복사 원천; 없으면 None)
    instances: list[Instance] = field(default_factory=list)
    size_hw:   tuple[int, int] | None = None   # 프레임 (H, W) — 못 구하면 None


@dataclass
class Frame_exporter(Exporter):
    """프레임 단위 sample → :class:`Frame_record` 정규화 (det·seg serializer 공통 base).

    서브클래스(``Coco_exporter``·``Yolo_exporter``·``Mask_exporter``)는 ``Export`` 에서 split 마다
    :meth:`_records` 를 받아 자기 레이아웃으로 직렬화만 한다. 픽셀은 sample 이 아니라 **정본**(``meta``)의
    프레임 leaf 에 있다(순수 역참조) — ``image_key`` 가 그 leaf 이름.

    Attributes:
        image_key: 정본 프레임 이미지 leaf 이름 (ingest glob key — 기본 ``frame``).
    """

    image_key: str = "frame"

    # ── task 성격 ──────────────────────────────────────────────────────────────
    def _needs_mask(self) -> bool:
        """이 task 가 인스턴스 mask 를 요구하나 — segmentation 이면 True (``segment`` 필수)."""
        from . import TASKS
        return bool(self.task) and TASKS[self.task].needs_mask

    # ── 정규화 ──────────────────────────────────────────────────────────────────
    def _source_item(self, ref: Data_Ref) -> Data_Ref | None:
        """sample 의 정본 프레임 item (``source_stem`` 역참조; 없으면 None).

        도메인 유지 sample 은 정본 순수 역참조라 객체(class·bbox)·segment 를 **정본에서 live** 로 읽는다 —
        sample 에 clone 이 없다. 재라벨하면 정본만 바뀌므로, clone 을 읽으면 bbox 는 옛것·mask 는 새것으로
        어긋난다(그 불일치를 없애려 여기서 한 출처로 읽는다).
        """
        _stem = ref.Attr("source_stem")
        return self.meta.Find(_stem) if (self.meta is not None and _stem) else None

    def _classes(self) -> set[str]:
        """전 split 인스턴스의 class 이름 집합 (id_map 자동생성용; class 없으면 빈 집합) — 정본 live."""
        return {_c
                for _split in self.source.CATEGORIES
                for _ref in self.source.Bucket(_split).values()
                if (_item := self._source_item(_ref)) is not None
                for _obj in _item.Branches().values()
                if (_c := _obj.Attr("class_id"))}

    def _records(self, split: str) -> list[Frame_record]:
        """한 split 의 프레임 sample 들을 :class:`Frame_record` 로 (정본 이미지 경로 + 인스턴스).

        객체(bbox·class·mask) 모두 **정본에서 live** 로 읽는다(한 출처 — 재라벨 불일치 제거).
        segmentation 이면 객체별 mask 를 싣는다 — 각 객체가 자기 ``mask``(mask 도메인)를 든다. 없으면
        조용히 bbox 로 떨어지지 않고 실패한다(:meth:`_instance`).
        """
        _out: list[Frame_record] = []
        for _sid, _ref in sorted(self.source.Bucket(split).items()):
            _item = self._source_item(_ref)                 # 정본 프레임 (객체 live)
            if _item is None:
                continue
            _stem = _ref.Attr("source_stem") or _sid
            _out.append(Frame_record(
                stem=_stem,
                image_src=self._frame_src(_stem),
                instances=[self._instance(_stem, _oid, _obj)
                           for _oid, _obj in _item.Branches().items()],
                size_hw=self._frame_size(_stem, _item)))
        return _out

    def _frame_size(self, stem: str, item: Data_Ref) -> tuple[int, int] | None:
        """프레임 ``(H, W)`` — **파일을 안 여는 경로부터** 차례로 (못 구하면 None).

        ① 프레임 leaf 서술자의 ``height``/``width``(정본에 적혀 있다) → ② 객체 mask 가 인라인 rle 면 그
        ``size``(rle 는 캔버스 크기를 들고 있다) → ③ 그래도 없으면 이미지를 로드해 shape 을 본다.
        앞의 둘은 디스크를 안 건드리므로, 프레임 수가 많아도 크기 때문에 파일을 다시 열지 않는다.
        """
        _leaf = item.Get(self.image_key)
        if _leaf is not None:
            _h, _w = _leaf.info.get("height"), _leaf.info.get("width")
            if _h and _w:
                return int(_h), int(_w)
        for _obj in item.Branches().values():           # 객체 mask 는 프레임 해상도 위에 산다
            _mref = _obj.Get("mask")
            _val = _mref.info.get("value") if _mref is not None else None
            if isinstance(_val, dict) and _val.get("size"):
                return _rle_fmt.Size(_val)
        _img = self.meta.Load(stem, self.image_key) if self.meta is not None else None
        return (int(_img.shape[0]), int(_img.shape[1])) if _img is not None else None

    def _instance(self, stem: str, obj_id: str, obj: Data_Ref) -> Instance:
        """객체 컨테이너 → :class:`Instance` (bbox·class, segmentation 이면 그 객체 mask 도).

        mask 는 **객체 자기 것(mask 도메인)** 이다 — rle·polygon·png 무관하게 store 가 배열로 준다. 없는데
        segmentation 이면 실패한다 — 조용히 bbox-only 로 떨어뜨리지 않는다.
        """
        _mask = None
        if self._needs_mask():
            _mask = self._obj_mask(stem, obj_id, obj)
            if _mask is None:
                raise ValueError(
                    f"segmentation 내보내기: '{stem}' 객체 '{obj_id}' 에 mask 가 없다 — segmentation "
                    "task 는 객체마다 mask 가 필요하다 (bbox-only 로 안 떨어뜨림)")
        return Instance(
            obj_id=obj_id,
            class_id=obj.Attr("class_id") or None,          # 없으면 class-agnostic
            bbox=self._bbox(obj),
            mask=_mask)

    # ── 좌표·픽셀 파생 ───────────────────────────────────────────────────────────
    @staticmethod
    def _bbox(obj: Data_Ref) -> list[float] | None:
        """객체 bbox → ``[x0, y0, x1, y1]`` 코너. 없거나 형식이 아니면 실패/None.

        정본은 [`region`](../port/domain/region.py) 도메인 bbox 로 든다(``("region", "bbox", style)``).
        저장 style 이 무엇이든 코너로 정규화한다 — [`format.bbox`](../format/bbox.py) 가 그 변환을 안다
        (COCO ``bbox`` 필드용 xyxy→xywh 는 serializer 가 따로 한다).
        """
        _box = obj.Get("bbox")
        if _box is None:
            return None
        _v = _box.info.get("value") or []
        if _box.format[:2] != ("region", "bbox") or len(_v) != 4:
            raise ValueError(f"export: bbox 가 region bbox 가 아니다 — format={_box.format} value={_v}")
        return _bbox_fmt.To_xyxy(_v, _bbox_fmt.Style_of(_box.format))

    def _obj_mask(self, stem: str, obj_id: str, obj: Data_Ref) -> np.ndarray | None:
        """객체 자기 ``mask`` 를 이진 배열로 (mask 도메인, 포맷 무관) — 없으면 None.

        객체가 자기 mask 를 든다(rle·polygon·png…). ``store.Decode`` 가 그 포맷을 손으로 풀지 않고
        도메인 경유로 배열을 준다 — export 는 binder 라 port 를 직접 못 부르고 store 창구를 쓴다.
        leaf 파일 경로 파생용으로 트리 위치 ``(범주, stem, obj_id)`` 를 넘긴다(인라인이면 안 쓰인다).
        """
        _leaf = obj.Get("mask")
        _ip = self.meta.Item_path(stem) if self.meta is not None else None
        if _leaf is None or _ip is None:
            return None
        return self.meta.Decode((*_ip, obj_id), "mask", _leaf)

    def _copy_image(self, rec: Frame_record, dst_dir: Path) -> str | None:
        """record 의 정본 프레임 원본 파일을 ``dst_dir`` 로 복사 (파일명 반환; 없으면 None)."""
        if rec.image_src is None:
            return None
        _name = f"{rec.stem}{rec.image_src.suffix}"
        self._copy(rec.image_src, dst_dir / _name)
        return _name

    # ── 검증 ────────────────────────────────────────────────────────────────────
    def _frame_src(self, stem: str) -> Path | None:
        """정본 프레임 이미지의 원본 파일 경로 (없으면 None) — serializer 가 복사한다.

        **범주를 하드코딩하지 않는다** — 빌드 뒤 stem 이 전이(예: 재라벨 → modified)했을 수 있어, store 에
        지금 자리를 물어 경로를 파생한다(`Item_path`+`Path_of`). 옛 코드는 `(STAGED, stem)` 을 손으로 박아
        전이한 프레임의 이미지를 조용히 빠뜨렸다.
        """
        _p = self.meta.Item_path(stem) if self.meta is not None else None
        _item = self.meta.Find(stem) if self.meta is not None else None
        _leaf = _item.Get(self.image_key) if _item is not None else None
        if _p is None or _leaf is None:
            return None
        _src = self.meta.Path_of(_p, self.image_key, _leaf)   # store 창구 (port 직접 안 부름)
        return _src if _src is not None and _src.exists() else None

    def _require_frame_samples(self) -> None:
        """sample 이 **프레임 단위**(정본 프레임 참조)인지 확인 — object 단위면 실패.

        det·seg 는 *이미지 하나 + 그 안의 객체들*이라 ``unit=frame`` 으로 빌드해야 한다. ``unit=object``
        는 객체 하나가 sample 이라 ``source_obj`` attr 이 붙는다(crop 기반 classification 용) — 그걸로 프레임
        참조와 가른다. object 단위를 프레임 내보내면 annotation 이 빈다 — 조용히 빈 manifest 를 내지 않고 막는다.
        """
        _samples = [_r for _s in self.source.CATEGORIES
                    for _r in self.source.Bucket(_s).values()]
        if _samples and any(_r.Attr("source_obj") for _r in _samples):
            raise ValueError(
                f"{self.task or 'frame'} 내보내기는 프레임 단위 sample 이 필요하다 (이미지 1장 + 그 "
                "객체들). 이 tasker 는 객체 단위(source_obj)로 빌드됐다 — 레시피의 unit 을 'frame' 으로 두고 "
                "다시 Sample 하라. (unit='object' 는 crop 기반 classification 용이다.)")

    def _require_meta(self) -> None:
        """프레임 픽셀은 sample 이 아니라 정본에 있다 — meta 없으면 실패."""
        if self.meta is None:
            raise ValueError(f"{self.task or 'frame'} 내보내기는 정본(meta)이 필요하다 — 픽셀이 "
                             "sample 이 아니라 정본 프레임 leaf 에 있다")
