"""tasker 레지스트리 — ``{root}/sample/taskers.yaml`` (name → sample config).

폴더(`{root}/sample/{name}/`)만으로는 그 tasker 가 어떤 설정(task·ratios·unit·salt)인지 알 수 없고,
한 task 종류로 여러 tasker 를 만들 수 있어 **이름↔설정 매칭**이 필요하다 — 그 매칭을 한 파일에 둔다.
각 tasker 의 산출물(`Sample_Set`)은 자기 폴더에 사이드카로 영속하고, 여기엔 **레시피(설정)만** 담는다
(store↔recipe 분리는 converter/flow 와 동형).
"""

from __future__ import annotations

from pathlib import Path

from python_toolbox.file import Read_from, Write_to

TASKERS_FILE = "taskers.yaml"   # {root}/sample/ 아래 tasker 레지스트리


def Load_taskers(sample_root: str | Path) -> dict[str, dict]:
    """``{sample_root}/taskers.yaml`` 을 읽어 ``{name: sample config}`` 로 (없거나 깨졌으면 ``{}``)."""
    _p = Path(sample_root) / TASKERS_FILE
    if not _p.exists():
        return {}
    _ok, _d = Read_from(_p)
    return _d if _ok and isinstance(_d, dict) else {}


def Save_taskers(sample_root: str | Path, taskers: dict[str, dict]) -> None:
    """``{name: sample config}`` 를 ``{sample_root}/taskers.yaml`` 에 쓴다 (부모 dir 보장)."""
    _p = Path(sample_root) / TASKERS_FILE
    _p.parent.mkdir(parents=True, exist_ok=True)
    Write_to(_p, taskers)
