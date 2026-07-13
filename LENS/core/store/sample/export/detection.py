"""detection — COCO 레이아웃 (원본 이미지 + annotation)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from python_toolbox.file import Write_to

from .... import port
from ....constant import STAGED
from ....schema import Data_Ref
from ._base import Exporter


@dataclass
class Coco_exporter(Exporter):
    """``{dest}/{split}/images/{stem}.{ext}`` + ``{split}/instances_{split}.json``.

    COCO 는 **원본 이미지 + annotation** 이다 — 객체별로 잘라낸 png 가 아니다. 그래서 픽셀은 sample 이
    아니라 **정본**(``meta``)의 프레임 leaf 에서 가져오고(순수 역참조), 객체 정보(bbox·class)는 sample
    아래 객체 컨테이너의 attr 에서 읽어 annotation 으로 낸다.

    Attributes:
        image_key: 정본에서 프레임 이미지를 담은 leaf 이름 (ingest 의 glob key — 기본 ``frame``).
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
        """객체의 bbox → COCO 규약 ``[x, y, w, h]`` (없으면 ``[]``).

        정본은 코너 ``xyxy`` 로 든다(``format=("bbox","list")`` — ``bbox`` 개념이 "int 4개 = 코너"를
        말한다). COCO 는 **좌상단+폭높이**라 여기서 변환한다. 산출물 규약을 정본 규약에 맞추면 학습
        측이 조용히 틀린 박스를 먹는다.
        """
        _box = obj.Get("bbox")
        if _box is None:
            return []
        _v = _box.info.get("value") or []
        if _box.format[:1] != ("bbox",) or len(_v) != 4:
            raise ValueError(f"COCO 내보내기: bbox 가 4-값 코너가 아니다 — format={_box.format} value={_v}")
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
        _src = port.Path_of(self.meta.root, (STAGED, stem), self.image_key, _leaf)
        if _src is None or not _src.exists():
            return None
        _name = f"{stem}{_src.suffix}"
        self._copy(_src, dst_dir / _name)
        return _name
