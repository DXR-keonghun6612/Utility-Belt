# UI Cookbook

`ui/`는 FOCUS 편집기를 실행하고 패널 간 상태를 연결하는 레이어임. 여기서는 앱 실행, 이벤트 흐름, 패널 확장 패턴만 정리함.

## 관련 문서

| 문서 | 설명 |
|---|---|
| [루트 COOKBOOK](../COOKBOOK.md) | 프로젝트 전체 실행 흐름 |
| [viewport/COOKBOOK.md](../viewport/COOKBOOK.md) | 뷰포트 코어와 상호작용 |
| [simulation/COOKBOOK.md](../simulation/COOKBOOK.md) | 오프라인 캡처 진입점 |

## 레시피 1: 편집기 실행

```bash
python app.py
```

`app.py`는 `QApplication` 생성 후 `ui.main.Main_Window`를 띄움.

## 레시피 2: Main_Window 조립 흐름 이해

```python
from ui.main import Main_Window

window = Main_Window()
window.show()
```

`Main_Window`는 다음 객체를 생성해 결합함.

- `Stage_Controller`
- `Viewer_Panel(stage)`
- `Scene_Explorer_Page(stage)`
- `Asset_Browser_Panel()`
- `Orbit_Camera_Panel()`
- `Simulation_Page(stage)`
- `Sidebar_Container([...])`

카메라 패널은 `viewer.camera`와 `viewer.renderer.config`에 바인딩되어 뷰포트 카메라와 그리드 설정을 편집함.

## 레시피 3: 전역 이벤트 버스 사용

```python
from ui.event_bus import EVENT_BUS

EVENT_BUS.scene_mutated.emit()
EVENT_BUS.selection_changed.emit([node])
EVENT_BUS.camera_changed.emit()
```

기본 규칙은 아래와 같음.

- 씬 구조 변경 후 `scene_mutated`
- 선택 변경 후 `selection_changed`
- 노드 속성 변경 후 `property_changed`
- 카메라 수치 편집 후 `camera_changed`
- 마우스 기반 카메라 이동 후 `camera_moved`
- 그리드 표시 설정 변경 후 `viewer_config_changed`

## 레시피 4: 새 패널 추가

1. `ui/panels/<name>/` 아래에 `Base_Panel` 상속 위젯을 만든다.
2. 필요한 도메인 객체는 생성하지 말고 생성자 인자로 주입받는다.
3. 위젯 간 직접 참조 대신 `EVENT_BUS` 시그널로 통신한다.
4. `ui/main.py`에서 인스턴스화하고 `Page_Config` 목록에 추가한다.

```python
from ui.sidebar.container import Page_Config

pages = [
    Page_Config("scene", "🗂", "Scene Explorer", scene_page),
    Page_Config("asset", "📦", "Asset Browser", asset_page),
]
```

## 레시피 5: 뷰포트 선택과 인스펙터 동기화

선택은 두 경로로 들어오지만 최종 동기화 지점은 `EVENT_BUS.selection_changed` 하나임.

1. 아웃라이너 선택 변경
2. 뷰포트 ID 패스 픽킹
3. `selection_changed` 발행
4. `Viewer_Panel`이 active selection 갱신
5. `Scene_Explorer_Page`가 `Property_Panel.Update_info()` 호출

이 규칙을 지키면 새 선택 소스가 추가되어도 동기화 경로가 단순하게 유지됨.
