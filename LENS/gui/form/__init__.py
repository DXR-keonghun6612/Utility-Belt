"""파라미터 폼 자동 생성 패키지 — spec 추출(``_spec``) + 위젯 빌더(``_form``). 설계는 README."""

from ._form import Config_form, _List_edit, _Model_form
from ._spec import _Spec, specs_from_callable, specs_from_dataclass

__all__ = [
    "Config_form",
    "_Model_form",
    "_List_edit",
    "_Spec",
    "specs_from_callable",
    "specs_from_dataclass",
]
