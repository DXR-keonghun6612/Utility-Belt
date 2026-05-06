# Viewport Cookbook

`viewport/`는 편집기용 실시간 뷰포트 코어다. 여기서는 UI에서 어떻게 붙는지보다, 카메라 조작·프레임 렌더·픽킹·기즈모 적용 흐름을 중심으로 정리함.

## 관련 문서

| 문서 | 설명 |
|---|---|
| [루트 COOKBOOK](../COOKBOOK.md) | 프로젝트 상위 흐름 |
| [ui/COOKBOOK.md](../ui/COOKBOOK.md) | Qt 편집기 결합 방식 |

## 레시피 1: 기본 렌더러 구성

```python
from viewport.orbit_cam import Orbit_Camera
from viewport.renderer import Scene_Renderer

camera = Orbit_Camera()
renderer = Scene_Renderer()
```

`Scene_Renderer.Initialize()`는 OpenGL 상태와 기본 광원을 초기화하고, 이후 프레임마다 `Render_frame()`을 호출하는 구조다.

## 레시피 2: 한 프레임 그리기

```python
renderer.Render_frame(
    root_node=stage.root,
    camera=camera,
    selected_node=selected_node,
)
```

이 호출은 다음 요소를 한 번에 처리함.

- 배경색 및 depth buffer 초기화
- `Orbit_Camera.Apply_view()`
- 공통 조명 적용
- `Ground_Grid` 렌더링
- 모든 `Mesh` 노드 렌더링
- 모든 `Camera` 노드의 프러스텀 렌더링
- 선택 노드가 있으면 강조 표시

## 레시피 3: Orbit 카메라 조작

```python
camera.Rotate(dx, dy)
camera.Pan(dx, dy)
camera.Zoom_to_cursor(delta, ndc_x, ndc_y, aspect)
camera.Update_projection(width, height, unit_length)
```

- `Rotate()`는 yaw/pitch를 갱신함
- `Pan()`은 현재 yaw/pitch 기준 right/up 벡터로 target을 이동함
- `Zoom_to_cursor()`는 단순 distance 변경이 아니라 커서 방향 world offset까지 같이 반영함
- `Update_projection()`은 `stage.unit_length`를 반영해 near/far clip을 씬 단위로 환산함

## 레시피 4: ID pass 픽킹

```python
from viewport.utils.selection import Selection_Controller

selection = Selection_Controller()
node = selection.Pick(x, y, stage.root, camera, renderer)
```

`Pick()`은 내부적으로 `renderer.Render_id_pass()`를 호출한 뒤 `glReadPixels()` 색을 읽어 노드를 역조회함. 좌표계 원점은 OpenGL 기준 좌하단이므로, Qt 이벤트 좌표는 호출 전에 `height - y`로 뒤집어야 함.

## 레시피 5: 기즈모 드래그 적용

```python
from viewport.node.gizmo import Transform_Gizmo

gizmo = Transform_Gizmo()
axis = gizmo.Pick_axis(x, y, camera, selected_node)
gizmo.Apply_drag(selected_node, dx, dy, screen_x, screen_y)
```

- `Pick_axis()`는 별도 컬러 픽킹 패스로 축 또는 회전 링을 선택함
- `Apply_drag()`는 선택된 축에 따라 이동 또는 회전 delta matrix를 계산해 `node.local_rigid`에 곱함
- 기즈모는 씬 노드가 아니라 뷰포트 오버레이 객체이므로 scene graph 저장 대상은 아님
