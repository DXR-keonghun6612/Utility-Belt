"""전역 심볼 레지스트리 베이스 정의."""
from typing import TypeVar
from python_toolbox import Registry

T = TypeVar("T")


class Symbol_Registry(Registry[T]):
    """전역 심볼 테이블(Global Symbol Table)을 위한 확장 레지스트리."""

    def Register_instance(self, key: str, obj: T) -> T:
        """파싱된 인스턴스 객체를 레지스트리에 직접 등록합니다."""
        if not isinstance(obj, self.target_type):
            raise TypeError(
                f"[ERROR] '{key}'의 데이터는 '{self.target_type.__name__}' 타입이어야 합니다."
            )

        self._module_dict[key] = obj
        return obj

    def Get_all(self) -> dict[str, T]:
        """등록된 모든 데이터를 딕셔너리 형태로 반환합니다."""
        return self._module_dict.copy()

    def Clear(self):
        self._module_dict.clear()
