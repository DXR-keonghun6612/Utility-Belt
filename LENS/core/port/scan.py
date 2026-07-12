"""외부 fs 발견 — 흩어진 raw 파일을 glob 로 묶어 stem 그룹으로 찾는다.

**pathlib 만 안다.** port 안의 어떤 것도 import 하지 않는다 — handler 도, registry 도, ``Data_Ref`` 도.
그래야 ``__init__`` 의 자동등록 순회가 이 모듈을 집어와도 순환이 나지 않는다.

발견(어떤 파일이 있나)과 등록(어느 범주에 어떻게 넣나)은 다른 일이다. 여기는 **발견만** 한다 —
등록은 ``store.Import`` 가 이 결과를 받아서 한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


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


def Pattern_of(spec: dict | str) -> str:
    """key 스펙(``{pattern, …}`` 또는 패턴 문자열)에서 glob 패턴만 꺼낸다."""
    return spec if isinstance(spec, str) else spec["pattern"]


def Scan(sources: list[str], globs: dict[str, Any]) -> dict[str, dict[str, Path]]:
    """``sources`` 를 glob 탐색해 ``{stem: {종류: 경로}}`` 로 묶는다.

    glob key 하나가 종류(leaf 이름) 하나다. **모든 key 를 갖춘 stem 만** 그룹이 된다(inner join) —
    한 종류가 빠진 프레임은 반쪽짜리라 들이지 않는다.

    Args:
        sources: 탐색할 raw 디렉터리들.
        globs: ``{종류: {pattern, …}}`` (또는 패턴 문자열).
    """
    _stem_map: dict[str, dict[str, Path]] = {}
    for _src in sources:
        _dir = Path(_src)
        for _name in globs:
            _pat = Pattern_of(globs[_name])
            for _file in sorted(_dir.glob(_pat)):
                _stem_map.setdefault(_extract_stem(_file.name, _pat), {})[_name] = _file
    _keys = set(globs)
    return {_s: _v for _s, _v in _stem_map.items() if _keys <= set(_v)}
