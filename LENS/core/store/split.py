"""몫 store — 내보내기에 먹일 **일회용** 범주 배정 (``{몫 이름: [정본 stem…]}``).

정본을 비율대로 갈라 폴더별로 내보낼 때, 내보내기(`../export`)가 요구하는 건 딱 둘이다: **범주 목록**과
범주마다의 **정본 역참조**(`source_stem`). 그 둘만 든 껍데기가 이것이다.

## 왜 store 인가 — 그리고 왜 디스크에 안 앉나

`Frame_exporter` 는 `source.CATEGORIES` 와 `source.Bucket(범주)` 로만 입력을 읽는다. 즉 **범주 × item**
이라는 store 의 모양이 곧 내보내기의 입력 계약이다. 그래서 새 계약을 만드는 대신 그 모양을 그대로 쓴다.

다만 **영속은 안 한다** — 이 배정은 산출물이 아니라 *이번 내보내기의 인자*다. 비율이나 salt 를 바꾸면
다른 배정이 나오는 게 정상이고, 그걸 디스크에 남기면 "어느 배정이 진짜냐"는 물음이 생긴다(레시피와
산출물을 섞지 않는다). 그래서 ``root`` 가 비어 있고 ``Save`` 를 부르지 않는다.

## 범주가 **인스턴스** 값이다

정본(`Dataset_Meta`)·파생(`Sample_Set`)은 범주가 타입의 성질이라 `CATEGORIES` 가 ClassVar 다. 여기서는
몫의 이름과 개수를 **사람이 그때그때 정하므로**(2분할·4분할·임의 이름) 인스턴스가 그 ClassVar 를 가린다.
그래서 이 타입은 병합(`Merge`)의 "같은 타입끼리만" 보장이 성립하지 않는다 — 애초에 라이프사이클을
안 쓰는 껍데기라 문제되지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schema import Data_Ref
from .bucket_store import Bucket_Store


@dataclass
class Split_Set(Bucket_Store):
    """범주 = 몫 이름, item = 정본 역참조 하나(`source_stem`). 메모리 전용.

    Attributes:
        categories: 몫 이름들 — 순서가 곧 내보내기 순회 순서다. ``CATEGORIES`` 를 인스턴스에서 가린다.
    """

    categories: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.categories = tuple(self.categories)
        self.CATEGORIES = self.categories      # 런타임 값이라 ClassVar 를 인스턴스가 가린다 (위 docstring)
        super().__post_init__()

    @classmethod
    def Of(cls, assignment: dict[str, list[str]]) -> "Split_Set":
        """``{몫 이름: [stem…]}`` → 몫 store. 빈 몫도 **범주로 남긴다**(빈 폴더가 나야 배정이 드러난다).

        item key 는 stem 그대로다 — 파생 sample 처럼 새 id 를 지어낼 이유가 없다(하나가 프레임 하나).
        """
        _set = cls(categories=tuple(assignment))
        for _name, _stems in assignment.items():
            for _stem in _stems:
                _ref = Data_Ref()
                _ref.Set_attr("source_stem", _stem)     # 내보내기가 정본을 되짚는 유일한 끈
                _set.tree.Get(_name).Push(_stem, _ref)
        return _set
