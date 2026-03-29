"""파싱 타입 및 전역 심볼 레지스트리 정의.

IR 노드 타입과 프로젝트 전역 심볼 테이블(Registry)을 정의합니다.
"""
from typing import TypeVar
from python_toolbox.project import Registry

from pychart.definition import Module_Info

NODE = Module_Info
T = TypeVar("T")


class Symbol_Registry(Registry[T]):
    """전역 심볼 테이블(Global Symbol Table)을 위한 확장 레지스트리."""

    def Register_instance(self, key: str, obj: T) -> T:
        """파싱된 인스턴스 객체를 레지스트리에 직접 등록합니다."""
        if not isinstance(obj, self.target_type):
            raise TypeError(
                f"[ERROR] '{key}'의 데이터는 '{self.target_type.__name__}' 타입이어야 합니다."
            )
            
        if key in self._module_dict:
            # 중복 등록 허용 (최신 파일 우선)
            self._module_dict[key] = obj
            return obj

        self._module_dict[key] = obj
        return obj

    def Get_all(self) -> dict[str, T]:
        """등록된 모든 데이터를 딕셔너리 형태로 반환합니다."""
        return self._module_dict.copy()


# 프로젝트 전체의 파일 경로 및 심볼 정보를 매핑하는 중앙 레지스트리 (명칭 통일: SYMBOL_TABLE)
SYMBOL_TABLE = Symbol_Registry[NODE]("Global_Symbol_Table", NODE)
