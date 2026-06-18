"""원시 세션 데이터에서 라벨을 파싱해 FrameMeta 스트림을 생성하는 Reader."""

from __future__ import annotations

from pathlib import Path

from ._base import (
    Base_Reader, Frame_Meta, CATEGORIZE_FILE_LIST, ID_MAP, UNCLASSIFIED,
)
from . import reader_registry


@reader_registry.Register_module("raw")
class Raw_Reader(Base_Reader):
    """세션 디렉토리에서 라벨 파싱 → FrameMeta 스트림 생성."""
    def Load(self, root: Path) -> tuple[CATEGORIZE_FILE_LIST, ID_MAP]:
        if not self.id_map:
            return {}, {}

        _by_cat: dict[str, list[Frame_Meta]] = {}
        for meta in self.Scan(root):
            try:
                label = meta.data_path["label"].read_text().strip()
            except Exception:
                label = ""
            class_name = label if label in self.id_map else UNCLASSIFIED
            _by_cat.setdefault(class_name, []).append(meta)

        _obj_id_map = {
            _n: self.id_map[_n] for _n in _by_cat if _n != UNCLASSIFIED
        }
        return _by_cat, _obj_id_map