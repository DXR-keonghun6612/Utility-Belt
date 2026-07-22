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

from core import port
from gui._worker import Pipeline_worker
from gui.widgets import List_editor, List_row, Pair_list_editor


# ── glob 편집기 ────────────────────────────────────────────────────────────────

# 등록된 핸들러가 진실원천 — 새 핸들러를 떨구면 여기가 따라온다(하드코딩하면 조용히 뒤처진다).
# 첫 항목 ""(미지정)은 **유효하지 않다** — Convert 가 "type 을 명시하세요"로 실패한다.
# 추론하지 않는 이유: 같은 png 라도 image 일 수도 mask 일 수도 있다.
_GLOB_TYPES = ["", *port.Types()]


# glob 행의 컬럼 규격 — 헤더와 행이 **같은 값**을 써야 정렬이 맞는다 (라벨, 폭(0=stretch), 툴팁).
# 칸은 셋뿐이고 각각 하나의 일만 한다: pattern+ext = 찾기 · type = 핸들러.
_GLOB_COLUMNS = [
    ("종류 (key)", 110, "이 데이터의 이름. **저장 폴더이자 process 가 ctx 에서 읽는 키**가 된다.\n"
                        "예: frame → modified/frame/{stem}.png · flow 의 process 가 `frame` 으로 받는다."),
    ("stem 패턴",    0, "raw 파일을 찾을 패턴 (확장자 없이). `*` 자리가 stem 이 된다.\n"
                        "예: *_rgb + png → '*_rgb.png' 를 찾고, 20260508_rgb.png 의 stem 은 20260508.\n"
                        "선언한 종류를 **다 갖춘 stem 만** 들인다."),
    ("확장자",      70, "**소스 파일의 확장자** — 패턴과 합쳐 glob 한다 (*_rgb + png → *_rgb.png).\n"
                        "저장 확장자도 이걸 따라간다(ingest 는 복사이지 변환이 아니다).\n"
                        "패턴에 이미 확장자를 썼다면 비워둔다."),
    ("type",       92, "핸들러 — **필수**. 확장자로 추론하지 않는다:\n"
                        "같은 png 라도 image(색 이미지)일 수도 mask(객체 마스크)일 수도 있다.\n"
                        "attr = 파일을 안 남기고 텍스트를 값으로 읽는다."),
]


class _Glob_row(List_row):
    """glob key 한 개를 편집하는 행 — ``종류 | stem 패턴 | 확장자 | type | ✕``.

    **확장자 칸은 하나뿐이다.** 예전엔 `format`(서술자 detail)이 확장자처럼 보이는 자리에 나란히 있어
    "확장자는 여기" 로 읽혔고, 그 바람에 패턴이 아무것도 못 찾아 **조용히 0건**이 났다. ingest 는
    **복사이지 변환이 아니라서** 저장 확장자를 따로 정할 이유가 없다 — 소스를 따라간다.

    **저장 위치를 정하는 칸도 없다** — 경로는 트리 위치에서 파생된다(kind-major: 종류 key 가 곧 폴더).
    """

    def __init__(self, key: str = "", spec=None, parent=None) -> None:
        super().__init__(parent)
        _spec = self._normalize(spec)
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(4)

        self._key = QLineEdit(key)
        self._key.setPlaceholderText("frame")
        self._pattern = QLineEdit(str(_spec.get("pattern", "")))
        self._pattern.setPlaceholderText("*_rgb")
        self._ext = QLineEdit(str(_spec.get("ext", "")))
        self._ext.setPlaceholderText("png")
        self._type = QComboBox()
        self._type.addItems(_GLOB_TYPES)                  # registry 가 진실원천 (하드코딩 아님)
        self._type.setCurrentText(str(_spec.get("type", "")))

        for _w, (_label, _width, _tip) in zip(
                (self._key, self._pattern, self._ext, self._type), _GLOB_COLUMNS):
            _w.setToolTip(_tip)
            if _width:
                _w.setFixedWidth(_width)
                _lay.addWidget(_w)
            else:
                _lay.addWidget(_w, stretch=1)
        _lay.addWidget(self._remove_button())

        for _sig in (self._key.textChanged, self._pattern.textChanged,
                     self._ext.textChanged, self._type.currentTextChanged):
            _sig.connect(self.changed)

    @staticmethod
    def _normalize(spec) -> dict:
        """패턴 문자열 또는 dict 를 ``{pattern, ext?, type?}`` dict 로 정규화한다 (죽은 키는 버린다)."""
        if isinstance(spec, dict):
            return spec
        return {"pattern": str(spec or "")}

    def to_config(self) -> tuple[str, object]:
        """``(key, spec dict)`` 로 직렬화한다 (key 가 빈 행은 상위에서 버림).

        빈 칸은 안 싣는다. ``type`` 이 비면 Convert 가 **에러로 알려준다**(조용히 추론하지 않는다).
        옛 레시피의 죽은 키(``format``·``dir``)는 여기서 자연히 떨어져 나간다.
        """
        _key = self._key.text().strip()
        _spec: dict = {"pattern": self._pattern.text().strip()}
        for _field, _w in (("ext", self._ext), ("type", self._type)):
            _val = (_w.currentText() if isinstance(_w, QComboBox) else _w.text()).strip()
            if _val:
                _spec[_field] = _val
        return _key, _spec


class _Glob_list_editor(List_editor):
    """``key → {pattern, ext?, type}`` glob 맵을 행 단위로 편집한다 (컬럼 헤더 포함).

    행 수명·dict 직렬화(``to_config``/``load``)는 ``List_editor`` 베이스가 갖고, 여기선 행 타입과
    컬럼 규격만 지정한다.
    """

    def __init__(self, parent=None) -> None:
        super().__init__("+ glob 추가", parent, headers=_GLOB_COLUMNS)

    def _make_row(self, key, spec) -> List_row:
        return _Glob_row(key, spec)


# ── params 편집기 ─────────────────────────────────────────────────────────────

_PARAM_COLUMNS = [
    ("종류 (key)", 110, "dataset-wide 값의 이름 (예: roi · id_map). 범주에 안 속하고 stem 축도 없다."),
    ("파일 경로",    0, "glob 이 아니라 **단일 파일 경로**다 (프레임마다 있는 게 아니므로)."),
    ("type",       92, "핸들러 — **필수**. 확장자로 추론하지 않는다:\n"
                        "같은 png 라도 image 일 수도 mask 일 수도 있다."),
]


class _Param_row(List_row):
    """dataset-wide 파일 한 개 — ``종류 | 경로 | type | 📁 | ✕``.

    glob 과 **같은 계약**이다(``{pattern, type}``) — 다만 ``pattern`` 이 패턴이 아니라 단일 경로다.
    """

    def __init__(self, key: str = "", spec=None, parent=None) -> None:
        super().__init__(parent)
        _spec = spec if isinstance(spec, dict) else {"pattern": str(spec or "")}
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(4)

        self._key = QLineEdit(key)
        self._key.setPlaceholderText("roi")
        self._path = QLineEdit(str(_spec.get("pattern", "")))
        self._path.setPlaceholderText("/path/to/roi.png")
        self._type = QComboBox()
        self._type.addItems(_GLOB_TYPES)
        self._type.setCurrentText(str(_spec.get("type", "")))

        for _w, (_label, _width, _tip) in zip(
                (self._key, self._path, self._type), _PARAM_COLUMNS):
            _w.setToolTip(_tip)
            if _width:
                _w.setFixedWidth(_width)
                _lay.addWidget(_w)
            else:
                _lay.addWidget(_w, stretch=1)

        _browse = QToolButton()
        _browse.setText("📁")
        _browse.clicked.connect(self._browse)
        _lay.addWidget(_browse)
        _lay.addWidget(self._remove_button())

        for _sig in (self._key.textChanged, self._path.textChanged,
                     self._type.currentTextChanged):
            _sig.connect(self.changed)

    def _browse(self) -> None:
        _p, _ = QFileDialog.getOpenFileName(self, "dataset-wide 파일 선택")
        if _p:
            self._path.setText(_p)

    def to_config(self) -> tuple[str, object]:
        _spec: dict = {"pattern": self._path.text().strip()}
        _t = self._type.currentText().strip()
        if _t:
            _spec["type"] = _t
        return self._key.text().strip(), _spec


class _Param_list_editor(List_editor):
    """``key → {pattern(경로), type}`` params 맵 (컬럼 헤더 포함)."""

    def __init__(self, parent=None) -> None:
        super().__init__("+ params 추가", parent, headers=_PARAM_COLUMNS)

    def _make_row(self, key, spec) -> List_row:
        return _Param_row(key, spec)


# ── 타입별 설정 위젯 ──────────────────────────────────────────────────────────

class _Glob_settings(QWidget):
    """glob ingest(``converter.Ingest``) 전용 설정 위젯.

    sources(디렉터리 목록) · globs(key→{pattern,type?,format?}) · params(key→경로)를
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
