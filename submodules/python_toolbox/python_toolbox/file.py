""" ### 파일 처리와 예외 핸들링을 위한 유틸리티 통합 모듈

이 모듈은 텍스트, JSON, YAML 포맷 파일의 읽기/쓰기 기능을 통합 제공합니다.
파일 저장 시 자동 디렉토리 생성 및 확장자 기반 분기 처리를 지원하며,
파일 입출력 과정에서 발생할 수 있는 예외를 공통 방식으로 처리하는
데코레이터 `Handle_exp` 도 함께 포함합니다.

---------------------------------------------------------------------------
### Requirement
    - Python >= 3.10
    - json, yaml
    - pathlib, shutil
    - typing, dataclasses

### Structure
    - Handle_exp
        - 예외 메시지를 표준화하여 출력하는 데코레이터 생성 함수
    - Process
        - File_Process: 입출력 공통 베이스 클래스
        - Text: .txt 파일 처리 클래스
        - Json: .json 파일 처리 클래스
        - Yaml: .yaml 파일 처리 클래스
    - Utils
        - Suffix_check: 확장자 검사 및 자동 보정
        - Read_from: 파일 확장자에 따른 읽기 자동 분기
        - Write_to: 데이터 유형 기반 저장 분기
        - Make_the_file_group: 이미지 파일을 그룹 단위로 복사 정리
"""
from abc import ABC, abstractmethod
from functools import wraps
from typing import TypeVar, Callable, cast, Any

from pathlib import Path
from shutil import copyfile

import json
import yaml


KEY = TypeVar(
    "KEY", bound=int | float | bool | str)
VALUE = TypeVar(
    "VALUE", bound=int | float | bool | str | tuple | list | dict | None)

F = TypeVar("F", bound=Callable)


def Handle_exp(extra_exp: dict[type[Exception], str] | None = None):
    """ ### 예외 발생 시 사용자 정의 메시지로 처리하는 데코레이터 생성 함수

    함수 실행 중 발생하는 예외를 잡아내고 등록된 예외 메시지를 출력한 뒤
    (False, None)을 반환합니다. 파일 입출력 또는 유틸 함수에 wrapping하여
    예외 메시지를 통합 관리하는 용도로 사용됩니다.

    ------------------------------------------------------------------
    ### Args
    - extra_exp: 예외 클래스와 출력 메시지 매핑 딕셔너리
                 예: {FileNotFoundError: "파일 없음"}

    ### Returns
    - Callable: 예외 처리가 적용된 데코레이터 함수

    ### Structure
    - Checker(func): 대상 함수에 데코레이터를 적용하는 내부 함수
    - wrapper(*args, **kwargs): 예외를 포착하고 메시지를 출력한 후
                                 (False, None) 반환
    """
    extra_exp = extra_exp or {}

    def Checker(func: F) -> F:

        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                _exp = type(e)
                message = extra_exp.get(_exp, "알 수 없는 파일 처리 오류 발생:")
                print(f"{message} -> {e}")
            return False, None
        return cast(F, wrapper)

    return Checker


BASIC_FILE_ERROR = {
    PermissionError: "파일 권한 부족"
}

JSON_FILE_READ_ERROR = {
    **BASIC_FILE_ERROR,
    json.JSONDecodeError: "JSON 파싱 오류 발생",
    TypeError: "JSON 변환 불가능한 데이터 포함"
}


class Process():
    """ ### 다양한 파일 포맷 처리 기능을 제공하는 클래스 집합

    텍스트, JSON, YAML 파일의 읽기/쓰기 기능을 포함하고 예외 처리도 통합함

    ---------------------------------------------------------------------------
    ### Structure
    - File_Process: 파일 입출력 기본 기능 클래스
    - Text: 텍스트 파일(.txt) 입출력 기능 제공
    - Json: JSON 파일 입출력 기능 제공
    - Yaml: YAML 파일 입출력 기능 제공
    """
    class File_Process(ABC):
        """ ### 파일 입출력의 공통 로직을 정의한 베이스 클래스

        파일 존재 보장, 일반화된 read/write 인터페이스를 제공함

        ------------------------------------------------------------------------
        ### Structure
        - Ensure_dir: 저장 경로가 없을 경우 생성
        - Read_from: 파일로부터 데이터 읽기 (미구현)
        - Write_to: 파일에 데이터 저장 (미구현)
        """
        @classmethod
        def Ensure_dir(cls, path: Path):
            """ ### 지정된 파일 경로의 상위 디렉토리가 없을 경우 생성

            ------------------------------------------------------------------
            ### Args
            - path: 디렉토리 생성이 필요한 파일 경로
            """
            path.parent.mkdir(parents=True, exist_ok=True)

        @classmethod
        @abstractmethod
        def Read_from(
            cls, *args, file: Path, enc: str = "UTF-8", **kwarg
        ) -> tuple[bool, Any]:
            """ ### 파일로부터 데이터를 읽어오는 인터페이스 (미구현)

            ------------------------------------------------------------------
            ### Args
            - file: 읽을 파일 경로
            - enc: 인코딩 방식
            - kwarg: 확장 인자

            ### Returns
            - Tuple[bool, Any]: 성공 여부 및 읽은 데이터

            ### Raises
            - NotImplementedError: 구현되지 않은 함수
            """
            raise NotImplementedError

        @classmethod
        @abstractmethod
        def Write_to(
            cls, *args, file: Path, data: Any, enc: str = "UTF-8", **kwarg
        ) -> bool:
            """ ### 데이터를 파일로 저장하는 인터페이스 (미구현)

            ------------------------------------------------------------------
            ### Args
            - file: 저장할 파일 경로
            - data: 저장할 데이터
            - enc: 인코딩 방식
            - kwarg: 확장 인자

            ### Returns
            - bool: 저장 성공 여부

            ### Raises
            - NotImplementedError: 구현되지 않은 함수
            """
            raise NotImplementedError

    class Text(File_Process):
        """ ### 텍스트 파일(.txt) 읽기/쓰기를 위한 처리 클래스

        ------------------------------------------------------------------------
        ### Structure
        - Read_from: 텍스트 파일을 줄 단위로 읽음
        - Write_to: 문자열 또는 문자열 리스트를 텍스트 파일로 저장
        """
        @classmethod
        @Handle_exp()
        def Read_from(
            cls, file: Path,
            enc: str = "UTF-8", start: int = 0, delim: str = "\n"
        ) -> tuple[bool, list[str]]:
            """ ### 텍스트 파일을 읽어 지정된 구분자 기준으로 나눈 리스트 반환

            ------------------------------------------------------------------
            ### Args
            - file: 읽을 텍스트 파일 경로
            - enc: 인코딩 방식
            - start: 읽기 시작할 인덱스
            - delim: 구분자 (기본값: 줄바꿈)

            ### Returns
            - Tuple[bool, list]: 성공 여부 및 문자열 리스트
            """
            _, _file = Utils.Suffix_check(file, ".txt")
            if _file.exists():
                return True, _file.read_text(enc).split(delim)[start:]
            return False, []

        @classmethod
        @Handle_exp()
        def Write_to(
            cls, file: Path, data: str | list[str], enc: str = "UTF-8",
            anno: list[str] | str | None = None
        ) -> bool:
            """ ### 텍스트 데이터를 파일로 저장

            주석 또는 메타 정보도 함께 저장 가능

            ------------------------------------------------------------------
            ### Args
            - file: 저장할 파일 경로
            - data: 저장할 문자열 또는 문자열 리스트
            - enc: 인코딩 형식
            - anno: 상단에 추가할 주석 (기본값 = None)

            ### Returns
            - bool: 저장 성공 여부
            """
            cls.Ensure_dir(file)
            _, _path = Utils.Suffix_check(file, ".txt", True)

            _data = (
                [anno] if isinstance(anno, str) else anno
            ) if anno else []
            _data += [data] if isinstance(data, str) else data

            _path.write_text("\n".join(_data), enc)

            return True

    class Json(File_Process):
        """ ### JSON 파일의 읽기/쓰기 기능을 제공하는 클래스

        ------------------------------------------------------------------------
        ### Structure
        - Read_from: JSON 파일을 파싱하여 dict 반환
        - Write_to: dict 데이터를 JSON 포맷으로 저장
        """
        @classmethod
        @Handle_exp(extra_exp=JSON_FILE_READ_ERROR)
        def Read_from(
            cls, file: Path, enc: str = "UTF-8"
        ) -> tuple[bool, dict[str, Any]]:
            """ ### JSON 파일을 읽어 딕셔너리로 반환

            ------------------------------------------------------------------
            ### Args
            - file: JSON 파일 경로
            - enc: 인코딩 방식

            ### Returns
            - Tuple[bool, dict]: 성공 여부 및 데이터 딕셔너리
            """
            _, _file = Utils.Suffix_check(file, ".json")

            if not _file.exists():
                return False, {}

            with file.open(encoding=enc) as _f:
                return True, json.load(_f)

        @classmethod
        @Handle_exp()
        def Write_to(
            cls, file: Path, data: Any, enc: str = "UTF-8",
            indent: int = 4
        ) -> bool:
            """ ### 딕셔너리 데이터를 JSON 파일로 저장

            ------------------------------------------------------------------
            ### Args
            - file: 저장할 파일 경로
            - data: 저장할 데이터 (딕셔너리)
            - enc: 인코딩 방식
            - indent: JSON 들여쓰기 수준

            ### Returns
            - bool: 저장 성공 여부
            """
            cls.Ensure_dir(file)

            _, _path = Utils.Suffix_check(file, ".json", True)

            with _path.open(mode="w", encoding=enc) as _f:
                json.dump(data, _f, indent=indent)
            return True

    class Yaml(File_Process):
        """ ### YAML 파일의 읽기/쓰기 기능을 제공하는 클래스

        ------------------------------------------------------------------------
        ### Structure
        - Read_from: YAML 파일을 파싱하여 객체 반환
        - Write_to: 객체를 YAML 형식으로 저장
        """
        loader = yaml.FullLoader

        @classmethod
        @Handle_exp()
        def Read_from(
            cls, file: Path, enc: str = "UTF-8", **kwarg
        ) -> tuple[bool, Any]:
            """ ### YAML 파일을 객체로 읽어 반환

            ------------------------------------------------------------------
            ### Args
            - file: YAML 파일 경로
            - enc: 인코딩 방식
            - kwarg: 확장 인자

            ### Returns
            - Tuple[bool, Any]: 성공 여부 및 파싱된 객체
            """
            _, _file = Utils.Suffix_check(file, ".yaml")

            if not _file.exists():
                return False, {}

            with file.open(encoding=enc) as _f:
                return True, yaml.load(_f, cls.loader)

        @classmethod
        @Handle_exp()
        def Write_to(
            cls, file: Path, data: Any, enc: str = "UTF-8",
            indent: int = 4
        ) -> bool:
            """ ### 데이터를 YAML 형식으로 파일에 저장

            ------------------------------------------------------------------
            ### Args
            - file: 저장할 파일 경로
            - data: 저장할 데이터 (딕셔너리 등)
            - enc: 인코딩 방식
            - indent: 들여쓰기 수준

            ### Returns
            - bool: 저장 성공 여부
            """
            cls.Ensure_dir(file)

            _, _path = Utils.Suffix_check(file, ".yaml", True)

            with _path.open(mode="w", encoding=enc) as _f:
                yaml.dump(data, _f, indent=indent, sort_keys=False)
            return True


class Utils():
    """ ### 파일 입출력 및 유틸리티 기능을 제공하는 클래스

    확장자 기반 처리, 형식 검증, 데이터 입출력 및 그룹 디렉토리 생성을 지원함

    ---------------------------------------------------------------------------
    ### Structure
    - Suffix_check: 확장자 검증 및 수정
    - Read_from: 파일 확장자에 따라 읽기 처리
    - Write_to: 파일 확장자에 따라 쓰기 처리
    - Make_the_file_group: 파일을 일정 간격으로 묶어 디렉토리 구성
    """
    @staticmethod
    def Suffix_check(path: Path, ext: list[str] | str, is_fix: bool = True):
        """ ### 파일 경로의 확장자를 확인하고 조건에 따라 수정

        ------------------------------------------------------------------
        ### Args
        - path: 검사할 파일 경로
        - ext: 허용되는 확장자 목록 또는 문자열
        - is_fix: 확장자 불일치 시 자동 수정 여부

        ### Returns
        - Tuple[bool, Path]: 일치 여부 및 (수정된) 파일 경로
        """
        _ext = ext if isinstance(ext, list) else [ext]
        if path.suffix in _ext:
            return True, path

        return False, path.with_suffix(_ext[0]) if is_fix else path

    @staticmethod
    def Read_from(file: Path, enc: str = "UTF-8", **kwarg) -> tuple[bool, Any]:
        """ ### 파일 확장자에 따라 알맞은 읽기 메서드 호출

        확장자에 따라 Process 모듈 내 적절한 클래스를 찾아 읽기 수행

        ------------------------------------------------------------------
        ### Args
        - file: 읽을 파일 경로
        - enc: 인코딩 방식
        - kwarg: 확장 키워드 인자

        ### Returns
        - Any: 파일에서 읽어온 데이터

        ### Raises
        - ValueError: 파일 확장자 미지원 또는 파일이 아님
        """
        if Path.is_file(file):
            _suffix: str = file.suffix
            _name = _suffix[1:].capitalize()

            if hasattr(Process, _name):
                _method: Process.File_Process = getattr(Process, _name)
                return _method.Read_from(file, enc, **kwarg)

            raise ValueError(f"File extension '{_suffix}' is not supported")
        raise ValueError(f"!!! This path {file} is not FILE !!!")

    @staticmethod
    def Write_to(
        file: Path, data: Any, enc: str = "UTF-8",
        **kwarg
    ):
        """ ### 파일 확장자에 따라 파일로 저장 처리

        파일 확장자에 따라 .json, .yaml, .txt 형식으로 자동 구분하여 저장함

        ------------------------------------------------------------------
        ### Args
        - file: 저장할 파일 경로
        - data: 저장할 데이터
        - enc: 인코딩 방식
        - kwarg: 확장 키워드 인자

        ### Returns
        - None

        ### Raises
        - ValueError: 지원되지 않는 파일 확장자
        """
        _suffix: str = file.suffix
        _name = _suffix[1:].capitalize()

        if hasattr(Process, _name):
            getattr(Process, _name).Write_to(file, data, enc, **kwarg)
        else:
            raise ValueError(
                f"File extension '{_suffix}' is not supported for writing."
            )

    @staticmethod
    def Make_the_file_group(
        file_dir: Path, save_dir: Path,
        keyword: str, size: int, stride: int, overlap: int,
        drop_last: bool = False
    ):
        """ ### 지정된 크기와 간격으로 파일을 묶어 디렉토리 그룹을 생성

        ------------------------------------------------------------------
        ### Args
        - file_dir: 원본 파일들이 존재하는 디렉토리
        - save_dir: 묶은 파일을 저장할 디렉토리
        - keyword: glob 패턴 필터링 키워드
        - size: 그룹 당 파일 개수
        - stride: 슬라이딩 윈도우 간격
        - overlap: 그룹 간 겹침 개수
        - drop_last: 마지막 그룹의 부족 파일 제거 여부

        ### Returns
        - None (그룹 디렉토리 생성 후 파일 복사 수행)
        """
        _range = size * stride
        _step = stride * (size - overlap)

        _file_list = sorted(file_dir.glob(keyword))
        save_dir.mkdir(exist_ok=True)

        if len(_file_list) % _step:
            _group_ct = (len(_file_list) // _step) + int(not drop_last)
        else:
            _group_ct = len(_file_list) // _step

        for _ct in range(_group_ct):
            _new_rgb_dir = save_dir / f"{_ct:0>5d}"
            _new_rgb_dir.mkdir(exist_ok=True)

            _st = _ct * _step
            _ed = _st + _range

            for _img_file in _file_list[_st:_ed:stride]:
                copyfile(_img_file, _new_rgb_dir / _img_file.name)
