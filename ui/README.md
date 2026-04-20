# ui

PySide6 기반 편집기 UI 레이어. `spatial_toolbox`(씬/에셋 모델·렌더 코어)와 `viewport/`·`simulation/`(편집기 뷰포트·오프라인 캡처)의 **최상위 소비자**이며, 이 레이어는 어떤 도메인 모듈도 참조하지 않음.

## 의존 방향

```text
spatial_toolbox  ──┐
viewport/          ├──→  ui/editor/
simulation/        ──┘
```

UI는 도메인을 호출만 하고, 도메인은 UI를 알지 못함. 위젯 간 직접 참조 없이 `Main_Window`가 **Mediator** 역할로 시그널/슬롯을 중재함.

## 구조

```
ui/
├── style.py                          # QSS 스타일 정의
└── editor/
    ├── main.py                       # Main_Window — 레이아웃 사령탑 + Mediator
    ├── viewer.py                     # Viewer_Panel — QOpenGLWidget 3D 뷰포트
    └── sidebar/
        ├── widget.py                 # Main_Sidebar — 크기 조절 가능한 컨테이너
        └── panels/
            ├── engine.py             #   Navigation / Page_Config — Activity Bar 엔진
            ├── scene/
            │   ├── page.py           #   Scene_Explorer_Page (Outliner + Inspector)
            │   ├── scene_tree.py     #   Scene_Tree_Widget — 트리 + visible 토글 + 인라인 편집
            │   └── property.py       #   Property_Panel — 선택 노드 속성 인스펙터
            ├── asset/
            │   ├── browser.py        #   Asset_Browser_Panel — 임포트/인스턴스화
            │   └── duplicate_dialog.py # Duplicate_Dialog — 유사도 기반 중복 감지 다이얼로그
            └── viewport/
                └── camera.py         #   Orbit_Camera_Panel — 뷰포트 카메라 파라미터 패널
```

## main.py — Main_Window

Activity/Side Bar(좌) + 3D Viewer(우) 2분할 레이아웃의 사령탑.

- **소유 자원**: `Stage_Controller`, `Asset_Cache` (도메인 단일 인스턴스를 보유하여 자식 위젯에 주입)
- **구성**: `Main_Sidebar` + `Viewer_Panel`을 `QHBoxLayout`에 배치, 사이드바는 고정 너비, 뷰어는 `setStretch(1, 1)`로 잔여 영역 100% 점유
- **Mediator 슬롯**: 위젯 간 직접 시그널 연결 대신 `Main_Window`가 중계함

```
Asset_Browser  ──(instantiate_requested)──→  Main_Window  ──→  Stage_Controller + Viewer
Scene_Tree     ──(selection_changed)──────→  Main_Window  ──→  Viewer.selection + Inspector
Inspector      ──(property_changed)───────→  Main_Window  ──→  Viewer.update()
Viewer         ──(node_selected_signal)───→  Main_Window  ──→  Scene_Tree.Set_external_selection
Viewer         ──(camera_moved_signal)────→  Main_Window  ──→  Camera_Panel.Refresh
Camera_Panel   ──(camera_changed)─────────→  Main_Window  ──→  Viewer.camera.Update_projection
Scene_Page     ──(scene_loaded)───────────→  Main_Window  ──→  Asset_Page.Clear + Viewer reset
```

## viewer.py — Viewer_Panel

`QOpenGLWidget`을 상속한 3D 뷰포트. `viewport/` 모듈을 Qt 이벤트 루프에 결합하는 어댑터 역할임.

- **보유 객체**: `Orbit_Camera`, `Scene_Renderer`, `Selection_Controller`, `Gizmo_Controller`
- **렌더링 루프**: `QTimer(16ms)` → `update()` → `paintGL` → `Scene_Renderer.Render_frame` + (선택 시) `Gizmo_Controller.Render_overlay`
- **입력 라우팅**:
  - 좌클릭 → `Pick_gizmo_axis` 우선 시도 → 미적중 시 `Selection_Controller.Pick`
  - 좌드래그 → 활성 축 있으면 `Apply_transform_drag`, 없으면 `Orbit_Camera.Rotate`
  - 휠 클릭 드래그 → `Orbit_Camera.Pan`
  - 휠 스크롤 → `Orbit_Camera.Zoom`
- **좌표 변환**: Qt의 좌상단 기준 y를 OpenGL 좌하단 기준으로 `self.height() - y` 반전 후 전달
- **시그널**: `node_selected_signal(object)`, `camera_moved_signal()`

## sidebar/widget.py — Main_Sidebar

자체 마우스 이벤트로 너비를 조절하는 컨테이너.

- 우측 5px `QFrame` 핸들 위젯이 마우스 이벤트를 전담 (자식 위젯과 간섭 회피)
- 닫힘 상태 50px ↔ 열림 상태 사용자 지정 너비(250~650), `Navigation.toggled` 시그널로 전환
- 자식 패널은 `Scene_Explorer_Page`, `Asset_Browser_Panel`, `Orbit_Camera_Panel`을 보유

## sidebar/panels/

### engine.py — Navigation

VS Code 스타일의 Activity Bar + Side Bar 레이아웃 엔진. `QHBoxLayout` 서브클래스.

- `Page_Config(icon, title, widget)` 제너릭 데이터클래스로 페이지 정의
- 활성 페이지 토글 시 `toggled(bool)` 시그널을 발행하여 사이드바 열림/닫힘 상태와 동기화

### scene/

| 위젯 | 역할 | 시그널 |
|---|---|---|
| `Scene_Explorer_Page` | Outliner + Inspector 묶음 페이지 | `selection_changed(list)`, `property_changed()`, `scene_loaded()` |
| `Outliner_Panel` | 씬 트리 뷰어 + 파일 I/O 버튼 (`Stage_Controller.Save/Load` 호출) | `selection_changed(list)`, `scene_loaded()` |
| `Scene_Tree_Widget` | `QTreeWidget` 기반 트리. visible 토글 아이콘, 라벨 인라인 편집(`_Name_Delegate`) | `selection_changed(list)` |
| `Property_Panel` | 선택 노드의 transform/속성 인스펙터. `Build_transform`/`Decompose_transform` 사용 | `property_changed()` |

### asset/

| 위젯 | 역할 | 시그널 |
|---|---|---|
| `Asset_Browser_Panel` | `Asset_Cache`에 등록된 에셋 목록 + 임포트/인스턴스화 트리거 | `instantiate_requested(object)`, `asset_removed(str)` |
| `Duplicate_Dialog` | 임포트 시 `spatial_toolbox.scene.asset.utils.similarity` 기반 중복 후보 표시 다이얼로그 | — |

### viewport/

| 위젯 | 역할 | 시그널 |
|---|---|---|
| `Orbit_Camera_Panel` | `Orbit_Camera`의 yaw/pitch/distance/fov 파라미터 편집 패널. `Bind_camera()`로 뷰포트 카메라 양방향 동기화 | `camera_changed()` |

## style.py

전역 QSS 스타일 정의. `app.py`에서 `QApplication` 생성 직후 적용함.

## 단방향 데이터 흐름 원칙

UI 위젯은 도메인 모델(`Stage_Controller`, `Asset_Cache`, `Base_Node`)을 직접 수정함. 향후 리팩토링 과제로 **Command 패턴 기반 상태 제어층**을 도입하여 UI ↔ 모델 사이에 트랜잭션 레이어를 두는 것이 명시되어 있음 (루트 README 참고).

현재는 다음 규칙으로 무결성을 유지함:

1. 모델 변경 후 반드시 시그널을 발행하여 다른 위젯이 동기화되도록 함
2. 위젯 간 직접 참조 금지 — `Main_Window` Mediator 슬롯을 경유함
3. 도메인 객체는 `__init__`에서 주입받음 (위젯 내부에서 생성하지 않음)
