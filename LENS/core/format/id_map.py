"""id_map — id 표의 **구조와 그 연산** (한 줄 = ``Id_entry``, 표 = ``Id_map``).

geometry 가 아닌데 여기 사는 이유는 형제들과 같다: 자기가 **무슨 뜻인지도**(어느 데이터셋의 표인지)
**어디 사는지도**(정본 params leaf 인지 내보낸 yaml 인지) 모른다. 읽고 쓰는 건 codec·port 가, 어느
파일이 정본인지는 store 가, 편집을 라벨에 반영하는 건 그 위(``Pipeline``)가 안다.

## 고정된 건 **번호와 이름 둘**뿐이다

표가 답하는 질문은 하나다 — *"이 번호는 무엇인가"*. 그래서 항목의 고정 필드도 둘이다: 라벨이 저장하는
``id_num``(정체·불변)과 사람이 읽는 ``id_name``(개정된다). ``category_id`` 처럼 소비 측이 붙이는 칸은
프로젝트마다 늘고 줄어서, 필드로 박으면 표 편집·병합이 그때마다 따라 바뀐다 — 그런 칸은 ``extra`` 로
**통째 나른다**(LENS 는 값을 만들지도 읽지도 않는다).

**부르는 이름과 앉는 이름은 다르다.** 파일은 학습 측과의 계약이라 ``class_id``/``name`` 으로 앉고
(``__custom_keys__``), 안에서는 그 칸이 무엇을 세는 번호든 ``id_num``/``id_name`` 으로 부른다.

## 문서와 표는 다른 것이다

파일에 앉는 모양(**문서**)은 호출번호 키 dict 다::

    0: {class_id: 0, name: no_label,      category_id: 0}
    1: {class_id: 1, name: 10D132000NT9,  category_id: 2}

바깥 키(호출번호)는 **목록에서의 자리**이고 ``id_num`` 은 정체다. 둘은 편집 뒤에도 **같이 조밀**하다 —
아래 압축 때문에 결과적으로 늘 일치하지만, 뜻이 다르니 따로 둔다(문서를 읽는 쪽은 바깥 키를 안 믿고
항목 안의 번호를 본다).

## 번호가 사라지면 뒤를 당긴다 (압축)

삭제·병합으로 번호가 비면 **그 뒤를 한 칸씩 당겨** 표를 0..N-1 로 유지한다. 대가는 분명하다: 지운 번호
뒤의 class 가 전부 밀리므로 **기존 체크포인트는 그 지점부터 무효**다(재학습 전제). 그래도 구멍을 남기는
쪽이 더 나쁘다 — 표에 빈 번호가 생기면 "이 번호는 지워진 건가, 아직 안 쓴 건가"를 아무도 답할 수 없고,
그 상태로 내보낸 산출물은 출력 차원과 항목 수가 안 맞는다.

그래서 이 모듈은 **번호를 옮기는 것을 정상 동작으로** 다룬다. 옮긴 내역은 ``remap`` 이 전부 담으므로
(아래) 라벨은 표를 따라 함께 움직이고, 사람이 볼 요약은 호출 측이 남긴다.

## 편집은 표와 ``remap`` 둘을 낸다

추가·삭제·병합은 새 표만으로 안 끝난다 — 사라지거나 밀린 번호를 든 **라벨**이 남기 때문이다. 그래서
편집 셋은 ``remap``(``{옛 id_num: 새 id_num}``)을 함께 내고, 라벨을 실제로 다시 쓰는 일은
``store.Dataset_Meta.Remap_classes`` 가 한다. 여기는 **무엇이 무엇으로 가는지만** 정한다.

remap 은 두 겹이다 — 편집 자체(지운 것 → 미분류 / 흡수된 것 → 생존자)와 그 뒤의 압축(밀린 것 → 새 자리).
:func:`Compose` 가 그 둘을 하나로 잇는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Iterable

from python_toolbox.data_schema import Data_Schema

from ..constant import UNCLASSIFIED_ID


@dataclass
class Id_entry(Data_Schema):
    """표의 한 줄 — 고정은 번호·이름 둘, 나머지는 나르기만 한다 (모듈 docstring 참고).

    Attributes:
        id_num:   그 id 의 번호 = 라벨이 저장하는 값. 표 안에서 **자리이자 정체**라, 앞이 지워지면 압축을
            따라 움직인다 (모듈 docstring). 옮긴 내역은 편집이 낸 ``remap`` 이 든다.
        id_name:  표시 이름(부품코드 등) — **개정된다**. 그래서 라벨은 이름이 아니라 번호를 저장한다.
        extra:    소비 측이 붙인 부속 칸(``category_id`` 등) — 그대로 실어 나른다. 문서로 나갈 때
            고정 둘과 **같은 층에 펴진다**(중첩 dict 가 아니라 형제 키).
    """

    __custom_keys__: ClassVar[dict[str, str]] = {"id_num": "class_id", "id_name": "name"}

    #: 문서에서 고정 둘이 앉는 키 — ``extra`` 를 가를 때 이 둘을 걷어낸다.
    _FIXED: ClassVar[tuple[str, ...]] = ("class_id", "name")

    id_num:  int
    id_name: str
    extra:   dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """타입을 굳힌다 — yaml/json 왕복은 숫자를 문자로 줄 수 있다."""
        self.id_num  = int(self.id_num)
        self.id_name = str(self.id_name)

    @classmethod
    def Restore(cls, entry: Any) -> "Id_entry | None":
        """문서 한 항목 → 항목 (**읽을 수 없으면 None** — 지어내지 않는다).

        고정 둘을 걷어낸 나머지가 그대로 ``extra`` 다. 그래서 모르는 칸이 있어도 왕복에서 안 사라진다.
        """
        if not isinstance(entry, dict):
            return None
        _num, _name = entry.get("class_id"), entry.get("name")
        if not _name or isinstance(_num, bool) or not isinstance(_num, (int, float)):
            return None
        return cls(int(_num), str(_name),
                   {_k: _v for _k, _v in entry.items() if _k not in cls._FIXED})

    def Serialize(self) -> dict[str, Any]:
        """문서 한 항목으로 — 고정 둘(저장 이름) + ``extra`` 를 같은 층에 편다."""
        _out = super().Serialize()
        _out.update(_out.pop("extra", {}))
        return _out


@dataclass
class Id_map(Data_Schema):
    """id 표 — ``Id_entry`` 목록 + 그 위의 편집(추가·삭제·병합).

    편집은 **제자리에서** 표를 고치고 ``remap`` 을 돌려준다 (모듈 docstring 참고). 여러 번 쌓을 땐
    :func:`Compose` 로 remap 을 합친다.

    Attributes:
        entries: 항목들 — 순서는 안 지킨다 (문서로 나갈 때 :meth:`Document` 가 번호순으로 세운다).
    """

    entries: list[Id_entry] = field(default_factory=list)

    # ── 문서 왕복 ─────────────────────────────────────────────────────────────
    @classmethod
    def Restore(cls, doc: dict | None) -> "Id_map":
        """문서(호출번호 키 dict) → 표. **바깥 키는 안 읽는다** — 정체는 항목 안의 번호다.

        읽을 수 없는 항목은 **버린다**(``Id_entry.Restore`` 가 판정). 조용히 고쳐 넣으면 정본과 어긋난
        표가 export 까지 흘러가기 때문이다. 대신 표를 **다시 쓰는** 호출 측(편집기)은 문서 항목 수와
        :attr:`entries` 수를 대조해 사용자에게 알려야 한다 — 안 그러면 저장 한 번에 읽을 수 없던 줄이
        소리 없이 사라진다.
        """
        _out = (Id_entry.Restore(_e) for _e in (doc or {}).values())
        return cls([_e for _e in _out if _e is not None])

    def Document(self) -> dict[int, dict]:
        """표 → 문서. 호출번호를 번호 오름차순으로 **0부터 조밀하게** 매긴다.

        편집을 거친 표는 압축(:meth:`_compact`) 때문에 이미 조밀해서 호출번호와 ``id_num`` 이 일치한다.
        여기서 다시 매기는 건 **밖에서 들어온 문서**(구멍이 있을 수 있다)를 그대로 내보낼 때를 위해서다.
        """
        return {_n: _e.Serialize() for _n, _e in enumerate(self.Sorted())}

    # ── 조회 ─────────────────────────────────────────────────────────────────
    def Sorted(self) -> list[Id_entry]:
        """번호 오름차순 항목들 — 표시·문서화의 공통 순서."""
        return sorted(self.entries, key=lambda _e: _e.id_num)

    def Get(self, id_num: int) -> Id_entry | None:
        """그 번호의 항목 (없으면 None)."""
        return next((_e for _e in self.entries if _e.id_num == int(id_num)), None)

    # ── 편집 — 표를 고치고 remap 을 낸다 ────────────────────────────────────────
    def Add(self, name: str, extra: dict[str, Any] | None = None) -> Id_entry:
        """새 항목을 표 **끝에** 더한다 (remap 없음 — 기존 라벨이 가리키는 게 안 바뀐다).

        번호는 현재 최대 + 1 이다. 표는 압축으로 늘 조밀하니 그게 곧 다음 빈 자리다.

        Args:
            name:  표시 이름.
            extra: 부속 칸(``category_id`` 등) — 무엇이 필요한지는 호출 측이 안다.

        Raises:
            ValueError: 이름이 비었거나 이미 표에 있는 이름일 때 (이름은 조회 축이라 유일해야 한다).
        """
        _name = str(name).strip()
        if not _name:
            raise ValueError("이름이 비었다")
        if any(_e.id_name == _name for _e in self.entries):
            raise ValueError(f"이미 있는 이름: {_name!r}")
        _entry = Id_entry(max((_e.id_num for _e in self.entries), default=-1) + 1,
                          _name, dict(extra or {}))
        self.entries.append(_entry)
        return _entry

    def Delete(self, id_nums: Iterable[int]) -> dict[int, int]:
        """항목들을 표에서 뺀다 — 그 라벨은 **미분류로 돌아가고**, 뒤의 번호는 당겨진다.

        지운다는 건 라벨을 없애는 게 아니라 근거를 걷는 것이다: 객체는 그대로 있고 분류만 미분류
        슬롯으로 되돌아간다.

        Returns:
            remap — ``{지운 번호: 0}`` 에 압축으로 밀린 것들(``{옛 번호: 새 번호}``)이 합쳐진 하나.

        Raises:
            ValueError: 표에 없는 번호이거나, 미분류(0) 슬롯을 지우려 할 때 — 그건 **삭제의 목적지**라
                지우면 되돌아갈 자리가 없어진다.
        """
        _ids = self._known(id_nums)
        if UNCLASSIFIED_ID in _ids:
            raise ValueError(f"미분류 슬롯({UNCLASSIFIED_ID}번)은 지울 수 없다 — 삭제의 목적지다")
        self.entries = [_e for _e in self.entries if _e.id_num not in _ids]
        return Compose({_c: UNCLASSIFIED_ID for _c in _ids}, self._compact())

    def Merge(self, into: int, others: Iterable[int]) -> dict[int, int]:
        """``others`` 를 ``into`` 로 합친다 — 흡수된 라벨은 생존자로 가고, 뒤의 번호는 당겨진다.

        **생존자는 호출 측이 따로 지정한다** — 객체 병합(가장 작은 obj_id 가 이긴다)과 다르다. 여기서는
        이름이 곧 사람이 읽는 정체(부품코드)라 어느 쪽으로 통합할지가 자동으로 정해지지 않는다. 생존자의
        ``id_name``·``extra`` 는 그대로 남고, 흡수되는 항목은 표에서 사라진다.

        Returns:
            remap — ``{흡수된 번호: 생존자}`` 에 압축으로 밀린 것들이 합쳐진 하나. **생존자 자신도 밀릴
            수 있다** — 앞쪽을 흡수했으면 자기 자리가 당겨지므로, 흡수된 번호는 그 최종 자리로 간다.

        Raises:
            ValueError: 표에 없는 번호이거나, 합칠 대상이 없거나, 미분류(0)가 ``into``·``others`` 어느
                쪽에든 들었을 때 — 미분류로 합치는 건 :meth:`Delete` 이고, 미분류를 어딘가로 흡수시키면
                "분류 안 됨"이 하나의 class 로 둔갑한다.
        """
        _into = int(into)
        if _into == UNCLASSIFIED_ID:
            raise ValueError(f"미분류({UNCLASSIFIED_ID}번)로 합치는 건 삭제다 — Delete 를 쓴다")
        _ids = self._known([_into, *others]) - {_into}
        if UNCLASSIFIED_ID in _ids:
            raise ValueError(f"미분류({UNCLASSIFIED_ID}번)는 흡수될 수 없다 — 분류가 없다는 표시다")
        if not _ids:
            raise ValueError("합칠 대상이 없다 (통합 대상과 병합 대상이 같다)")
        self.entries = [_e for _e in self.entries if _e.id_num not in _ids]
        return Compose({_c: _into for _c in _ids}, self._compact())

    def _compact(self) -> dict[int, int]:
        """번호를 0부터 조밀하게 다시 매긴다 — 반환은 그 이동 ``{옛 번호: 새 번호}`` (제자리는 뺀다).

        **순서는 보존한다** — 번호 오름차순 그대로 자리만 당기므로 표를 보던 사람의 감각이 안 뒤집힌다.
        미분류(0)는 항상 최소라 그대로 0 에 남는다(삭제·흡수 둘 다 막혀 있어 사라질 수 없다).
        """
        _shift: dict[int, int] = {}
        for _new, _e in enumerate(self.Sorted()):
            if _e.id_num != _new:
                _shift[_e.id_num] = _new
                _e.id_num = _new
        return _shift

    def _known(self, id_nums: Iterable[int]) -> set[int]:
        """표에 실제로 있는 번호 집합으로 — 하나라도 없으면 **실패**한다(조용히 건너뛰지 않는다)."""
        _ids = {int(_c) for _c in id_nums}
        _missing = sorted(_c for _c in _ids if self.Get(_c) is None)
        if _missing:
            raise ValueError(f"표에 없는 번호: {_missing}")
        return _ids


def Compose(base: dict[int, int], more: dict[int, int]) -> dict[int, int]:
    """remap 둘을 잇는다 — ``base`` 뒤에 ``more`` 를 적용한 하나의 ``{옛 번호: 최종 번호}``.

    편집을 쌓을 때 필요하다: 5 를 3 으로 합친 뒤 3 을 지우면 5 도 결국 미분류로 가야 하는데, 두 remap 을
    그냥 합치면 5→3 이 남아 없는 항목을 가리킨다. 제자리로 돌아온 것(``옛 == 최종``)은 뺀다.

    Args:
        base: 먼저 일어난 재배정.
        more: 그 결과 위에 일어난 재배정 (키는 ``base`` 적용 **후**의 번호).
    """
    _out = {_old: more.get(_cur, _cur) for _old, _cur in base.items()}
    _out.update({_cur: _new for _cur, _new in more.items() if _cur not in _out})
    return {_old: _new for _old, _new in _out.items() if _old != _new}
