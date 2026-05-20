"""Parser Protocol.

언어별 파서가 따라야 할 공통 인터페이스를 정의합니다.

모든 언어 백엔드(C++, Python, ...)는 본 프로토콜을 만족해야 합니다.
파이프라인의 무효화 로직은 ``core`` 한 곳에 구현되며, 언어별 차이는
``Parser_Protocol`` 구현체가 흡수합니다.
"""
from __future__ import annotations
from pathlib import Path
from typing import Protocol, runtime_checkable

from core.definition import Module_Info


@runtime_checkable
class Parser_Protocol(Protocol):
    """언어 독립 파서 인터페이스.

    Notes:
        - 01_parser 단계의 출발점.
        - 반환되는 ``Module_Info``는 ``stereotype/abstraction/traits``가
          비어있는 상태(잠정값)이며, 분류는 02_classifier가 채웁니다.
        - 반환되는 의존 파일 목록은 무효화 판정에 사용됩니다.
          (예: C++의 transitive include, Python의 import 그래프)
        - 컨텍스트 해시는 언어별 빌드/실행 환경(C++의 compile_flags,
          Python 버전 등)의 변경을 감지하기 위한 키입니다.
    """

    language: str
    """언어 식별자 (예: ``"cxx"``, ``"python"``)."""

    def Parse_file(
        self, path: Path
    ) -> tuple[Module_Info, list[Path], str]:
        """단일 소스 파일을 파싱하여 IR과 무효화 메타데이터를 반환합니다.

        Args:
            path: 파싱할 소스 파일의 절대 경로.

        Returns:
            (IR Module_Info, 의존 파일 절대 경로 목록, 컨텍스트 해시).
        """
        ...
