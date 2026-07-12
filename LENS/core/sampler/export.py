"""내보내기 — 파생 store(``Sample_Set``)를 **학습 프레임워크 레이아웃**으로 실체화한다.

**task 가 사는 곳은 여기다.** 빌드(sink)는 무엇을 뽑을지만 정하고 task 를 모른다 — classification 이냐
detection 이냐는 *같은 데이터를 어떤 폴더 모양으로 내놓느냐*의 문제이고, 그 축이 서로 배타적이라 store
구조로는 둘 다 못 섬긴다:

- **ImageFolder** (classification) — ``{split}/{class}/{sample}.png``. **class-major**: 폴더명이 곧 라벨.
- **COCO** (detection) — ``{split}/images/{stem}.png`` + ``{split}/instances_{split}.json``. **kind-major**:
  픽셀과 annotation 이 갈리고 class 는 json 안 정수.

그래서 store 는 축을 하나만(kind-major) 고르고, 학습셋 관행은 여기서 옮겨 짓는다. 원본(작업 store)은
비파괴 — payload 는 ``handler.Path_of`` 로 원본 파일을 찾아 복사한다(디코드·재인코딩 없음).

split 은 **재배정하지 않는다** — store 가 이미 split 범주로 갈려 있다(빌드가 배정). 여기선 순회할 뿐이다.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from python_toolbox.file import Write_to

from ..constant import STAGED
from ..data import handler
from ..data.handler import Data_Ref
from ..data.meta import Dataset_Meta
from ..data.sample import Sample_Set
from .stage import UNLABELED


@dataclass
class Exporter(ABC):
    """파생 store → 학습셋 레이아웃 (task 별 서브클래스).

    Attributes:
        source: 파생 store — 내보낼 sample 들 (split 범주로 이미 갈려 있다).
        meta:   정본 store — sample 이 A+ 역참조라 픽셀이 여기 있을 수 있다(detection 의 프레임 이미지).
        id_map: class→정수 매핑. 주어지면(정본 params 유래) 그대로, None 이면 class 정렬로 생성.
    """

    source: Sample_Set
    meta:   Dataset_Meta | None    = None
    id_map: dict[str, int] | None  = None

    @abstractmethod
    def Export(self, dest: str | Path) -> None:
        """``dest`` 아래에 이 task 의 레이아웃으로 실체화한다."""

    # ── 공통 ──────────────────────────────────────────────────────────────────
    def _resolve_id_map(self, classes) -> dict[str, int]:
        """class→정수 확정 — 주어지면 그대로, 없으면 class 정렬로 1부터."""
        return (dict(self.id_map) if self.id_map else
                {_c: _i for _i, _c in enumerate(sorted(classes), start=1)})

    @staticmethod
    def _copy(src: Path | None, dst: Path) -> bool:
        """원본 파일 → dst 로 복사 (없으면 False). 부모 dir 보장."""
        if src is None or not src.exists():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True


@dataclass
class ImageFolder_exporter(Exporter):
    """classification — ``{dest}/{split}/{class}/{sample}.png`` + ``id_map.json``.

    torchvision ``ImageFolder``·Keras ``image_dataset_from_directory`` 가 그대로 먹는 모양. class 는
    sample 의 ``class_id`` attr 에서 읽어 **여기서 폴더로 실체화**한다(store 에선 attr). crop 이 실체화된
    sample 만 픽셀이 나온다 — 레시피에 crop 체인이 필요하다.
    """

    def Export(self, dest: str | Path) -> None:
        _out = Path(dest)
        _classes: set[str] = set()
        for _split in self.source.CATEGORIES:
            for _sid, _ref in self.source.Bucket(_split).items():
                _class = _ref.Attr("class_id") or UNLABELED
                _classes.add(_class)
                _crop = _ref.Get("crop")
                if _crop is None:                     # A+ 역참조만 — 복사할 픽셀이 없다
                    continue
                _src = handler.Path_of(self.source.root, (_split, _sid), "crop", _crop)
                if _src is None:
                    continue
                self._copy(_src, _out / _split / _class / f"{_sid}{_src.suffix}")
        Write_to(_out / "id_map.json", self._resolve_id_map(_classes))


@dataclass
class Coco_exporter(Exporter):
    """detection — ``{dest}/{split}/images/{stem}.{ext}`` + ``{split}/instances_{split}.json``.

    COCO 는 **원본 이미지 + annotation** 이다 — 객체별로 잘라낸 png 가 아니다. 그래서 픽셀은 sample 이
    아니라 **정본**(``meta``)의 프레임 leaf 에서 가져오고(A+ 역참조), 객체 정보(bbox·class)는 sample 아래
    객체 컨테이너의 attr 에서 읽어 annotation 으로 낸다.

    Attributes:
        image_key: 정본에서 프레임 이미지를 담은 leaf 이름 (converter 의 glob key — 기본 ``frame``).
    """

    image_key: str = "frame"

    def Export(self, dest: str | Path) -> None:
        if self.meta is None:
            raise ValueError("COCO 내보내기는 정본(meta)이 필요하다 — 픽셀이 sample 이 아니라 정본에 있다")
        self._require_frame_samples()
        _out = Path(dest)
        _classes = {_o.Attr("class_id")
                    for _split in self.source.CATEGORIES
                    for _ref in self.source.Bucket(_split).values()
                    for _o in _ref.Branches().values() if _o.Attr("class_id")}
        _ids = self._resolve_id_map(_classes)

        for _split in self.source.CATEGORIES:
            _images: list[dict] = []
            _anns:   list[dict] = []
            for _iid, (_sid, _ref) in enumerate(sorted(self.source.Bucket(_split).items()), start=1):
                _stem = _ref.Attr("source_stem") or _sid
                _file = self._copy_frame(_stem, _out / _split / "images")
                _images.append({"id": _iid, "file_name": _file or f"{_stem}.png"})
                for _oid, _obj in _ref.Branches().items():
                    _anns.append({
                        "id":          len(_anns) + 1,
                        "image_id":    _iid,
                        "category_id": _ids.get(_obj.Attr("class_id"), 0),
                        "bbox":        self._coco_bbox(_obj),
                        "source_obj":  _oid,
                    })
            Write_to(_out / _split / f"instances_{_split}.json", {
                "images":      _images,
                "annotations": _anns,
                "categories":  [{"id": _i, "name": _n} for _n, _i in _ids.items()],
            })
        Write_to(_out / "id_map.json", _ids)

    @staticmethod
    def _coco_bbox(obj: Data_Ref) -> list[float]:
        """객체의 bbox attr → COCO 규약 ``[x, y, w, h]`` (없으면 ``[]``).

        정본은 코너 ``xyxy`` 로 든다(``format=("attr","xyxy")``) — COCO 는 **좌상단+폭높이**라 여기서
        변환한다. 산출물 규약을 정본 규약에 맞추면 학습 측이 조용히 틀린 박스를 먹는다.
        """
        _box = obj.Get("bbox")
        if _box is None:
            return []
        _v = _box.info.get("value") or []
        if _box.format[1:] != ("xyxy",) or len(_v) != 4:
            raise ValueError(f"COCO 내보내기: bbox 가 xyxy 4-값이 아니다 — format={_box.format} value={_v}")
        _x0, _y0, _x1, _y1 = (float(_c) for _c in _v)
        return [_x0, _y0, _x1 - _x0, _y1 - _y0]

    def _require_frame_samples(self) -> None:
        """sample 이 **프레임 단위**(객체를 자식으로 낀 것)인지 확인 — 아니면 실패.

        빌드의 ``unit`` 이 어떤 내보내기가 가능한지를 정한다: COCO 는 *이미지 하나 + 그 안의 객체들*이라
        ``unit=frame`` 으로 빌드해야 한다. ``unit=object`` 로 빌드하면 sample 이 객체라 이미지가 객체 수만큼
        중복되고 annotation 이 빈다 — 조용히 빈 manifest 를 내지 않고 여기서 막는다.
        """
        _samples = [_r for _s in self.source.CATEGORIES
                    for _r in self.source.Bucket(_s).values()]
        if _samples and not any(_r.Branches() for _r in _samples):
            raise ValueError(
                "COCO 내보내기는 프레임 단위 sample 이 필요하다 (이미지 1장 + 그 객체들). 이 tasker 는 "
                "객체 단위로 빌드돼 sample 에 객체 자식이 없다 — 레시피의 unit 을 'frame' 으로 두고 "
                "다시 Sample 하라. (unit='object' 는 crop 기반 classification 용이다.)")

    def _copy_frame(self, stem: str, dst_dir: Path) -> str | None:
        """정본 staged 프레임 이미지를 ``dst_dir`` 로 복사한다 (파일명 반환; 없으면 None)."""
        _item = self.meta.Find(stem)
        if _item is None:
            return None
        _leaf = _item.Get(self.image_key)
        if _leaf is None:
            return None
        _src = handler.Path_of(self.meta.root, (STAGED, stem), self.image_key, _leaf)
        if _src is None or not _src.exists():
            return None
        _name = f"{stem}{_src.suffix}"
        self._copy(_src, dst_dir / _name)
        return _name


# config task → exporter (Pipeline.Export_tasker 가 소비). 새 포맷(YOLO 등)은 여기 한 줄.
EXPORTERS: dict[str, type[Exporter]] = {
    "classification": ImageFolder_exporter,
    "detection":      Coco_exporter,
}
