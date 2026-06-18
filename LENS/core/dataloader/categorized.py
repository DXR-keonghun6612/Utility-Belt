"""이미 분류된 폴더 구조에서 FrameMeta 스트림을 생성하는 Reader."""

from __future__ import annotations

from pathlib import Path

from ._base import Base_Reader, CATEGORIZE_FILE_LIST, Frame_Meta, ID_MAP
from . import reader_registry


@reader_registry.Register_module("categorized")
class Categorized_Reader(Base_Reader):
    """root/ 하위 폴더명 = class_name 구조에서 FrameMeta 스트림 생성.

    id_map_file 제공 시 파일에서 로드, 없으면 폴더명 정렬 순서로 자동 부여 (0, 1, 2 …).
    """

    def Load(self, root: Path) -> tuple[CATEGORIZE_FILE_LIST, ID_MAP]:
        class_dirs = sorted(d for d in root.iterdir() if d.is_dir())
        obj_id_map = self.id_map or {d.name: {"id": i} for i, d in enumerate(class_dirs)}

        categorization: dict[str, list[Frame_Meta]] = {}
        for class_dir in class_dirs:
            if frames := self.Scan(class_dir):
                categorization[class_dir.name] = frames

        return categorization, obj_id_map
