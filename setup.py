"""setup.py"""
from setuptools import setup, find_packages

setup(
    name="pychart",
    version="0.1.0",
    author="Your Name",
    description="Code Hierarchy & Architecture Rendering Tool (Python)",
    # pychart 및 하위 패키지(form 등)를 자동 탐색
    packages=find_packages(include=["pychart", "pychart.*"]),
    python_requires=">=3.9",
    # 외부 패키지 의존성이 있다면 여기에 추가 (현재는 표준 라이브러리만 사용하므로 비움)
    install_requires=[],
    entry_points={
        "console_scripts": [
            # 터미널에서 'pychart' 입력 시 -> pychart.printer 모듈의 cli_main 함수 실행
            "pychart=pychart.printer:cli_main",
        ],
    },
)