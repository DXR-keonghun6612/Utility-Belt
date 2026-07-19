"""계층 경계 검사 — 산문이 아니라 **실행되는 규칙**으로 못박는다.

`core` 는 **아는 타입**으로 계층이 갈린다. 경계를 README 문단으로만 두면 조용히 무너지므로, import 방향을
여기서 검사한다. 아래 `LAYER` dict 가 그 번호의 **단일 진실원천**이고, 이 다이어그램은 그 지도다. 이
파일이 통과하는 한 계층은 살아 있다.

```text
schema·typing·constant  횡단 primitive (Data_Ref 등)         (의존 0 · cv2-free)
func     배열↔배열 순수 계산 (cv·chroma·mask)               (core 를 아무것도 모른다 — numpy·cv2 뿐)
format   데이터 구조 + 그 연산 (bbox·polygon·rle)           (Data_Ref 도 I/O 도 모른다)
  ↑
codec    포맷 단위 직렬화 (raster·npy·inline·docs)          (구조를 디스크·사이드카에 싣는다)
  ↑
port     domain — 무엇으로 읽나 + 검증·정책 + 디스패치 + scan (디스크·포맷만 안다 — store 를 모른다)
  ↑
store    Bucket_Store · Dataset_Meta · Sample_Set          (범주·item 주소 + 라이프사이클)
  ↑
process  engine(Stage) · stream                            (계산의 흐름)
  ↑
binder   Pipeline · export                                 (셋을 잇는다)
```

**`func` 가 `process` 밑에 있지 않은 이유** — 소속은 출처가 아니라 **아는 타입**으로 정한다. `func` 는
core 에서 아무것도 import 하지 않고(numpy·cv2 뿐), 정작 당기는 쪽은 gui(3곳)·export·process 다. `process`
밑에 두면 "process·gui·binder 가 자유롭게 부른다"는 결정이 계층상 거짓이 된다 — 실제로 `port` 는 func 을
**docstring 으로만 가리킬** 수 있었다(역방향이라 import 불가). 올라오니 그 기형이 풀린다.

**왜 이 검사가 있나.** 예전엔 `Bucket_Store` 가 cv2-free 인 척하려고 `port` 를 함수 본문 안에서 지연
import 했고, 그 위장의 어색함이 *"라이프사이클이 store 에 있으면 안 되나 보다"* 라는 오진을 낳아 같은
경계를 두 바퀴 돌았다. 순수해야 하는 건 `schema` 한 모듈이지 계층 전체가 아니다 — 그걸 밖으로 꺼낸 뒤로
`store → port` 는 떳떳한 top-level import 다. 이 검사는 그 결론을 고정한다.

실행: ``pytest core/test_layering.py`` 또는 ``python core/test_layering.py``.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parent

# 계층 번호 — 위 계층은 아래를 알아도 되고, 아래는 위를 몰라야 한다.
LAYER: dict[str, int] = {
    "schema": 0, "typing": 0, "constant": 0,   # 횡단 primitive (의존 0)
    "func":    0,                              # 순수 계산 — core 를 모른다 (numpy·cv2 뿐). 누구나 부른다.
    "format":  0,                              # 데이터 구조 + 그 연산 — Data_Ref 도 I/O 도 모른다.
    "codec":   1,                              # 직렬화 — 구조를 디스크·사이드카에 싣고 내린다.
    "port":    2,                              # domain — 무엇으로 읽나 + 검증·정책 + 디스패치.
    "store":   3,
    "process": 4,
    "_base":   5, "tasker": 5, "__init__": 5, "export": 5,  # binder (export = read+compute+external-write)
}


def _layer_of(rel: Path) -> tuple[str, int] | None:
    """core 상대경로 → (계층명, 번호). 검사 대상이 아니면 None."""
    _top = rel.parts[0]
    _name = _top[:-3] if _top.endswith(".py") else _top
    if _name in ("test_layering", "__pycache__"):
        return None
    _lv = LAYER.get(_name)
    return (_name, _lv) if _lv is not None else None


def _imported_core_modules(path: Path, rel: Path) -> set[str]:
    """이 파일이 당기는 **core 내부** 최상위 계층 이름들 (절대·상대 import 모두)."""
    _tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    _pkg = rel.parts[:-1]                       # 이 모듈이 사는 패키지 경로 (core 기준)
    _out: set[str] = set()
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            for _a in _n.names:
                if _a.name.startswith("core."):
                    _out.add(_a.name.split(".")[1])
        elif isinstance(_n, ast.ImportFrom):
            if _n.level == 0:                   # 절대 — core.X…
                if _n.module and _n.module.startswith("core."):
                    _out.add(_n.module.split(".")[1])
                continue
            _base = _pkg[: len(_pkg) - (_n.level - 1)]     # 상대 — level 만큼 올라간다
            _parts = list(_base) + ((_n.module or "").split(".") if _n.module else [])
            if _parts:
                _out.add(_parts[0])
            else:                               # `from .. import X` — X 가 형제 모듈/패키지
                _out.update(_a.name for _a in _n.names)
    return _out


def check_import_direction() -> list[str]:
    """아래 계층이 위 계층을 import 하면 위반. 위반 목록을 돌려준다."""
    _bad: list[str] = []
    for _path in sorted(CORE.rglob("*.py")):
        _rel = _path.relative_to(CORE)
        if "__pycache__" in _rel.parts:
            continue
        _self = _layer_of(_rel)
        if _self is None:
            continue
        _sname, _slv = _self
        for _dep in _imported_core_modules(_path, _rel):
            _dlv = LAYER.get(_dep)
            if _dlv is None or _dep == _sname:
                continue
            if _dlv > _slv:                     # 위 계층을 당겼다 (같은 계층끼리는 허용)
                _bad.append(f"{_rel.as_posix()}  ({_sname}:{_slv})  →  {_dep}:{_dlv}")
    return _bad


def check_port_consumer() -> list[str]:
    """``port`` 의 소비자는 ``store`` 하나여야 한다 — 그게 "port 는 가장 독립적"의 실체다.

    읽기/쓰기는 store 가 소유하고 위 계층은 **요청**한다(``store.Resolve``/``store.Route``). process 가
    ``port`` 를 직접 부르면 계산 계층이 파일 포맷·경로 파생을 아는 셈이라 그 선을 넘은 것이다.
    """
    _bad: list[str] = []
    for _path in sorted(CORE.rglob("*.py")):
        _rel = _path.relative_to(CORE)
        if "__pycache__" in _rel.parts or _rel.parts[0] in ("port", "store", "test_layering.py"):
            continue
        if "port" in _imported_core_modules(_path, _rel):
            _bad.append(f"{_rel.as_posix()} 이 port 를 직접 당긴다 — store 에 요청해야 한다")
    return _bad


def check_schema_is_pure() -> list[str]:
    """``core.schema`` 만 들였을 때 무거운 의존(cv2·numpy…)이 안 딸려와야 한다 (진짜 cv2-free)."""
    _code = (
        "import sys; import core.schema; "
        "heavy = [m for m in ('cv2', 'numpy', 'matplotlib', 'torch') if m in sys.modules]; "
        "print(','.join(heavy))"
    )
    _r = subprocess.run([sys.executable, "-c", _code], capture_output=True, text=True,
                        cwd=str(CORE.parent))
    if _r.returncode != 0:
        return [f"core.schema import 실패: {_r.stderr.strip().splitlines()[-1:]}"]
    _heavy = _r.stdout.strip()
    return [f"core.schema 가 무거운 의존을 끌고 온다: {_heavy}"] if _heavy else []


def test_import_direction() -> None:
    _bad = check_import_direction()
    assert not _bad, "계층 역방향 import:\n  " + "\n  ".join(_bad)


def test_port_consumer() -> None:
    _bad = check_port_consumer()
    assert not _bad, "port 를 직접 부른 곳:\n  " + "\n  ".join(_bad)


def test_schema_is_pure() -> None:
    _bad = check_schema_is_pure()
    assert not _bad, "\n  ".join(_bad)


if __name__ == "__main__":
    _fail = 0
    for _name, _fn in (("import 방향", check_import_direction),
                       ("port 소비자 = store 뿐", check_port_consumer),
                       ("schema 순수성", check_schema_is_pure)):
        _bad = _fn()
        print(f"[{'FAIL' if _bad else ' ok '}] {_name}")
        for _b in _bad:
            print(f"        {_b}")
        _fail += len(_bad)
    sys.exit(1 if _fail else 0)
