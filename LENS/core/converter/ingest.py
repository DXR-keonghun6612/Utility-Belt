"""raw ingest — 외부 레이아웃의 흩어진 파일을 glob 로 묶어 정본 store 에 들인다.

**엔진을 쓰지 않는다.** Convert 는 process 체인이 비고(ctx 도 resolve 도 없다) 하는 일이
``scan(외부) → handler.Save → store.Set`` 뿐이라, 계산이 아니라 **store 진입 게이트**다 —
``Restore``(자기 레이아웃)·``Merge``(다른 store)·``Export``(내보내기)의 빠진 형제이고, ``Export`` 의
역함수다. 그래서 stage(source/sink)로 세우지 않고 자유함수 하나로 둔다.

(2단계에서 `core/port/` 로 이사한다 — 계획은 [`../TODO.md`](../TODO.md) "★ core 4분할".)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterator

from ..data import handler
from ..data.handler import Data_Ref


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


def _spec_ref(spec: dict | str) -> Data_Ref:
    """key 스펙(``{pattern, type?, format?}`` 또는 패턴 문자열)에서 LEAF ref 템플릿.

    ``type`` 미지정 시 패턴 확장자로 핸들러를 추론(``handler.Infer_type``); 추론 실패면 에러
    (인라인 type 은 명시). ``format``(=ext) 미지정이면 ``handler.Save`` 가 소스 파일 확장자로 채운다.

    **저장 위치는 스펙이 안 정한다** — 경로는 트리 위치(범주·stem)와 key 이름에서 handler 가 파생한다
    (kind-major: glob key 가 곧 종류 폴더).
    """
    if isinstance(spec, str):
        spec = {"pattern": spec}
    _type = spec.get("type")
    if _type is None:
        _ext = Path(spec["pattern"]).suffix
        _type = handler.Infer_type(_ext)
        if _type is None:
            raise ValueError(f"glob 패턴 '{spec['pattern']}': 확장자 '{_ext}' 로 type 추론 불가 "
                             f"— type 을 명시하세요")
    return Data_Ref(format=(_type, spec.get("format", "")))


def Scan(sources: list[str], globs: dict[str, Any]) -> dict[str, dict[str, Path]]:
    """``sources`` 를 glob 탐색해 ``{stem: {key: path}}`` 로 묶는다 (모든 key 매칭 = inner join).

    glob key 하나가 종류(leaf 이름) 하나에 대응한다 — 한 stem 이 선언된 key 를 다 갖출 때만 그룹이 선다.
    """
    _stem_map: dict[str, dict[str, Path]] = {}
    for _src in sources:
        _dir = Path(_src)
        for _name in globs:
            _pat = _pattern(globs[_name])
            for _file in sorted(_dir.glob(_pat)):
                _stem_map.setdefault(_extract_stem(_file.name, _pat), {})[_name] = _file
    _keys = set(globs)
    return {_s: _v for _s, _v in _stem_map.items() if _keys <= set(_v)}


def Ingest(store, sources: list[str], globs: dict[str, Any],
           params: dict[str, Any] | None = None,
           progress: Callable[[str, int, int], None] | None = None) -> int:
    """raw 를 발견해 payload 를 저장하고 stem 컨테이너를 store 의 진입 범주에 등록한다.

    **이미 있는 stem 은 건드리지 않는다** — 상태(범주)도 내용도 그대로 둔다. convert 는 raw 를 들이는
    ingest 라 이미 들인 것에 할 일이 없고, 내보내기가 범주 기반이므로 재수집이 검수 이력(staged/skipped)을
    덮어써서는 안 된다. 그래서 존재 검사가 payload write **앞**에 온다(파일도 안 쓴다).

    Args:
        store: 들일 store (``Dataset_Meta``) — 진입 범주는 ``DEFAULT_CATEGORY``.
        sources: 탐색할 raw 디렉터리들.
        globs: ``{종류: {pattern, type?, format?}}`` — key 가 곧 종류 폴더.
        params: 범주 무관 dataset-wide 파일 ``{종류: {pattern, …}}`` (stem 이 없다).
        progress: 진행 콜백 ``(label, i, total)``.

    Returns:
        새로 등록한 stem 수.
    """
    _groups = Scan(sources, globs)
    _total, _added = len(_groups), 0
    for _i, (_stem, _files) in enumerate(_groups.items(), start=1):
        if not store.Has(_stem):                              # 이미 들인 stem → 상태·내용 보존
            _path = (store.DEFAULT_CATEGORY, _stem)
            _info = {_name: handler.Save(store.root, _path, _name, _spec_ref(globs[_name]), _src)
                     for _name, _src in _files.items()}
            store.Set(_stem, Data_Ref(info=_info))
            _added += 1
        if progress is not None:
            progress("convert", _i, _total)

    for _name, _spec in (params or {}).items():               # dataset-wide root leaf
        _src = Path(_pattern(_spec))
        if _src.exists():
            store.Set_param(_name, handler.Save(
                store.root, (store.PARAMS,), _name, _spec_ref(_spec), _src))
    return _added
