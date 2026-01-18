""" ### 시스템 및 문자열 유틸리티, OS 처리, 시간 계산 등을 포함한 도구 모음

이 모듈은 Python 환경에서 자주 사용하는 기능들을 클래스 기반으로 구성합니다.
운영체제 구분, 문자열 정렬 및 포맷팅, 시간 관련 변환, 서버 연결 인터페이스 등을
제공합니다.

---------------------------------------------------------------------------
### Requirement
    - Python >= 3.10
    - numpy
    - scipy (Rotation 모듈 사용 시)
    - dateutil (relativedelta)

### Structure
    - String
        - 문자열 포맷팅, 길이 정렬, 진행바 등 처리 유틸리티 클래스
        - 하위: String_Enum (StrEnum 기반 enum 확장)
    - Operating_System
        - 현재 운영체제 확인 및 열거형 정의
    - Server
        - 서버 연결 상태 관리 및 OS 기반 처리 분기
    - Time_Utils
        - 현재 시간 생성, 포맷 변환, 시간 간격 계산 기능 제공
        - 하위: Relative (상대적 시간 정보를 저장하는 dataclass)
"""

from __future__ import annotations
from enum import StrEnum, auto
from typing import (Tuple, Literal, TypeVar)

from dataclasses import dataclass

import sys
import platform
from os import get_terminal_size

# from pathlib import Path

from datetime import datetime, date, time, timezone
from dateutil.relativedelta import relativedelta


# -- DEFINE CONSTNAT -- #
# Data type for hint
NUMBER = TypeVar("NUMBER", bound=int | float)

# System Constant
PYTHON_VERSION = sys.version_info


class String():
    """ ### 문자열 처리와 변환 관련 유틸리티 함수 모음
    문자열 정렬, 변환, 출력 포맷 지정 등에 활용되는 기능 제공

    ---------------------------------------------------------------------------
    ### Structure
    - Count_auto_align: 숫자 정렬 문자열 생성
    - Str_adjust: 문자열 길이 조정
    - Progress_bar: 터미널 진행바 출력
    - String_Enum: 문자열로 출력되는 열거형 클래스
    """
    @staticmethod
    def Count_auto_align(
        value: int, max_count: int, is_right: bool = True, fill: str = "0"
    ):
        """ ### 숫자를 정렬하여 문자열 형태로 반환

        ------------------------------------------------------------------
        ### Args
        - value: 출력할 숫자 값
        - max_count: 최대 숫자 (전체 자리수 기준)
        - is_right: 오른쪽 정렬 여부
        - filler: 채울 문자

        ### Returns
        - str: 정렬된 문자열 (예: "003/100")
        """
        if is_right:
            return f"{str(value).rjust(len(str(max_count)), fill)}/{max_count}"
        return f"{str(value).ljust(len(str(max_count)), fill)}/{max_count}"

    @staticmethod
    def Str_adjust(
        text: str,
        max_length: int,
        fill: str = " ",
        align: Literal["l", "c", "r"] = "r"
    ) -> Tuple[int, str]:
        """ ### 문자열을 지정된 길이에 맞춰 정렬

        한글 등 멀티바이트 문자를 너비 2로 간주하여 시각적 길이를 계산합니다.

        ------------------------------------------------------------------
        ### Args
        - text: 입력 문자열
        - max_length: 최대 길이
        - fill: 채움 문자
        - align: 정렬 방향 ("l", "c", "r")

        ### Returns
        - Tuple[int, str]: 초과 길이, 정렬된 문자열
        """
        # 참고: 이 방식은 터미널 환경에 따라 정확하지 않을 수 있습니다.
        # 보다 정확한 계산이 필요하면 wcwidth 라이브러리 사용을 권장합니다.
        visual_width = 0
        for char in text:
            # 간단한 휴리스틱: encode 결과가 isalpha와 다르면 멀티바이트로 간주
            if char.encode().isalpha() != char.isalpha():
                visual_width += 2
            else:
                visual_width += 1

        padding_size = max_length - visual_width
        if padding_size < 0:
            return -padding_size, text

        if align == "l":
            return 0, text + fill * padding_size
        if align == "c":
            left_padding = padding_size // 2
            right_padding = padding_size - left_padding
            return 0, fill * left_padding + text + fill * right_padding
        # align == 'r'
        return 0, fill * padding_size + text

    @staticmethod
    def Progress_bar(
        iteration: int, total: int,
        prefix: str = '', suffix: str = '',
        decimals: int = 1, fill: str = '█'
    ):
        """ ### 반복문 내에서 사용할 터미널 진행 표시 바 출력

        ------------------------------------------------------------------
        ### Args
        - iteration: 현재 반복 횟수
        - total: 전체 반복 횟수
        - prefix: 진행바 앞에 붙는 문자열
        - suffix: 진행바 뒤에 붙는 문자열
        - decimals: 퍼센트 표시 소수점 자리수
        - fill: 진행바 채움 문자
        """
        _percentage = iteration / float(total)
        _str_p = ("{0:." + str(decimals) + "f}").format(100 * _percentage)

        _bias = len(prefix + _str_p + suffix) + 6
        _bar_l = get_terminal_size().columns - _bias
        _fill_l = round(_bar_l * _percentage)
        _str_b = fill * _fill_l + '-' * (_bar_l - _fill_l)

        print(f'\r{prefix} |{_str_b}| {_str_p}% {suffix}', end="\r")
        # Print New Line on Complete
        if iteration == total:
            print()

    class String_Enum(StrEnum):
        """ ### 문자열로 출력되는 열거형 클래스

        ------------------------------------------------------------------
        """
        def __repr__(self) -> str:
            return self.name.lower()


class Operating_System():
    """ ### 운영체제(OS) 관련 정보 및 조건 처리 유틸리티 클래스

    --------------------------------------------------------------------
    ### Structure
    - Name: 운영체제 이름 열거형
    - Matches_os: 현재 OS가 입력된 OS와 일치하는지 확인
    """

    THIS_STYLE = platform.system().lower()

    class Name(String.String_Enum):
        """
        각 OS 별 처리 문자열
        ----------------------------------------------------------------
        """
        WINDOW = auto()
        LINUX = auto()

    @staticmethod
    def Matches_os(name: Operating_System.Name | str = "window"):
        """ ### 현재 OS가 지정된 OS와 일치하는지 확인

        ------------------------------------------------------------------
        ### Args
        - os_name: 비교 대상이 되는 OS 이름 (문자열 또는 Enum)

        ### Returns
        - bool: 현재 OS와 비교 대상 OS가 일치하면 True
        """
        return Operating_System.THIS_STYLE == name


class Server():
    """ ### 서버 연결 관련 기능을 제공하는 클래스

    운영체제 정보에 따라 연결 로직을 분기할 수 있도록 설계됨

    ------------------------------------------------------------------
    ### Attributes
    - is_window: 현재 실행 환경이 Windows 운영체제인지 여부

    ### Structure
    - Connect_to: 서버에 연결을 시도하는 메서드 (미구현)
    - Disconnect_to: 서버 연결을 종료하는 메서드 (미구현)
    """
    is_window: bool = Operating_System.Matches_os()

    @classmethod
    def Connect_to(cls):
        """ ### 서버 연결을 초기화하는 메서드 (미구현)
        ------------------------------------------------------------------
        ### Raises
        - NotImplementedError: 해당 기능은 아직 구현되지 않음
        """
        # TODO:
        raise NotImplementedError

    @classmethod
    def Disconnect_to(cls):
        """ ### 서버 연결을 종료하는 메서드 (미구현)
        ------------------------------------------------------------------
        ### Raises
        - NotImplementedError: 해당 기능은 아직 구현되지 않음
        """
        # TODO:
        raise NotImplementedError


class Time_Utils():
    """ ### 시간 관련 유틸리티 기능을 제공하는 클래스

    현재 시각 생성, 시각 차이 계산, 포맷 변환 등의 기능을 포함함

    ---------------------------------------------------------------------------
    ### Structure
    - Stamp: 현재 시각을 timezone 정보와 함께 반환
    - Get_term: 기준 시각으로부터의 시간 차이 계산
    - Make_text_from: datetime 객체를 문자열로 변환
    - Make_time_from: 문자열을 datetime 객체로 변환
    """
    @staticmethod
    def Stamp(set_timezone: timezone | None = None):
        """ ### 현재 시간 정보를 반환

        ------------------------------------------------------------------
        ### Args
        - set_timezone: 반환될 datetime에 적용할 timezone 객체 (기본값: None)

        ### Returns
        - datetime: 현재 시각 객체
        """
        return datetime.now(set_timezone)

    @staticmethod
    def Get_term(
        standard_time: datetime, set_timezone: timezone | None = None
    ):
        """ ### 기준 시간으로부터의 경과 시간 계산

        ------------------------------------------------------------------
        ### Args
        - standard_time: 기준 시간 (datetime 객체)
        - set_timezone: 현재 시각 기준 timezone (기본값: None)

        ### Returns
        - timedelta: 기준 시간으로부터의 시간 차이
        """
        return Time_Utils.Stamp(set_timezone) - standard_time

    @staticmethod
    def Make_text_from(
        src: datetime | date | time | None = None, d_fmt: str | None = None
    ):
        """ ### 날짜/시간 객체를 문자열로 변환

        ------------------------------------------------------------------
        ### Args
        - src: 변환할 시간 객체 (기본값: 현재 시각)
        - d_fmt: 문자열 포맷 지정 (기본값: ISO 8601)

        ### Returns
        - str: 포맷된 날짜/시간 문자열
        """
        _time = Time_Utils.Stamp() if src is None else src
        if d_fmt is None:
            return _time.isoformat()
        return _time.strftime(d_fmt)

    @staticmethod
    def Make_time_from(
        src: str, d_fmt: str | None = None,
        use_microsec: bool = False,
        use_timezone: bool = False
    ):
        """ ### 문자열을 datetime 객체로 변환

        ISO 8601 또는 지정된 포맷 문자열을 기반으로 변환함

        ------------------------------------------------------------------
        ### Args
        - src: 변환 대상 문자열
        - d_fmt: 수동 지정 포맷 문자열 (기본값: None → ISO)
        - use_microsec: ISO 포맷 사용 시 마이크로초 포함 여부
        - use_timezone: ISO 포맷 사용 시 timezone 포함 여부

        ### Returns
        - datetime: 파싱된 datetime 객체

        ### Raises
        - ValueError: 포맷이 일치하지 않을 경우 발생
        """
        if d_fmt is not None:
            _date_format = d_fmt
        else:  # iso
            _date_format = "%Y-%m-%dT%H:%M:%S"
            _date_format += ".%f" if use_microsec else ""
            _date_format += "%z" if use_timezone else ""

        _datetime = datetime.strptime(src, _date_format)
        return _datetime

    @dataclass
    class Relative():
        """ ### relativedelta를 쉽게 다루기 위한 데이터 클래스
        """
        years: int = 0
        months: int = 0
        weeks: int = 0
        days: int = 0
        hours: int = 0
        minutes: int = 0
        seconds: int = 0
        microseconds: int = 0

        @classmethod
        def from_delta(cls, delta: relativedelta) -> Time_Utils.Relative:
            """ relativedelta 객체로부터 Relative 인스턴스를 생성합니다. """
            return cls(
                years=delta.years,
                months=delta.months,
                weeks=delta.weeks,
                days=delta.days,
                hours=delta.hours,
                minutes=delta.minutes,
                seconds=delta.seconds,
                microseconds=delta.microseconds
            )

        def to_delta(self) -> relativedelta:
            """ Relative 인스턴스를 relativedelta 객체로 변환합니다. """
            return relativedelta(
                years=self.years,
                months=self.months,
                weeks=self.weeks,
                days=self.days,
                hours=self.hours,
                minutes=self.minutes,
                seconds=self.seconds,
                microseconds=self.microseconds
            )
