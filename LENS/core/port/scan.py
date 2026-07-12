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
    """key 스펙에서 **패턴 문자열 그대로** 꺼낸다 (확장자 결합 없음 — params 의 단일 경로에도 쓴다)."""
    return spec if isinstance(spec, str) else spec["pattern"]


def Glob_of(spec: dict | str) -> str:
    """key 스펙 → **실제로 glob 할 패턴**. ``pattern`` + ``ext`` 를 합친다.

    ``ext`` 는 **소스 파일의 확장자**다 — 파일을 *찾는* 데 쓰인다. 서술자의 ``format``(image=저장 ext,
    attr=값 타입 detail)과는 **다른 것**이라 필드를 가른다: 같은 칸에 두면 "확장자는 여기 적는 것"으로
    읽혀 패턴이 아무것도 못 찾는다(실제로 그렇게 조용히 0건이 났다).

    ``ext`` 없이 패턴에 확장자를 쓴 형태(``*_pose.png``)도 그대로 받는다.

    Raises:
        ValueError: 패턴에 이미 확장자가 있는데 ``ext`` 까지 준 경우 (어느 쪽이 맞는지 모호하다).
    """
    if isinstance(spec, str):
        return spec
    _pattern = spec["pattern"]
    _ext = str(spec.get("ext", "")).lstrip(".")
    if not _ext:
        return _pattern
    if Path(_pattern).suffix:
        raise ValueError(
            f"glob '{_pattern}' 에 이미 확장자가 있는데 ext='{_ext}' 도 주어졌다 — 둘 중 하나만 쓰세요 "
            f"(패턴에 넣거나, 패턴은 stem 만 두고 ext 로 주거나).")
    return f"{_pattern}.{_ext}"



def Scan(sources: list[str], globs: dict[str, Any]) -> dict[str, dict[str, Path]]:
    """``sources`` 를 glob 탐색해 ``{stem: {종류: 경로}}`` 로 묶는다.

    glob key 하나가 종류(leaf 이름) 하나다. **모든 key 를 갖춘 stem 만** 그룹이 된다(inner join) —
    한 종류가 빠진 프레임은 반쪽짜리라 들이지 않는다.

    **아무것도 못 찾으면 조용히 빈 결과를 주지 않고 실패한다.** 예전엔 패턴이 틀려 0건이어도 아무 말 없이
    빈 목록이 떴다(무엇이 잘못됐는지 알 길이 없었다). 어느 종류가 몇 개 잡혔는지 함께 알린다.

    Args:
        sources: 탐색할 raw 디렉터리들.
        globs: ``{종류: {pattern, ext?, …}}`` (또는 패턴 문자열).

    Raises:
        ValueError: 소스·glob 이 비었거나 · 어떤 종류가 **한 파일도** 못 찾았거나 ·
            모든 종류를 갖춘 stem 이 하나도 없을 때 (키별 매칭 수를 함께 알린다).
    """
    if not sources:
        raise ValueError("raw 소스 디렉터리가 없습니다 — 탐색할 곳을 지정하세요.")
    if not globs:
        raise ValueError("glob 이 하나도 없습니다 — 무엇을 들일지(종류·패턴) 지정하세요.")

    _stem_map: dict[str, dict[str, Path]] = {}
    _hits: dict[str, int] = {}
    for _name, _spec in globs.items():
        _pat = Glob_of(_spec)
        _found = [_f for _src in sources for _f in sorted(Path(_src).glob(_pat))]
        _hits[_name] = len(_found)
        for _file in _found:
            _stem_map.setdefault(_extract_stem(_file.name, _pat), {})[_name] = _file

    _report = ", ".join(f"{_k}({Glob_of(globs[_k])})={_v}개" for _k, _v in _hits.items())
    _empty = [_k for _k, _v in _hits.items() if _v == 0]
    if _empty:
        raise ValueError(
            f"glob 이 한 파일도 찾지 못했습니다: {', '.join(_empty)} — 패턴·확장자를 확인하세요. "
            f"(매칭: {_report} / 소스: {', '.join(map(str, sources))})")

    _keys = set(globs)
    _groups = {_s: _v for _s, _v in _stem_map.items() if _keys <= set(_v)}
    if not _groups:
        raise ValueError(
            f"모든 종류를 갖춘 stem 이 없습니다 — 종류마다 파일은 찾았지만 **같은 stem 을 공유하지 않습니다**. "
            f"패턴의 `*` 자리가 같은 이름을 가리키는지 확인하세요. (매칭: {_report})")
    return _groups
