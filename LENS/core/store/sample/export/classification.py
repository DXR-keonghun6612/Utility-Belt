"""classification — ImageFolder 레이아웃 (class-major)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from python_toolbox.file import Write_to

from .... import port
from ._base import Exporter


@dataclass
class ImageFolder_exporter(Exporter):
    """``{dest}/{split}/{class}/{sample}.png`` + ``id_map.json``.

    torchvision ``ImageFolder``·Keras ``image_dataset_from_directory`` 가 그대로 먹는 모양.
    class 는 sample 의 ``class_id`` attr 에서 읽어 **여기서 폴더로 실체화**한다(store 에선 attr) —
    그래서 재분류가 store 에선 파일을 안 건드리고, 폴더 모양은 내보낼 때만 생긴다.

    crop 이 실체화된 sample 만 픽셀이 나온다 — 레시피에 crop 체인이 필요하다.

    **class 는 옵셔널** — ``class_id`` attr 이 없으면(class-agnostic) class 폴더 없이 ``{split}/{sid}.png``
    로 평탄하게 낸다. class 를 안 쓰는 데이터면 학습 측도 안 쓰는 게 맞다 — 폴더를 지어내지 않는다.
    """

    def Export(self, dest: str | Path) -> None:
        _out = Path(dest)
        _classes: set[str] = set()
        for _split in self.source.CATEGORIES:
            for _sid, _ref in self.source.Bucket(_split).items():
                _class = _ref.Attr("class_id") or None   # 없으면 class-agnostic (폴더 없이 평탄)
                if _class is not None:
                    _classes.add(_class)
                _crop = _ref.Get("crop")
                if _crop is None:                        # 순수 역참조만 — 복사할 픽셀이 없다
                    continue
                _src = port.Path_of(self.source.root, (_split, _sid), "crop", _crop)
                if _src is None:
                    continue
                _dir = _out / _split / _class if _class is not None else _out / _split
                self._copy(_src, _dir / f"{_sid}{_src.suffix}")
        if _classes:                                     # class-agnostic 이면 id_map 자체가 없다
            Write_to(_out / "id_map.json", self._resolve_id_map(_classes))
