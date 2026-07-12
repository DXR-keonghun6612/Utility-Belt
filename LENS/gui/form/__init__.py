"""파라미터 폼 자동 생성 — spec 추출(``_spec``) + 위젯 빌더(``_form``). 설계는 README."""

from ._form import Config_form, _Model_form
from ._spec import specs_from_callable

__all__ = ["Config_form", "_Model_form", "specs_from_callable"]
