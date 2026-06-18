"""Config 로부터 Reader 인스턴스를 생성하는 빌더.

Session_config 는 dataloader config yaml 경로만 들고, 실제 reader 조립은 여기서
한다. dataloader config 하나가 데이터 그룹 하나(= reader + 입력 sources)를 정의한다.
"""

from __future__ import annotations

from pathlib import Path

from python_toolbox.file import Make_dict_from

from . import reader_registry
from ._base import FRAME_KEY, Base_Reader, Dataloader_config
from .categorized import Categorized_Reader
from .uncategorized import Raw_Reader


# ── 빌더 ──────────────────────────────────────────────────────────────────────

def Build_reader(config: str | dict) -> Base_Reader:
    """dataloader config(경로 또는 meta dict)로부터 reader 와 sources 를 만든다.

    Args:
        config: dataloader config yaml 경로 또는 meta dict.

    Returns:
        (reader 인스턴스, 입력 source 경로 목록).

    Raises:
        ValueError: 알 수 없는 reader 종류일 때.
    """
    if isinstance(config, str):
        _, _meta = Make_dict_from(Path(config))
    else:
        _meta = config

    _cfg = Dataloader_config(**_meta)
    try:
        return reader_registry.Get(_cfg.object_type)(**_cfg.Extract())
    except KeyError:
        raise ValueError(
            f"알 수 없는 reader: {_cfg.object_type!r} "
        )
