"""Convert source — 폴더의 흩어진 raw 파일을 glob 로 묶어 stem 그룹으로 발견한다.

``process`` 의 Stage 입력 계약(``Base_Source``/``Frame``/``Unit``)을 구현한다 — Run 의 ``Frame_source`` 가
정본을 순회하듯, ``Raw_source`` 는 raw 를 발견한다. 실제 저장은 sink([`sink.py`](sink.py) ``Register_sink``)가
handler 로 하고, source 는 발견·ref 템플릿만 정한다(정해진 포맷 파서 coco/yolo 는 다른 Source 로 추가).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from ..data import handler
from ..data.handler import Data_Ref
from ..process.source import Base_Source, Frame, Unit


def _extract_stem(filename: str, pattern: str) -> str:
    """glob 패턴에서 ``*`` 위치의 variable part 를 추출한다.

    예) ``mask_*.png`` + ``mask_001.png`` → ``001`` / ``*_pose.png`` + ``001_pose.png`` → ``001``.
    """
    if "*" not in pattern:
        return Path(filename).stem
    _star = pattern.index("*")
    _prefix, _suffix = pattern[:_star], pattern[_star + 1:]
    _name = filename
    if _prefix and _name.startswith(_prefix):
        _name = _name[len(_prefix):]
    if _suffix and _name.endswith(_suffix):
        _name = _name[: -len(_suffix)]
    return _name


def _pattern(spec: dict | str) -> str:
    return spec if isinstance(spec, str) else spec["pattern"]


def _spec_ref(spec: dict | str, default_dir: str | None) -> Data_Ref:
    """key 스펙(``{pattern, type?, dir?, format?}`` 또는 패턴 문자열)에서 ref 템플릿.

    ``type`` 미지정 시 패턴 확장자로 핸들러를 추론(``handler.Infer_type``); 추론 실패면 에러
    (인라인 type 은 명시). ``dir`` 미지정 시 ``default_dir``(frame=None → name / params="params").
    """
    if isinstance(spec, str):
        spec = {"pattern": spec}
    _info: dict[str, Any] = {}
    _dir = spec.get("dir", default_dir)
    if _dir is not None:
        _info["dir"] = _dir
    _type = spec.get("type")
    if _type is None:
        _ext = Path(spec["pattern"]).suffix
        _type = handler.Infer_type(_ext)
        if _type is None:
            raise ValueError(f"glob 패턴 '{spec['pattern']}': 확장자 '{_ext}' 로 type 추론 불가 "
                             f"— type 을 명시하세요")
    return Data_Ref(type=_type, format=spec.get("format", ""), info=_info)


@dataclass
class Raw_frame(Frame):
    """발견된 raw 그룹 하나 — 파일 경로 + ref 템플릿을 unit 으로 낸다 (resolve 없음).

    ``target`` = 이 그룹이 향할 곳(``frame`` = modified 버킷 stem / ``params`` = dataset-wide root leaf) —
    sink(``Register_sink``)가 이 정보로 저장 위치를 가른다.
    """

    stem:   str
    files:  dict[str, Path]
    specs:  dict[str, Data_Ref]
    target: str = "frame"

    def context(self, store, params_ctx: dict) -> dict:
        return {}

    def units(self, store, fctx: dict) -> Iterator[Unit]:
        yield Unit(stem=self.stem, ctx=dict(self.files),
                   extra={"specs": self.specs, "target": self.target})


@dataclass
class Raw_source(Base_Source):
    """glob 발견 converter source. 각 glob key(``globs``)는 ``{pattern, type?, dir?, format?}``.

    발견된 그룹은 ``Raw_frame``(target="frame"), ``params`` 는 stem 무관 dataset-wide 파일(target="params").
    ``type`` 생략 시 패턴 확장자로 핸들러 추론(png→image), 추론 안 되는 확장자(txt 등)는 명시.
    """

    sources: list[str]                 = field(default_factory=list)
    globs:   dict[str, dict[str, Any]] = field(default_factory=dict)
    params:  dict[str, dict[str, Any]] = field(default_factory=dict)

    def prelude(self, store) -> dict:
        return {}

    def frames(self, store) -> Iterator[Raw_frame]:
        for _stem, _files in self._scan().items():
            _specs = {_n: _spec_ref(self.globs[_n], None) for _n in _files}
            yield Raw_frame(_stem, _files, _specs, target="frame")
        if self.params:                                    # dataset-wide 파일 (한 그룹)
            _pfiles = {_n: Path(_pattern(_s)) for _n, _s in self.params.items()}
            _pspecs = {_n: _spec_ref(_s, "params") for _n, _s in self.params.items()}
            yield Raw_frame("__params__", _pfiles, _pspecs, target="params")

    def count(self, store) -> int:
        return len(self._scan())

    def _scan(self) -> dict[str, dict[str, Path]]:
        """sources 를 glob 탐색해 ``{stem: {name: path}}`` (모든 key 매칭 = inner join)."""
        _stem_map: dict[str, dict[str, Path]] = {}
        for _src in self.sources:
            _dir = Path(_src)
            for _name in self.globs:
                _pat = _pattern(self.globs[_name])
                for _file in sorted(_dir.glob(_pat)):
                    _stem_map.setdefault(_extract_stem(_file.name, _pat), {})[_name] = _file
        _keys = set(self.globs)
        return {_s: _v for _s, _v in _stem_map.items() if _keys <= set(_v)}
