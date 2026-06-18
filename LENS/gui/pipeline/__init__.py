"""Pipeline 탭 패키지 — 파이프라인 저작(빌더)."""

import importlib
import pkgutil

import core.process.batch as _batch_pkg
import core.process.frame as _frame_pkg
import core.process.init as _init_pkg
import core.dataloader as _loader_pkg


def _import_pkg_modules(pkg) -> None:
    for _m in pkgutil.iter_modules(pkg.__path__):
        if not _m.name.startswith("_"):
            importlib.import_module(f"{pkg.__name__}.{_m.name}")


_import_pkg_modules(_frame_pkg)
_import_pkg_modules(_batch_pkg)
_import_pkg_modules(_init_pkg)
_import_pkg_modules(_loader_pkg)


from gui.pipeline._panel import PipelinePanel

__all__ = ["PipelinePanel"]
