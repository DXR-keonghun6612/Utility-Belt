# (보류) scaffold 프레임워크 추출 + gui 표준화 계획

> 상태: **미실행 / 향후 참고용**. 지금은 첫걸음으로 `UI` 만 `core/dataset` 으로 옮긴 상태.
> 아래는 그 연장선의 큰 그림으로, 합의되면 단계적으로 실행한다.

## Context

`gui/` 는 동작하지만 위젯·페이지를 PySide6 로 만드는 **기본 구조가 표준화돼 있지 않다**(같은
패턴이 5곳에서 제각각 재구현). 목표는 두 갈래다:

1. **재사용 프레임워크 패키지 `scaffold/` 추출** — "gui 기반 프로젝트를 위한 기반 구조". 프로젝트
   무관한 부품(저수준 위젯·base 클래스·`Annotated[UI]` 폼 생성·데이터 계층·`UI` 메타데이터)을
   `gui/`·`core/` 에서 떼어내 한 곳에 모은다.
2. **gui 위젯/페이지 기본 구조 표준화** — base 클래스로 중복을 제거하고 모든 위젯이 같은
   계약(`changed`/`to_config`/`load`)으로 조립되게 한다.

핵심 제약: **`core` 는 Qt-free 여야 한다**(cli 가 gui 없이 core 사용). 따라서 `scaffold` 의
Qt 의존부(widgets/form/_base)와 Qt-free 부(`meta/`)를 가르고, core 는 `scaffold.meta` 만 쓴다.

확정 방향(논의 결과):
- 프레임워크 패키지명 = **`scaffold`**.
- `UI` 메타데이터 → `scaffold/meta/`.  (※ 현재는 중간 단계로 `core/dataset/ui.py` 에 위치)
- **데이터 계층 전체 이동** — `core/dataset/`(`meta.py`, `handler/`, `utils/`, `ui.py`) →
  `scaffold/meta/`. core/gui 가 scaffold 에 의존(방향 깨끗).

## 목표 구조

```
scaffold/                  ← 재사용 기반 (gui 기반 프로젝트용)
  __init__.py              ← Qt-free 유지 (top-level 에서 Qt import 금지 — core 보호)
  meta/                    ← Qt-free: 메타데이터 + 데이터 계층
    __init__.py            ← Data_Ref·Dataset_Meta·Frame·Object·META_FILE·UI·handler·io/rle 재노출
    meta.py                ← (← core/dataset/meta.py)
    ui.py                  ← (← core/dataset/ui.py) UI dataclass
    handler/               ← (← core/dataset/handler/)
    utils/                 ← (← core/dataset/utils/)
    test_dataset.py        ← (← core/dataset/test_dataset.py)
    README.md
  widgets.py               ← (← gui/widgets.py) 저수준 Qt 위젯 (core 의존 0)
  _base.py                 ← NEW. base 위젯 클래스 (표준화 산물)
  form.py                  ← (← gui/form.py) Annotated[UI]→폼, UI 는 scaffold.meta 에서 import
gui/                       ← LENS 페이지 (scaffold + core 의존)
  page.py, converter/, run/, meta_view/, verify/
core/                      ← LENS 계산 계층 (scaffold.meta 만 의존, Qt-free 유지)
```

의존 방향: `scaffold.meta`(Qt-free) ← `core` ← `gui` → `scaffold`(widgets/_base/form, Qt).
**`scaffold/__init__.py` 는 Qt 를 eager import 하지 않는다** — 소비자는
`scaffold.meta`/`scaffold.widgets`/`scaffold.form`/`scaffold._base` 를 명시 import.

## Phase A — scaffold 골격 + 데이터 계층 이동

1. `scaffold/` 생성. `core/dataset/` 의 `meta.py`·`ui.py`·`handler/`·`utils/`·`test_dataset.py`·
   `README.md` 를 `scaffold/meta/` 로 이동(내용 동일, 내부 상대 import 유지 — `handler/__init__.py`
   의 `from ..meta import Data_Ref` 는 scaffold 안에서도 유효).
2. `core/dataset/__init__.py` 재노출 목록을 `scaffold/meta/__init__.py` 로 이관.
3. `core/dataset/` 디렉터리 제거.

## Phase B — import 경로 갱신 (동작 100% 동일)

- `core/_base.py`: `from .dataset import …` → `from scaffold.meta import …`
- `core/process/_base.py`: `from ..dataset.meta import …`, `from ..dataset import handler`,
  `from ..dataset import UI` → `from scaffold.meta import Data_Ref, Dataset_Meta, Frame, Object, handler, UI`
  (process 모듈들의 `from .._base import Base_Process, UI` 호환 위해 재노출 유지).
- `core/converter/discover/glob.py`: `from ...dataset import handler` → `from scaffold.meta import handler`
- gui: `from core.dataset.meta import …` → `from scaffold.meta import …`,
  `from core.dataset import handler` → `from scaffold.meta import handler`
  (`gui/page.py`, `gui/meta_view/_view.py`·`_datas.py`·`_tree_utils.py`, `gui/verify/_dialog.py`·`_overlay.py`).
- `gui/widgets.py` → `scaffold/widgets.py`, `gui/form.py` → `scaffold/form.py`
  (`form.py` 의 UI import 는 `from scaffold.meta import UI`). gui 내 `from gui.widgets/form` →
  `from scaffold.widgets/form`.
- import 헬스체크로 회귀 0 확인.

## Phase C — 표준 base 클래스 (`scaffold/_base.py`)

- `Config_widget(QWidget)` — `changed` + `to_config()`/`load()` 계약, `_build()` 관례.
- `Row_list(Config_widget)` → `Dict_editor`(행 `(key,value)`→dict) / `List_editor`(행 `value`→list).
  추가/삭제/(선택)▲▼/`changed` 집계, `widgets._reorder`/`_drop` 재사용.
- `Collapsible(QWidget)` — 헤더 토글 + body(접으면 maxHeight 고정; 현 `page._Collapsible` 로직).
- `Swappable_form(QWidget)` — selector 변경 시 내부 폼 교체(`set_form`).
- `Background_task(QObject)` + `Thread_runner` — `finished=Signal(bool,str)`, `work()->str` +
  QThread 수명 캡슐화.
- `row_controls(on_remove, on_up=None, on_down=None)` — `_flow_card._move_btns` 일반화.

## Phase D — base 위로 재구현 (중복 제거)

- `scaffold/form.py`: `_Pair_list_editor` → `Dict_editor`(호환 별칭 `pairs/set_pairs/append`),
  `_Model_form` → `Swappable_form`, `Config_form` → `Config_widget` 계약.
- `gui/converter/_panel.py`: `_Glob_list_editor` → `Dict_editor`, `_Convert_worker` →
  `Background_task`+`Thread_runner`. `_CONVERTER_WIDGETS` 유지.
- `gui/run/_flow_card.py`: `_Outputs_editor` → `Dict_editor`, step 목록 → `List_editor`,
  접기 → `Collapsible`, `_move_btns` → `row_controls`, `_rebuild_form` → `Swappable_form`.
- `gui/run/_sequence.py`: `Flow_sequence` → `List_editor`.
- `gui/run/_panel.py`+`_worker.py`: `Run_worker` → `Background_task`(+progress/stop), 스레드 배선
  → `Thread_runner`.
- `gui/page.py`: `_Collapsible` 제거 → `scaffold._base.Collapsible`.
- `gui/meta_view/`·`gui/verify/`: 트리 기반이라 **계약/명명만 정렬**, 편집 로직 동작 보존.

## 명명/관례 표준

- config 위젯: 시그널 `changed`, 메서드 `to_config()`/`load()`. 생성 골격
  `__init__(…, parent=None) → super().__init__(parent) → self._build()`. private 모듈 `_` 접두,
  공개 API 는 `__init__` 의 `__all__` 재노출.
- README: 루트 `README.md` "모듈 구성" 에 `scaffold/` 추가, `gui/README.md` 공유 모듈 표를
  scaffold 기준으로 수정, `scaffold/README.md` 신설.

## 비목표

- pyproject/배포 패키징, 앱 셸(app.py) 이동, 기능 추가/동작 변경. 순수 구조 재배치 + 표준화이며
  **입출력 동작은 동일**해야 한다.

## 위험 / 주의

- `scaffold/__init__.py` 가 Qt 를 eager import 하면 core 오염 → init 은 Qt-free 로.
- `python_toolbox` 는 외부 패키지(편집 대상 아님). `scaffold.meta` 는 `python_toolbox`·numpy·cv2
  에만 의존하므로 이동해도 자족적.
- `core/dataset/utils.io.Read_from` 와 `python_toolbox.file.Read_from` 공존 — 사용처별 출처 보존.

## 검증

1. import 헬스체크 (Phase B 직후·완료 후):
   `python -c "import scaffold.meta, core, core.process, core.converter"` (core Qt-free 유지 —
   PySide6 없이도 통과) + `python -c "import scaffold.widgets, scaffold.form, scaffold._base, gui.page"`.
2. 데이터 계층 테스트: `pytest scaffold/meta/test_dataset.py`.
3. gui 오프스크린 라운드트립: `test_gui_card.py` 를 현 `Flow_card`/`Flow_sequence` + scaffold import
   기준으로 재작성, Dict/List_editor 위젯 `to_config()/load()` 라운드트립 검증.
4. 수동 구동: `python app.py` 로 주요 동선 회귀 없음 확인.
5. CLI 회귀: `python cli.py --config <config> --stages converter run`.
