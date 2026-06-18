"""파일 탐색 유틸 + FrameMeta + Input Reader 추상 베이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from python_toolbox.data_schema import Data_Schema
from python_toolbox.project.config import Base_Config
from python_toolbox.file import Make_dict_from


FRAME_KEY        = "frame"
MASK_KEY         = "mask"
UNCLASSIFIED = "__unclassified__"
EXCLUDED_KEY     = "__excluded__"

ID_MAP = dict[str, dict[str, int]]  # {class_name: {id_type: id_num}}


@dataclass
class Frame_Meta(Data_Schema):
    """프레임 한 장에 대한 식별 정보.

    data_path 키는 Scanner_Config.globs 키와 대응.
    data_path 는 런타임 전용 — 직렬화 제외, 로드 후 Scan 으로 복원.
    class_name 은 categorization dict 키로 관리.
    필요 시 상속으로 필드 확장.
    """

    __exclude_serialize__: ClassVar[set[str]] = {"data_path"}

    stem:      str             = ""
    data_path: dict[str, Path] = field(default_factory=dict)


@dataclass
class Dataloader_config(Base_Config):
    """단일 데이터 그룹을 정의하는 reader 메타데이터.

    Attributes:
        object_type: reader 종류 키 ("raw" | "categorized").
        id_map_file: class → id 매핑 파일 경로.
        sources: 입력 세션 디렉터리 경로 목록.
        globs: reader 파일 패턴 ({glob_key: pattern}).
    """
    __unpack_extract__: ClassVar[set[str]] = {"globs"}
    __exclude_extract__: ClassVar[set[str]] = {"sources"}

    config_type: str = f"dataloader_config"
    object_type: str = "raw"

    id_map_file: str       = "ip_map.json"
    sources:     list[str] = field(default_factory=list)
    globs:       dict[str, str] = field(default_factory=lambda: {
        FRAME_KEY: "*_pose.png",
    })

CATEGORIZE_FILE_LIST = dict[str, list[Frame_Meta]]


class Base_Reader(ABC):
    """categorization + obj_id_map 을 생성하는 공통 인터페이스."""
    def __init__(self, id_map_file: str = "ip_map.json", **globs: str) -> None:
        if (_id_map_file := Path(id_map_file)).exists():
            _, _id_map = Make_dict_from(_id_map_file)
        else:
            _id_map = {}
        self.id_map = _id_map
        self.globs = globs

    def Scan(self, dir: Path) -> list[Frame_Meta]:
        _files: dict[str, dict[str, Path]] = {}  # {stem: {glob_key: Path}}
        for _k, _p in self.globs.items():
            _pre, _, _suf = _p.split(".")[0].partition("*")
            for _f in sorted(dir.glob(_p)):
                _pure_stem = _f.stem.removeprefix(_pre).removesuffix(_suf)
                _files.setdefault(_pure_stem, {})[_k] = _f

        _n = len(self.globs)
        return [
            Frame_Meta(
                _stem, _paths
            ) for _stem, _paths in _files.items() if len(_paths) == _n
        ]

    @abstractmethod
    def Load(self, root: Path) -> tuple[CATEGORIZE_FILE_LIST, ID_MAP]:
        """root 를 읽어 (categorization, obj_id_map) 반환."""
