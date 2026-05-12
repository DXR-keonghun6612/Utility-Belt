"""setup.py"""
from setuptools import setup, find_packages

setup(
    name="pychart",
    version="0.2.0",
    author="keong-hun, choi",
    description="Code Hierarchy & Architecture Rendering Tool",
    packages=find_packages(include=["core", "core.*", "pychart", "pychart.*", "cchart", "cchart.*"]),
    python_requires=">=3.11",
    install_requires=[
        "python_toolbox @ git+https://github.com/DXR-keonghun6612/ToolBox.git@python_toolbox",
    ],
    entry_points={
        "console_scripts": [
            "pychart=pychart.printer:Cli_Main",
            "cchart=cchart.printer:Cli_Main",
        ],
    },
)