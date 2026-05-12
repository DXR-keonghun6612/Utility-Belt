"""Python IR Layer.

core.definition의 공통 IR을 재사용하며, Python 전용 확장이 필요한 경우 이 파일에 추가합니다.
"""
from core.definition import Arg_Info, Method_Info, Class_Info, Module_Info

__all__ = ["Arg_Info", "Method_Info", "Class_Info", "Module_Info"]
