# ui

`ui/`는 PySide6 기반 편집기 레이어임. `spatial_toolbox`가 제공하는 씬/렌더/시뮬레이션 코어와, 프로젝트 로컬 `viewport/`, `simulation/` 어댑터를 묶어 데스크톱 편집기로 노출함.

```text
spatial_toolbox ──┐
viewport/        ├──► ui/
simulation/      ──┘
```

## 설계 경계

- `ui/`는 도메인 객체를 생성하고 연결하지만, 도메인 코드는 `ui/`를 참조하지 않음
- 패널 간 직접 참조 대신 `ui.event_bus.EVENT_BUS`로 상태 변경을 전파함
- `Main_Window`는 레이아웃 조립과 의존성 주입을 담당하고, 개별 패널은 자신의 편집 책임만 가짐

## 구조

```text
ui/
├── main.py                    # Main_Window
├── viewer.py                  # QOpenGLWidget 기반 뷰포트 어댑터
├── event_bus.py               # 전역 시그널 허브
├── style.py                   # QSS 스타일 상수
├── sidebar/
│   └── container.py           # 액티비티 바 + 패널 스택 + 리사이저
└── panels/
    ├── _base.py               # Base_Panel
    ├── scene/                 # 씬 트리, 인스펙터, 파일 I/O
    ├── asset/                 # 에셋 브라우저, 중복 검사
    ├── viewport/              # Orbit camera, grid 설정
    └── simulation/            # Sim_Config 생성/선택, 백그라운드 실행
```

## 핵심 객체

- `Main_Window`: `Stage_Controller`, `Viewer_Panel`, 각 패널을 생성하고 결합함
- `Viewer_Panel`: `Orbit_Camera`, `Scene_Renderer`, `Selection_Controller`, `Transform_Gizmo`를 Qt 이벤트 루프에 연결함
- `EVENT_BUS`: `scene_loaded`, `scene_mutated`, `selection_changed`, `property_changed`, `camera_changed`, `camera_moved`, `viewer_config_changed`, `asset_instantiate_requested` 시그널을 제공함

## 문서

- 상위 사용 흐름: [COOKBOOK.md](./COOKBOOK.md)
- 뷰포트 렌더 코어: [../viewport/README.md](../viewport/README.md)
- 시뮬레이션 패널이 호출하는 오프라인 캡처: [../simulation/README.md](../simulation/README.md)
