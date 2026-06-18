"""CLI 진입점 — session_config 로 데이터셋 생성 Session 을 실행한다.

GUI(Pipeline 탭) 또는 손으로 작성한 session_config.yaml 을 받아 그대로 실행한다.
dataloaders / processes 항목은 dataloader·process config yaml 경로 목록이며,
상대경로는 session_config.yaml 위치 기준으로 해석한다.

Examples:
    python cli.py config/session_config.yaml
    python cli.py config/session_config.yaml --project-name belt_v2
"""

from __future__ import annotations

import argparse
from pathlib import Path

from python_toolbox.file import Make_dict_from

# 등록 부작용: process / reader 를 레지스트리에 채운다(Build_process/Build_reader 용).
import core.process.frame   # noqa: F401
import core.process.batch   # noqa: F401
import core.process.init    # noqa: F401
from core.session.base import Session, Session_config


def _resolve(base: Path, path: str) -> str:
    """상대경로를 session_config 디렉터리 기준 절대경로로 바꾼다."""
    _p = Path(path)
    return str(_p if _p.is_absolute() else (base / _p))


def Load_session_config(path: Path) -> Session_config:
    """session_config.yaml → Session_config (dataloader/process 경로 해석 포함)."""
    _ok, _meta = Make_dict_from(path)
    if not _ok or not isinstance(_meta, dict):
        raise ValueError(f"session_config 로드 실패: {path}")

    _config = Session_config(**_meta)
    _base = path.parent
    _config.dataloaders = [_resolve(_base, _p) for _p in _config.dataloaders]
    _config.processes   = [_resolve(_base, _p) for _p in _config.processes]
    return _config


def _build_parser() -> argparse.ArgumentParser:
    _p = argparse.ArgumentParser(description="session_config 로 데이터셋 생성")
    _p.add_argument("session_config", type=Path, help="session_config.yaml 경로")
    _p.add_argument("--project-name", default=None, help="project_name 덮어쓰기")
    return _p


def run(args: argparse.Namespace) -> None:
    _config = Load_session_config(args.session_config)
    if args.project_name:
        _config.project_name = args.project_name

    print(f"dataloader {len(_config.dataloaders)}개 · process {len(_config.processes)}단계 실행")
    _session = Session(_config)
    _session.Run()
    print(f"완료 → {_session.workspace}")


def main() -> None:
    run(_build_parser().parse_args())


if __name__ == "__main__":
    main()
