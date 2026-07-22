"""Process step별 출력 라우팅 편집기 — ``outputs`` 한 항목 행 + 규칙 목록 (route spec 은 README)."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit

from gui.widgets import List_editor, List_row


class _Output_row(List_row):
    """``outputs`` 한 항목 편집 행 — ``출력키 | → | to | 위치 | type | 확장자 | ✕`` (route spec 은 README).

    **저장 위치를 정하는 칸은 없다** — 파일 경로는 spec 이 아니라 **트리 위치**(범주·stem·obj_id)와
    출력키에서 파생된다(kind-major: 출력키가 곧 종류 폴더). 그래서 `dir` 같은 칸이 없다.
    """

    def __init__(self, key: str = "", spec: dict | None = None,
                 keys=(), block: bool = False, parent=None) -> None:
        """행을 구성한다.

        Args:
            key: 초기 출력 키.
            spec: 초기 라우팅 스펙 (``to`` / ``level`` / ``type`` / ``format``).
            keys: 키 콤보에 채울 후보(이 process의 OUTPUTS).
            block: True면 finalize/params 레벨 — level 숨김, ``to=meta`` 는 params 를 뜻한다.
            parent: 부모 위젯.
        """
        super().__init__(parent)
        self._block = block
        spec = spec or {}
        _lay = QHBoxLayout(self)
        _lay.setContentsMargins(0, 0, 0, 0)
        _lay.setSpacing(4)

        self._key = QComboBox()
        self._key.setEditable(True)
        self._key.addItems(list(keys))
        self._key.setCurrentText(key)
        self._key.setToolTip(
            "영속할 출력 키 (이 process 의 OUTPUTS 중에서).\n"
            "**여기 선언한 키만 저장된다** — 나머지는 ctx 로만 흐르다 사라진다.\n"
            "저장 폴더 이름도 이 키다 (kind-major).")

        self._to = QComboBox()
        self._to.addItems(["meta", "storage"])
        self._to.setCurrentText(spec.get("to", "meta"))
        self._to.setToolTip(
            "보관 방식 — meta=사이드카에 인라인(스칼라·rle) · storage=별도 파일(image·array)"
            + ("\n(finalize 라 위치가 없다 → dataset-wide params 로 간다)" if block else ""))

        self._level = QComboBox()
        self._level.addItems(["object", "frame"])
        self._level.setCurrentText(spec.get("level", "object"))
        self._level.setToolTip(
            "트리에서 값이 붙을 위치 — object=객체마다 한 개 · frame=프레임에 한 개")

        self._type = QLineEdit(str(spec.get("type", "")))
        self._type.setPlaceholderText("type")
        self._type.setFixedWidth(84)
        self._type.setToolTip(
            "핸들러 (mask·image·array 등) — 비우면 값과 맥락으로 추론한다.\n"
            "추론이 안 되면 조용한 기본값 없이 실패하므로 그때 명시한다.")

        self._format = QLineEdit(str(spec.get("format", "")))
        self._format.setPlaceholderText("png")
        self._format.setFixedWidth(64)
        self._format.setToolTip("저장 확장자 (png·npy 등) — 비우면 핸들러의 기본 확장자")

        _lay.addWidget(self._key, stretch=1)
        _lay.addWidget(QLabel("→"))
        _lay.addWidget(self._to)
        _lay.addWidget(self._level)
        _lay.addWidget(self._type)
        _lay.addWidget(self._format)
        _lay.addStretch(1)
        _lay.addWidget(self._remove_button())

        self._to.currentTextChanged.connect(self._sync_storage_fields)
        self._key.currentTextChanged.connect(self.changed)
        self._to.currentTextChanged.connect(self.changed)
        self._level.currentTextChanged.connect(self.changed)
        self._type.textChanged.connect(self.changed)
        self._format.textChanged.connect(self.changed)
        self._sync_storage_fields()

    def _sync_storage_fields(self) -> None:
        """type·확장자는 storage(파일 저장)일 때만, level 은 finalize/params 가 아닐 때만 의미 있다."""
        _storage = self._to.currentText() == "storage"
        self._type.setVisible(_storage)
        self._format.setVisible(_storage)
        self._level.setVisible(not self._block)

    def set_keys(self, keys) -> None:
        """키 콤보 후보를 갱신한다 (현재 텍스트는 유지).

        Args:
            keys: 새 키 후보 시퀀스.
        """
        _cur = self._key.currentText()
        self._key.blockSignals(True)
        self._key.clear()
        self._key.addItems(list(keys))
        self._key.setCurrentText(_cur)
        self._key.blockSignals(False)

    def to_config(self) -> tuple[str, dict]:
        """행을 ``(출력키, 스펙 dict)`` 로 직렬화한다.

        기본값(``to=meta``, ``level=object``)은 생략하고, ``type``/``format`` 은 storage 일 때만 담는다.

        Returns:
            ``(key, spec)``. key가 비면 상위에서 버려진다.
        """
        _spec: dict = {}
        _to = self._to.currentText()
        if _to != "meta":
            _spec["to"] = _to
        if not self._block and self._level.currentText() != "object":  # finalize/params 는 level 없음
            _spec["level"] = self._level.currentText()
        if _to == "storage":                                # type·확장자는 storage 전용
            _tp = self._type.text().strip()
            if _tp:
                _spec["type"] = _tp
            _fmt = self._format.text().strip()
            if _fmt:
                _spec["format"] = _fmt
        return self._key.currentText().strip(), _spec


class _Outputs_editor(List_editor):
    """한 step 의 ``outputs`` 규칙(행) 목록 편집기 (``List_editor`` 베이스)."""

    def __init__(self, block: bool = False, parent=None) -> None:
        """편집기를 구성한다.

        Args:
            block: True면 finalize/params 레벨 행 — level 숨김, ``to=meta`` 는 params 를 뜻한다.
            parent: 부모 위젯.
        """
        super().__init__("+ 출력 추가", parent)
        self._block = block
        self._keys: tuple[str, ...] = ()

    def set_keys(self, keys) -> None:
        """모든 행의 키 후보를 갱신하고 이후 추가될 행에도 적용한다.

        Args:
            keys: 새 키 후보 시퀀스(이 process의 OUTPUTS).
        """
        self._keys = tuple(keys)
        for _r in self._rows:
            _r.set_keys(self._keys)

    def _make_row(self, key, spec) -> List_row:
        return _Output_row(key, spec if isinstance(spec, dict) else {},
                           self._keys, block=self._block)
