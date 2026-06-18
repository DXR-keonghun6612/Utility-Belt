"""Session — 설정 기반 데이터셋 생성 진입점."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from python_toolbox.file import Make_dict_from
from python_toolbox.project import Base_Config, Project_Template

from core.dataloader.build import Build_reader
from core.process.build import Build_process
from core.session.checkpoint import Checkpoint, Hash


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class Session_config(Base_Config):
    """한 번의 데이터셋 생성 실행을 정의하는 설정 객체."""

    project_name: str       = "segment_labeling"
    dataloaders:  list[str] = field(default_factory=list)
    processes:    list[str] = field(default_factory=list)
    checkpoint:   bool      = False
    debug:        bool      = False


# ── Session ───────────────────────────────────────────────────────────────────

class Session(Project_Template):
    """Session_config 를 받아 데이터셋 생성을 실행하는 진입점."""

    def __init__(self, config: Session_config) -> None:
        super().__init__(config.project_name)
        self.config = config
        self._ckpt  = Checkpoint(self.workspace / ".cache")

    def Run(self) -> None:
        _processes = [
            Build_process(Make_dict_from(Path(_p))[1])
            for _p in self.config.processes
        ]
        for _dl_path in self.config.dataloaders:
            _, _dl_meta = Make_dict_from(Path(_dl_path))
            _reader = Build_reader(_dl_meta)
            for _source in _dl_meta.get("sources", []):
                _frames, _id_map = _reader.Load(Path(_source))
                self._Run_pipeline(_frames, _id_map, _processes, _source)

    def _Run_pipeline(
        self, frames, id_map: dict, processes: list, source: str
    ) -> None:
        _n = sum(len(_v) for _v in frames.values())
        print(f"[session] {Path(source).name}: class={len(frames)} frames={_n}")
        if _n == 0:
            print("  [경고] 로드된 프레임 0개 — reader/globs/sources 확인 필요")
            return

        _ctx = {
            "frames":    frames,
            "id_map":    id_map,
            "save_root": str(self.workspace),
            "debug":     self.config.debug,
        }

        for _i, _proc in enumerate(processes):
            if self.config.checkpoint:
                _dir = self._ckpt.Dir(_i, _proc.name, Hash([source, _i]))
                if self._ckpt.Exists(_dir):
                    _ctx.update(self._ckpt.Load(_dir))
                    print(f"  [{_i}] {_proc.name}: 체크포인트 복원")
                    continue

            _result = _proc.Run(**_ctx) or {}
            _ctx.update(_result)

            if self.config.checkpoint:
                self._ckpt.Save(_dir, _result)
