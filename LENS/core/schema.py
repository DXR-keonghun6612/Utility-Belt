"""**재귀 트리 스키마** — 유일 노드 ``Data_Ref`` (데이터모델의 순수 코어).

노드 클래스가 없다. 트리는 ``Data_Ref`` 하나로 재귀하고, kind 는 **``format`` 이 비었는지**로 갈린다:
BRANCH(비었음 — ``info`` = 자식 dict) / LEAF(``(handler, detail)`` — payload 서술자). 모델·범주·영속
전모는 [`README.md`](README.md).

이 모듈은 **저장·정책을 모른다** — ``handler`` 를 import 하지 않아(단방향) 데이터모델만 필요한 소비자가
cv2·registry 없이 이 파일 하나만 들일 수 있다(cv2-free 코어). 범주·영속·컬렉션은 forest 파사드
``Bucket_Store`` ([`store/`](store)) 소유 — 경계는 "한 노드의 자기 범위 vs 컬렉션·정책 범위".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from python_toolbox.data_schema import Data_Schema

@dataclass
class Data_Ref(Data_Schema):
    """트리의 **유일** 노드 — ``bool(format)`` 이 BRANCH(비었음) / LEAF 를 가른다.

    ``Serialize`` 가 중첩 ``Data_Ref`` 를 재귀 직렬화하고 ``__post_init__`` 이 역-재구성한다(``format`` 은
    직렬화 왕복에서 list→tuple 정규화).

    Attributes:
        format: LEAF ``(handler, detail)`` (handler = 디스패치 키, detail = ext/dtype); BRANCH 는 ``()``.
        info:   BRANCH = 자식 ``dict[str, Data_Ref]`` / LEAF = 인라인 payload(``value``; 파일 LEAF 는
            비어 있다 — 경로는 트리 위치와 leaf 이름에서 handler 가 파생한다).
    """

    format: tuple[str, ...] = ()
    info:   dict[str, Any]  = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.format, list):              # JSON 왕복 → list → tuple 정규화
            self.format = tuple(self.format)
        if not self.format:                            # BRANCH → 자식(info 값)을 Data_Ref 로 재구성(재귀)
            self.info = Build(self.info)

    def Is_branch(self) -> bool:
        """컨테이너(BRANCH)인지 — ``format`` 이 비었으면 컨테이너, 있으면 payload(LEAF)."""
        return not self.format

    # ── 자식 CRUD — BRANCH 가 자기 ``info``(자식들)에게 하는 연산 (스택 은유: Push/Pop) ──
    def Get(self, key: str) -> "Data_Ref | None":
        """자식 하나를 이름으로 (없으면 None)."""
        return self.info.get(key)

    def Has(self, key: str) -> bool:
        """그 이름의 자식이 있는지."""
        return key in self.info

    def Push(self, key: str, ref: "Data_Ref") -> None:
        """자식을 넣는다 (같은 이름이면 덮는다 — 한 이름 = 한 자리)."""
        self.info[key] = ref

    def Pop(self, key: str) -> "Data_Ref | None":
        """자식을 빼서 돌려준다 (없으면 None)."""
        return self.info.pop(key, None)

    def Items(self) -> "Iterator[tuple[str, Data_Ref]]":
        """자식들을 ``(key, ref)`` 로 열거한다 (읽기 순회)."""
        yield from self.info.items()

    def At(self, path: tuple[str, ...]) -> "Data_Ref | None":
        """경로(key 시퀀스)를 따라 내려간 노드 (중간에 없으면 None)."""
        _node: "Data_Ref | None" = self
        for _k in path:
            if _node is None:
                return None
            _node = _node.Get(_k)
        return _node

    # ── kind 로 가른 직속 자식 — 이 물음의 유일한 답처 ────────────────────────────
    # LEAF 와 BRANCH 가 한 ``info`` 를 공유하므로 "이 자식이 payload 냐 컨테이너냐" 를 소비처마다
    # 손으로 거르면 같은 필터가 흩어진다. 그 물음은 여기서만 답한다.
    # (``Iter_leaves`` 와 혼동 주의 — 저건 **서브트리 전체**를 재귀로 훑고, 이건 **직속 자식**만 본다.)
    def Leaves(self) -> dict[str, "Data_Ref"]:
        """직속 자식 중 LEAF (payload 서술자) — ``{이름: ref}``."""
        return {_k: _v for _k, _v in self.info.items() if not _v.Is_branch()}

    def Branches(self) -> dict[str, "Data_Ref"]:
        """직속 자식 중 BRANCH (객체 등 컨테이너) — ``{이름: ref}``."""
        return {_k: _v for _k, _v in self.info.items() if _v.Is_branch()}

    def Replace_branches(self, refs: "list[Data_Ref]") -> None:
        """BRANCH 자식을 통째로 갈아끼운다 — **LEAF 는 보존**, 새 이름은 순번(``"0"``, ``"1"`` …).

        프로세스가 낸 객체 리스트로 프레임의 객체 집합을 교체하는 자리. LEAF(rgb·segmap 등)는 객체와 같은
        ``info`` 에 살지만 교체 대상이 아니라, 그 보존이 이 연산의 **불변식**이다(소비처가 손으로 지키지 않게).
        """
        self.info = {**self.Leaves(),
                     **{str(_i): _ref for _i, _ref in enumerate(refs)}}

    # ── 복제 ────────────────────────────────────────────────────────────────────
    def Clone(self) -> "Data_Ref":
        """이 서브트리의 깊은 사본 (``Serialize`` 왕복) — 트리 경계를 넘겨 들이는 ref 는 여길 통과해 공유를 끊는다."""
        return Data_Ref(**self.Serialize())

    # ── 순회 — leaf 주소 지정의 유일한 출처 ──────────────────────────────────────
    def Iter_leaves(self, path: tuple[str, ...] = ()
                    ) -> Iterator[tuple[tuple[str, ...], str, "Data_Ref"]]:
        """이 컨테이너 아래 모든 **LEAF** 를 ``(path, name, ref)`` 로 재귀 순회 (branch 는 파고든다).

        ``path`` 는 조상 branch 의 key 시퀀스 — payload 파일 경로(``{root}/{*path}/{name}.{ext}``)의 **유일한
        출처**다. 인라인 LEAF(attr/rle)도 함께 나오지만 handler 가 파일 연산 때 no-op 이라 순회에 안전하다.
        """
        for _name, _entry in self.info.items():
            if _entry.Is_branch():
                yield from _entry.Iter_leaves(path + (_name,))
            else:                                          # LEAF (파일·인라인 모두)
                yield path, _name, _entry

    def Merge_from(self, src: "Data_Ref"
                   ) -> list[tuple[tuple[str, ...], str, "Data_Ref"]]:
        """``src`` 서브트리에서 **host 에 없는 것만** 들인다 (host 가 이김; 순수 — 디스크 모름).

        겹치는 컨테이너는 파고들고 없는 노드는 ``Clone`` 해 꽂는다. 들인 LEAF 를 ``Iter_leaves`` 와 같은
        모양(``(path, name, ref)``)으로 돌려줘, 호출 측이 그 payload 만 골라 복사한다.
        """
        _inserted: list[tuple[tuple[str, ...], str, "Data_Ref"]] = []
        for _name, _entry in src.info.items():
            _cur = self.info.get(_name)
            if _entry.Is_branch():
                if isinstance(_cur, Data_Ref) and _cur.Is_branch():
                    for _p, _n, _r in _cur.Merge_from(_entry):           # 양쪽에 있음 → 파고듦
                        _inserted.append(((_name,) + _p, _n, _r))
                else:
                    _clone = _entry.Clone()                              # 통째 삽입
                    self.info[_name] = _clone
                    _inserted += [((_name,) + _p, _n, _r)
                                  for _p, _n, _r in _clone.Iter_leaves()]
            elif _cur is None:                                           # leaf — host 에 없을 때만
                _clone = _entry.Clone()
                self.info[_name] = _clone
                _inserted.append(((), _name, _clone))
        return _inserted

    # ── 인라인 값 LEAF — class_id·bbox·source_stem 등 ────────────────────────────
    def Attr(self, name: str, default: str = "") -> str:
        """이 컨테이너의 인라인 값 (``info[name].info["value"]``; 없으면 default)."""
        _a = self.info.get(name)
        return _a.info.get("value", default) if isinstance(_a, Data_Ref) else default

    def Set_attr(self, name: str, value: str) -> None:
        """이 컨테이너의 인라인 **문자열** 라벨을 설정한다 (있으면 값만 갱신, 없으면 ``("", "str")``).

        class_id·source_stem 처럼 개념 없는 문자열 전용이다. 다른 타입·개념(``bbox`` 등)은 format 을
        선언해 :func:`Build` 로 세운다 — 여기서 값의 타입을 알아맞히지 않는다.
        """
        _a = self.info.get(name)
        if isinstance(_a, Data_Ref):
            _a.info["value"] = value
        else:
            self.info[name] = Data_Ref(format=("", "str"), info={"value": value})


#: 인라인 LEAF 의 detail(둘째 칸)에 오는 **파이썬 타입** 이름 — 값이 파일이 아니라 ``info["value"]`` 에 산다.
#: 값→이름 판정은 [`port/attr.py`](port/attr.py) 가 한다 (읽고 쓰는 쪽의 일이다).
PYTHON_TYPES: tuple[str, ...] = ("str", "int", "float", "list")


def Build(data: dict) -> dict[str, Data_Ref]:
    """선언 dict → 자식 노드들 ``{이름: Data_Ref}``. BRANCH 자식은 ``__post_init__`` 이 재귀로 마저 세운다.

    값이 이미 ``Data_Ref`` 면 그대로 두고, 선언 dict(``{format, info}``)면 노드로 세운다. **key 는 이름
    (경로)일 뿐이고, 그 노드가 무엇인지는 언제나 ``format`` 이 말한다** — 이름에서 종류를 되짚지 않는다.

    LEAF 의 ``format`` = ``(개념, detail)``:

    - **파일** — ``("segmap", "png")`` · ``("image", "jpg")``. 첫 칸이 등록된 handler, detail 은 확장자.
    - **인라인** — 값에 개념이 없으면 첫 칸이 비고 detail 이 파이썬 타입이다: ``("", "str")`` ·
      ``("", "int")`` · ``("", "list")``. 개념이 있을 때만 첫 칸이 찬다 — ``("bbox", "list")``: 첫 칸이
      원소 규약(int 4개)을 말하고 detail 은 그저 파이썬 타입이다. 원소 타입은 **검사하지 않는다**.

    ``port`` 는 **등록된 handler 가 아닌 첫 칸을 전부 인라인**으로 보므로, 개념을 더해도 port 를 안 고친다.
    (예전엔 인라인이 전부 ``("attr", <아무 문자열>)`` 이었다 — 값이 list 인데 detail 은 ``"str"`` 이라고
    적혀 있었고, 소비처마다 그 문자열을 손으로 지어 복제했다.)

    Example:
        >>> Data_Ref(info=Build({
        ...     "class_id": {"format": ("", "str"),      "info": {"value": "crack"}},
        ...     "bbox":     {"format": ("bbox", "list"), "info": {"value": [3, 7, 40, 52]}}}))
    """
    return {_k: _v if isinstance(_v, Data_Ref) else Data_Ref(**_v) for _k, _v in data.items()}
