"""Converter 탭 패널 — Pipeline.Convert() 설정 UI."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui._worker import Pipeline_worker
from gui.widgets import List_editor, List_row, Pair_list_editor


# ── glob 편집기 ────────────────────────────────────────────────────────────────

_GLOB_TYPES = ["", "image", "array", "attr", "rle"]   # "" = 확장자로 추론(Infer_type)


class _Glob_row(List_row):
    """glob key 한 개를 편집하는 행 — ``key | pattern | type | dir | format | ✕``.

    ``type`` 을 비우면 패턴 확장자로 핸들러를 추론한다(추론 안 되는 txt 등은 명시). 직렬화는
    pattern 만 있으면 패턴 문자열로, 추가 키가 있으면 ``{pattern, type?, dir?, format?}`` dict 로 한다.
    시그널(``changed``/``remove_requested``)은 ``List_row`` 베이스가 갖는다.
    """

    def __init__(self, key: str = "", spec=None, parent=None) -> None:
        super().__init__(parent)
        _spec = self._normalize(spec)
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(4)

        self._key = QLineEdit(key)
        self._key.setPlaceholderText("key")
        self._key.setFixedWidth(120)
        self._pattern = QLineEdit(str(_spec.get("pattern", "")))
        self._pattern.setPlaceholderText("*_pose.png")
        self._type = QComboBox()
        self._type.addItems(_GLOB_TYPES)
        self._type.setCurrentText(str(_spec.get("type", "")))
        self._type.setToolTip("비우면 확장자로 추론 · txt 등 추론 안 되는 건 명시")
        self._dir = QLineEdit(str(_spec.get("dir", "")))
        self._dir.setPlaceholderText("dir")
        self._dir.setFixedWidth(80)
        self._dir.setToolTip("저장 디렉토리명 오버라이드 (선택)")
        self._format = QLineEdit(str(_spec.get("format", "")))
        self._format.setPlaceholderText("fmt")
        self._format.setFixedWidth(56)

        _rm = self._remove_button()

        for _w, _stretch in ((self._key, 0), (self._pattern, 1), (self._type, 0),
                             (self._dir, 0), (self._format, 0)):
            _lay.addWidget(_w, stretch=_stretch)
        _lay.addWidget(_rm)

        self._key.textChanged.connect(self.changed)
        self._pattern.textChanged.connect(self.changed)
        self._type.currentTextChanged.connect(self.changed)
        self._dir.textChanged.connect(self.changed)
        self._format.textChanged.connect(self.changed)

    @staticmethod
    def _normalize(spec) -> dict:
        """패턴 문자열 또는 dict 를 ``{pattern, type?, dir?, format?}`` dict 로 정규화한다."""
        if isinstance(spec, dict):
            return spec
        return {"pattern": str(spec or "")}

    def to_config(self) -> tuple[str, object]:
        """``(key, 패턴 문자열 또는 spec dict)`` 로 직렬화한다 (key가 빈 행은 상위에서 버림).

        type/dir/format 이 모두 비면 패턴 문자열만, 하나라도 있으면 dict 로 낸다.
        """
        _key = self._key.text().strip()
        _pattern = self._pattern.text().strip()
        _extra = {_k: _v for _k, _v in (
            ("type",   self._type.currentText().strip()),
            ("dir",    self._dir.text().strip()),
            ("format", self._format.text().strip()),
        ) if _v}
        if not _extra:
            return _key, _pattern
        return _key, {"pattern": _pattern, **_extra}


class _Glob_list_editor(List_editor):
    """``key → {pattern, type?, dir?, format?}`` glob 맵을 행 단위로 편집한다.

    행 수명·dict 직렬화(``to_config``/``load``)는 ``List_editor`` 베이스가 갖고, 여기선 행 타입만
    지정한다.
    """

    def __init__(self, parent=None) -> None:
        super().__init__("+ glob 추가", parent)

    def _make_row(self, key, spec) -> List_row:
        return _Glob_row(key, spec)


# ── 타입별 설정 위젯 ──────────────────────────────────────────────────────────

class _Glob_settings(QWidget):
    """``Raw_source``(glob 발견) 전용 설정 위젯.

    sources(디렉터리 목록) · globs(key→{pattern,type?,dir?,format?}) · params(key→경로)를
    편집한다. glob key 마다 ``type`` 으로 핸들러가 갈리며, 특수 취급되는 key 는 없다.

    Attributes:
        changed: 입력이 바뀔 때 emit하는 시그널.
    """

    changed = Signal()

    def __init__(self, parent=None) -> None:
        """설정 위젯을 구성한다.

        Args:
            parent: 부모 위젯.
        """
        super().__init__(parent)
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(0)

        # ── 상단: Sources ─────────────────────────────────────────────────────
        _src_box = QGroupBox("Sources")
        _src_lay = QVBoxLayout(_src_box)
        _src_lay.setSpacing(4)
        self._sources = QListWidget()
        self._sources.setMinimumHeight(60)
        self._sources.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        _src_lay.addWidget(self._sources, stretch=1)
        _src_btns = QHBoxLayout()
        _add_src = QPushButton("+ 디렉터리")
        _add_src.clicked.connect(self._add_source)
        _del_src = QPushButton("− 삭제")
        _del_src.clicked.connect(self._remove_source)
        _src_btns.addWidget(_add_src)
        _src_btns.addWidget(_del_src)
        _src_btns.addStretch()
        _src_lay.addLayout(_src_btns)

        # ── 하단: Globs | Params ──────────────────────────────────────────────
        _bottom_split = QSplitter(Qt.Orientation.Horizontal)

        _glob_box = QGroupBox("Globs")
        _glob_lay = QVBoxLayout(_glob_box)
        _glob_lay.setSpacing(4)
        self._globs = _Glob_list_editor()
        self._globs.changed.connect(self.changed)
        _glob_lay.addWidget(self._globs, stretch=1)
        _bottom_split.addWidget(_glob_box)

        _param_box = QGroupBox("Params")
        _param_lay = QVBoxLayout(_param_box)
        _param_lay.setSpacing(4)
        self._params = Pair_list_editor("", kind="path")
        self._params.changed.connect(self.changed)
        _param_lay.addWidget(self._params, stretch=1)
        _bottom_split.addWidget(_param_box)

        _bottom_split.setStretchFactor(0, 1)
        _bottom_split.setStretchFactor(1, 2)
        _bottom_split.setSizes([190, 380])

        _vsplit = QSplitter(Qt.Orientation.Vertical)
        _vsplit.addWidget(_src_box)
        _vsplit.addWidget(_bottom_split)
        _vsplit.setStretchFactor(0, 1)
        _vsplit.setStretchFactor(1, 2)
        _vsplit.setSizes([120, 260])
        _lay.addWidget(_vsplit, stretch=1)

    def _add_source(self) -> None:
        _d = QFileDialog.getExistingDirectory(self, "소스 디렉터리 추가")
        if _d:
            self._sources.addItem(_d)
            self.changed.emit()

    def _remove_source(self) -> None:
        for _it in self._sources.selectedItems():
            self._sources.takeItem(self._sources.row(_it))
        self.changed.emit()

    def to_config(self) -> dict:
        """현재 설정을 converter 본문 dict로 직렬화한다.

        Returns:
            ``sources`` / ``globs`` (+비어있지 않으면 ``params``) dict.
        """
        _sources = [
            self._sources.item(_i).text()
            for _i in range(self._sources.count())
        ]
        _params = dict(self._params.pairs())
        _cfg: dict = {
            "sources": _sources,
            "globs":   self._globs.to_config(),
        }
        if _params:
            _cfg["params"] = _params
        return _cfg

    def load(self, d: dict) -> None:
        """converter 본문 dict로 설정 위젯을 복원한다.

        Args:
            d: ``to_config`` 형식의 dict.
        """
        self._sources.clear()
        for _s in d.get("sources", []) or []:
            self._sources.addItem(str(_s))
        self._globs.load(d.get("globs") or {})
        self._params.set_pairs(list((d.get("params") or {}).items()))


# 새 converter 타입 추가 시 이 dict에 등록
_CONVERTER_WIDGETS: dict[str, type[QWidget]] = {
    "glob": _Glob_settings,
}


# ── Converter_panel ───────────────────────────────────────────────────────────

class Converter_panel(QWidget):
    """Converter 탭 — ``Pipeline.Convert()`` 설정 UI.

    타입별 설정 위젯을 콤보로 전환하고 ``to_config()`` 로 ``{"converter": {...}}`` 를 직렬화한다.
    콤보·상태 라벨·Convert 버튼은 패널이 소유하되 배치는 호스트가 ``format_combo()`` 등으로 가져간다.
    새 타입: ``_CONVERTER_WIDGETS["my_type"] = _My_settings``.

    Attributes:
        changed: 설정 변경 시 emit.
        convert_done: ``Convert()`` 완료 시 emit (page 가 meta 뷰 갱신).
    """

    changed       = Signal()
    convert_done  = Signal()    # Convert() 완료 → page 가 meta 뷰 갱신

    def __init__(self, get_pipeline: Callable[[], object | None], parent=None) -> None:
        """Args:
        get_pipeline: 보유 ``Pipeline`` 을 돌려주는 콜백 — 편집한 converter 를 주입해 그 위에서 Convert.
        """
        super().__init__(parent)
        self._get_pipeline = get_pipeline
        self._thread: QThread | None = None
        self._worker: Pipeline_worker | None = None
        self._build()

    def _build(self) -> None:
        _lay = QVBoxLayout(self)
        _lay.setContentsMargins(6, 6, 6, 6)
        _lay.setSpacing(4)

        # 첫 줄/하단 위젯은 패널이 소유(상태관리)하되 배치는 호스트(다이얼로그)가 한다:
        # datasource_format 콤보(설정 스택 전환) · 상태 라벨 · Convert 실행 버튼.
        self._type_combo = QComboBox()
        self._type_combo.addItems(list(_CONVERTER_WIDGETS))
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        self._status_lbl = QLabel("")
        self._run_btn = QPushButton("Convert ▶")
        self._run_btn.clicked.connect(self._on_convert)

        # 타입별 설정 스택
        self._stack = QStackedWidget()
        self._settings_widgets: dict[str, QWidget] = {}
        for _name, _cls in _CONVERTER_WIDGETS.items():
            _w = _cls()
            _w.changed.connect(self.changed)  # type: ignore[attr-defined]
            self._stack.addWidget(_w)
            self._settings_widgets[_name] = _w
        _lay.addWidget(self._stack, stretch=1)

    # ── 내부 동작 ─────────────────────────────────────────────────────────────

    def _on_convert(self) -> None:
        if self._thread is not None:
            return
        _pipe = self._get_pipeline()
        if _pipe is None or not str(_pipe.root).strip():
            self._status_lbl.setText("dataset_root 미설정")
            return
        _conv = self.to_config()["converter"]                 # 편집한 converter 섹션
        self._run_btn.setEnabled(False)
        self._status_lbl.setText("변환 중…")

        def _task(_progress) -> None:                          # 보유 Pipeline 에 주입 후 Convert
            _pipe.set_converter(_conv)
            _pipe.Convert()

        self._thread = QThread()
        self._worker = Pipeline_worker(_pipe, _task)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _on_finished(self, ok: bool, info: str) -> None:
        self._status_lbl.setText("완료" if ok else f"실패: {info.splitlines()[-1]}")
        self._run_btn.setEnabled(True)
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        if ok:
            self.convert_done.emit()

    def _on_type_changed(self, name: str) -> None:
        _keys = list(_CONVERTER_WIDGETS)
        if name in _keys:
            self._stack.setCurrentIndex(_keys.index(name))
        self.changed.emit()

    # ── Public API ────────────────────────────────────────────────────────────

    def format_combo(self) -> QComboBox:
        """datasource_format(구 object_type) 콤보 — 호스트가 첫 줄에 배치한다 (설정 스택 전환)."""
        return self._type_combo

    def status_label(self) -> QLabel:
        """변환 상태 라벨 — 호스트가 배치한다 (메시지 갱신은 패널)."""
        return self._status_lbl

    def run_button(self) -> QPushButton:
        """Convert 실행 버튼을 돌려준다 — 호스트가 원하는 위치에 배치한다 (상태관리는 패널)."""
        return self._run_btn

    def to_config(self) -> dict:
        """Pipeline_config 호환 dict 반환.

        Returns:
            {"converter": {"object_type": ..., ...}}
        """
        _type = self._type_combo.currentText()
        _specific = self._settings_widgets[_type].to_config()  # type: ignore[attr-defined]
        _conv: dict = {"object_type": _type, **_specific}
        return {"converter": _conv}

    def load(self, d: dict) -> None:
        """저장된 dict로 패널 복원."""
        _conv = d.get("converter", d) or {}
        _type = _conv.get("object_type", self._type_combo.currentText())
        if _type in _CONVERTER_WIDGETS:
            self._type_combo.setCurrentText(_type)
            self._settings_widgets[_type].load(_conv)  # type: ignore[attr-defined]
