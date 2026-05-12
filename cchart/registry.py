"""C++ 전역 심볼 테이블 정의."""
from core.registry import Symbol_Registry
from cchart.definition import Translation_Unit_Info

NODE = Translation_Unit_Info

SYMBOL_TABLE = Symbol_Registry[NODE]("CXX_Symbol_Table", NODE)
