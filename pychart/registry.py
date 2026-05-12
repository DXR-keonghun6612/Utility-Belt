"""Python 전역 심볼 테이블 정의."""
from core.registry import Symbol_Registry
from core.definition import Module_Info

NODE = Module_Info

SYMBOL_TABLE = Symbol_Registry[NODE]("Global_Symbol_Table", NODE)
