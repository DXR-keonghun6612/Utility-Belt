""" ### 설정 객체 관리 및 프로젝트 템플릿 정의 모듈

이 모듈은 설정 데이터를 객체화하여 dict 기반 설정보다 관리와 재사용성을
높이고자 설계되었습니다. 또한 설정 정보를 기반으로 프로젝트 템플릿을 구성할
수 있는 클래스를 제공합니다.

---------------------------------------------------------------------------
### Requirement
    - Python >= 3.10
    - argparse
    - pathlib
    - dataclasses
    - json / yaml 파일 포맷 사용 가능 (Utils 기반 처리)

### Structure
    - Config
        - 설정 데이터 클래스인 Basement 정의
        - 설정 파일을 로드하는 Read_from_file 함수 포함
        - argparse 기반 설정 생성용 Read_with_arg_parser 함수 포함
    - Project_Template
        - Config 객체를 기반으로 프로젝트 이름과 결과 경로를 관리
        - 프로젝트별 결과 저장 경로 로직 커스터마이징 가능
"""

from __future__ import annotations
from typing import (
    Any, TypeVar, Generic
)
from dataclasses import asdict, dataclass
from pathlib import Path

import argparse

from .file import Utils


class Config():
    """ ### 프로젝트 설정 관리를 위한 유틸리티 클래스

    설정 정보 객체화를 통해 dict 기반 대비 가독성과 유지보수성 향상

    ---------------------------------------------------------------------------
    ### Structure
    - Basement: 설정 기본 구조를 정의한 dataclass
    - Read_from_file: 설정 파일에서 설정 정보를 불러오는 함수
    - Read_with_arg_parser: argparse 기반 설정 파싱 (미구현)
    """

    @dataclass
    class Basement():
        """ ### 프로젝트 설정 값을 담는 클래스 템플릿

        field 및 __post_init__ 기능을 통해 자동 처리 로직 적용 가능

        -----------------------------------------------------------------------
        ### Structure
        - Config_to_dict: 객체를 dict 형태로 변환
        - Write_to: 객체를 파일로 저장
        """
        def Config_to_dict(self) -> dict[str, Any]:
            """ ### 객체 정보를 dict 데이터로 변환

            ------------------------------------------------------------------
            ### Returns
            - dict[str, Any]: 저장 가능한 형태의 설정 정보
            """
            return asdict(self)

        def Get_args(self):
            """ ### 객체 정보에서 설정 데이터를 생성

            ------------------------------------------------------------------
            ### Returns
            - dict[str, Any]: 함수의 params
            """
            return self.Config_to_dict()

        def Write_to(
            self, name: str, save_dir: str, encoding_type: str = "UTF-8"
        ):
            """ ### 설정 정보를 주어진 경로에 파일로 저장

            ------------------------------------------------------------------
            ### Args
            - name: 저장할 파일 이름
            - save_dir: 저장할 디렉토리 경로
            - encoding_type: 인코딩 형식 (기본값: UTF-8)
            """
            Utils.Write_to(
                Path(save_dir) / name, self.Config_to_dict(), encoding_type
            )

    @staticmethod
    def Read_from_file(
        cfg_obj: type[Config_T], file_path: Path, encoding_type: str = "UTF-8"
    ) -> Config_T:
        """ ### 파일에서 설정 정보를 로드하여 객체로 반환

        json 또는 yaml 포맷을 지원함

        ------------------------------------------------------------------
        ### Args
        - cfg_obj: 설정 클래스 타입
        - file_path: 읽어올 파일 경로
        - encoding_type: 파일 인코딩 (기본값: UTF-8)

        ### Returns
        - Config_T: 설정 객체 인스턴스

        ### Raises
        - ValueError: 지원하지 않는 파일 형식이거나 파일 읽기 실패 시
        """
        _is_ok, _ = Utils.Suffix_check(
            file_path, [".json", ".yaml"], is_fix=False
        )

        if not _is_ok:
            raise ValueError(
                f"Unsupported config file format: {file_path.suffix}"
            )

        is_read_ok, data = Utils.Read_from(file_path, encoding_type)

        if is_read_ok and isinstance(data, dict):
            try:
                return cfg_obj(**data)
            except TypeError as e:
                raise ValueError(
                    f"Failed to instantiate config from {file_path}: {e}"
                ) from e

        raise ValueError(f"Failed to read or parse config file: {file_path}")

    @staticmethod
    def Read_with_arg_parser(
        config_template: type[Config_T],
        parser: argparse.ArgumentParser | None = None
    ) -> tuple[bool, Config_T]:
        """ ### argparse 파서를 통해 설정 정보를 구성 (미구현)

        향후 커맨드라인 기반 설정 파싱을 위한 인터페이스

        ------------------------------------------------------------------
        ### Raises
        - NotImplementedError: 현재 구현되지 않음
        """
        # TODO:
        raise NotImplementedError("this function has problem")


Config_T = TypeVar("Config_T", bound=Config.Basement)


class Project_Template(Generic[Config_T]):
    """ ### 프로젝트 구조를 정의하는 템플릿 클래스

    프로젝트명, 설정값, 결과 저장 경로 등을 관리

    ---------------------------------------------------------------------------
    ### Structure
    - __init__: 프로젝트 초기 설정
    - Get_result_path: 결과 경로 반환 메서드 (미구현)
    """
    def __init__(
        self, name: str, config: Config_T
    ):
        """ ### 프로젝트 템플릿 초기화

        ------------------------------------------------------------------
        ### Args
            - This
                - name: 프로젝트 이름
                - config: Config 클래스에서 파생된 설정 객체

        ### Attributes
        - project_name: 프로젝트 이름 문자열
        - result_path: 설정 기반으로 계산된 결과 저장 경로

        ### Structure
        - __init__: 템플릿 초기화 메서드
        - Get_result_path: 결과 저장 경로를 반환하는 함수 (미구현)
        """
        self.project_name = name
        self.result_path = self.Get_result_path(config)

    def Get_result_path(self, config: Config_T) -> Path:
        """ ### 결과 저장 경로를 반환하는 함수

        ------------------------------------------------------------------
        ### Raises
        - NotImplementedError: 각 프로젝트마다 별도 구현 필요
        """
        raise NotImplementedError
