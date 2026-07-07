"""analysis 공통 구조 — 데이터타입별 분석을 같은 포맷으로 호출·처리한다.

process/pipeline 과 동일하게 ``python_toolbox`` 의 :class:`Registry` 로 등록한다. 각 분석은
:class:`Analysis` 의 서브클래스로, staticmethod 세 관례를 제공한다:

    analyze(**params) -> result        # 순수 계산 (입력 파라미터는 분석마다 다름)
    format_report(result) -> str       # 텍스트 표현
    build_figure(result) -> Figure     # 시각화

레지스트리에 등록하면 CLI/GUI 가 이름으로 찾아 균일하게 **호출**(analyze)하고 **처리**
(:func:`present` 로 report·figure 저장·표시)한다. 만능 함수가 아니라 '같은 모양의 진입점'을
모으는 것 — 분석별 입력 파라미터는 각 패키지가 책임진다.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar, TYPE_CHECKING

from python_toolbox.registry import Registry

if TYPE_CHECKING:
    from matplotlib.figure import Figure


class Analysis:
    """데이터타입별 분석의 공통 진입점 베이스 (서브클래스가 staticmethod 3개를 제공)."""

    name:        ClassVar[str] = ""
    description: ClassVar[str] = ""

    @staticmethod
    def analyze(**params: Any) -> Any:          # (**params) -> result
        raise NotImplementedError

    @staticmethod
    def format_report(result: Any) -> str:      # result -> text
        raise NotImplementedError

    @staticmethod
    def build_figure(result: Any) -> "Figure":  # result -> matplotlib Figure
        raise NotImplementedError


ANALYSIS_REGISTRY = Registry[type]("analysis", Analysis)


def Get(name: str) -> type[Analysis]:
    """이름으로 분석 클래스를 찾는다."""
    return ANALYSIS_REGISTRY.Get(name, Analysis)


def Available() -> list[str]:
    """등록된 분석 이름 목록."""
    return sorted(ANALYSIS_REGISTRY._module_dict)


def Run(name: str, **params: Any) -> Any:
    """이름으로 분석을 호출한다 — ``Get(name).analyze(**params)``."""
    return Get(name).analyze(**params)


def present(
    result: Any, analysis: type[Analysis] | ModuleType, out_dir: Path, *,
    prefix: str | None = None, plot: bool = True, show: bool = True,
) -> dict[str, Path]:
    """공통 표현 boilerplate — report txt(+옵션 figure png) 저장·표시.

    분석별 ``__main__`` 이 중복하던 "report 출력→저장→figure 저장→표시"를 한곳으로 모은다.
    ``analysis`` 는 ``format_report``/``build_figure`` 를 노출하는 무엇이든 된다 — :class:`Analysis`
    서브클래스든, 같은 관례를 모듈 함수로 노출한 분석 패키지(예: ``analysis.chroma``)든.
    저장 경로 dict 를 돌려준다 (GUI 는 ``build_figure`` 를 직접 써 canvas 에 임베드해도 된다).
    """
    _prefix = prefix or getattr(analysis, "name", analysis.__name__)
    _txt = analysis.format_report(result)
    print("\n" + _txt + "\n")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _rep = out_dir / f"{_prefix}_report.txt"
    _rep.write_text(_txt, encoding="utf-8")
    print(f"[save] report → {_rep}")
    _saved = {"report": _rep}

    if plot:
        import matplotlib.pyplot as plt
        _fig = analysis.build_figure(result)
        _png = out_dir / f"{_prefix}.png"
        _fig.savefig(_png, dpi=120)
        print(f"[save] figure → {_png}")
        _saved["figure"] = _png
        if show:
            plt.show()
        else:
            plt.close(_fig)
    return _saved
