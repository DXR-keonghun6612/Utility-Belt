"""glob 패턴으로 폴더의 흩어진 파일을 묶어 컨테이너 ``Data_Ref``(type="stem") 를 만드는 discover converter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from python_toolbox.file import Read_from

from ....data import handler
from ...handler import Data_Ref
from .._base import Base_Converter


def _extract_stem(filename: str, pattern: str) -> str:
    """glob 패턴에서 ``*`` 위치의 variable part 를 추출한다.

    예) ``mask_*.png`` + ``mask_001.png`` → ``001`` / ``*_pose.png`` + ``001_pose.png`` → ``001``
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


@dataclass
class Glob_Discover(Base_Converter):
    """glob 패턴 기반 stem 그룹핑 converter.

    Example::

        sources: [/data/raw]
        globs:
          frame:    {pattern: "*_pose.png"}                # type 생략 → 확장자로 추론(png→image)
          class_id: {pattern: "*_pose.txt", type: attr}    # 확장자 추론 안 됨 → type 명시
        params:
          roi: {pattern: /path/roi.png}                    # dir 생략 → params
        id_map: /path/id_map.yaml
    """

    sources: list[str]      = field(default_factory=list)
    globs:   dict[str, dict[str, Any]] = field(default_factory=dict)
    params:  dict[str, dict[str, Any]] = field(default_factory=dict)
    id_map:  str | None     = None

    def Convert(self, stem_root, params_root):
        _frames = [
            (
                _stem, self._Frame(stem_root, _stem, _paths)
            ) for _stem, _paths in self._Scan().items()
        ]
        return _frames, self._Params(params_root)

    def Load_id_map(self):
        if not self.id_map:
            return {}
        _ok, _d = Read_from(Path(self.id_map))
        return _d if _ok and isinstance(_d, dict) else {}

    # ── 내부 ──────────────────────────────────────────────────────────────────
    def _Frame(self, root: str, stem: str, paths: dict[str, Path]) -> Data_Ref:
        """glob 매칭된 파일들을 저장하고 한 프레임 컨테이너(``type="stem"``)로 묶는다."""
        _info = {
            _name: handler.Save(root, stem, _name, self._Ref(self.globs[_name], None), _src)
            for _name, _src in paths.items()
        }
        return Data_Ref(type="stem", info=_info)

    def _Params(self, root: str) -> dict[str, Data_Ref]:
        return {
            _name: handler.Save(root, None, _name, self._Ref(_spec, "params"),
                                Path(self._Pattern(_spec)))
            for _name, _spec in self.params.items()
        }

    @staticmethod
    def _Pattern(spec: dict | str) -> str:
        return spec if isinstance(spec, str) else spec["pattern"]

    @staticmethod
    def _Ref(spec: dict | str, default_dir: str | None) -> Data_Ref:
        """key 스펙(`{pattern, type?, dir?, format?}` 또는 패턴 문자열)에서 ref 템플릿.

        ``type`` 미지정 시 패턴의 확장자로 핸들러를 추론한다(``handler.Infer_type``).
        추론 실패면 에러 — 조용한 기본값을 두지 않는다(인라인 type 은 명시해야 함).
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
                raise ValueError(
                    f"glob 패턴 '{spec['pattern']}': 확장자 '{_ext}' 로 type 추론 불가 "
                    f"— type 을 명시하세요")
        return Data_Ref(
            type=_type,
            format=spec.get("format", ""),
            info=_info
        )

    def _Scan(self) -> dict[str, dict[str, Path]]:
        """sources 를 glob 탐색해 ``{stem: {name: path}}`` (모든 key 매칭 = inner join)."""
        _stem_map: dict[str, dict[str, Path]] = {}
        for _src in self.sources:
            _dir = Path(_src)
            for _name in self.globs:
                _pat = self._Pattern(self.globs[_name])
                for _file in sorted(_dir.glob(_pat)):
                    _stem_map.setdefault(_extract_stem(_file.name, _pat), {})[_name] = _file
        _keys = set(self.globs)
        return {_s: _v for _s, _v in _stem_map.items() if _keys <= set(_v)}
