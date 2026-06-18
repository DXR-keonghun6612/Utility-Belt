"""Config로부터 Process 인스턴스를 생성하는 빌더."""

from __future__ import annotations

from pathlib import Path

from python_toolbox.file import Make_dict_from

from .. import config_registry
from ._base import Base_Process
from . import pipeline_registry


def Build_process(config: str | dict) -> Base_Process:
    """Config 인스턴스로부터 대응하는 Process를 생성한다.

    Process(Config, Base_Process) 구조이므로 config 필드를 그대로 전달한다.
    config.object_type → pipeline_registry 조회.

    Args:
        config: Process_config 서브클래스 인스턴스.

    Returns:
        대응하는 Process 인스턴스.
    """
    if isinstance(config, str):
        _file_name = Path(config)
        if not _file_name.exists():
            if config in pipeline_registry._module_dict:
                return pipeline_registry.Get(config)()
            raise ValueError(f"Unknown process or missing file: {config!r}")
        _, _cfg_meta = Make_dict_from(_file_name)
    else:
        _cfg_meta = config

    if "config_type" not in _cfg_meta:
        raise ValueError

    _cfg = config_registry.Get(_cfg_meta["config_type"])(**_cfg_meta)
    return pipeline_registry.Get(_cfg.object_type)(**_cfg.Extract())
