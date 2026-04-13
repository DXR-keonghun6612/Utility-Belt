# graphics/viewport

편집기의 실시간 3D 뷰포트. 씬 시각화, 카메라 내비게이션, 객체 선택 및 기즈모 조작을 처리함.

## 구조

```
viewport/
├── renderer.py         # Scene_Renderer — 메인 패스 + ID 픽킹 패스 + 그라운드 그리드
├── view.py             # Orbit_Camera — 극좌표계 기반 궤도 카메라
├── transform.py        # Transform_Math — 마우스 2D 델타 → 3D 행렬 변환
└── tool/
    ├── gizmo.py        # Gizmo_Controller — 3축 이동/회전 핸들
    ├── camera_gizmo.py # Draw_camera_gizmo — Camera_Node 와이어프레임 시각화
    └── selection.py    # Selection_Controller — ID 패스 기반 객체 픽킹
```

## 모듈 관계

```
Viewer_Panel (ui/editor/viewer.py)
    │
    ├── Orbit_Camera          ← 마우스 이벤트로 회전/패닝/줌
    ├── Scene_Renderer        ← 매 프레임 Render_frame() 호출
    │       └── GPU_Resource_Manager (graphics/core/resource.py)
    ├── Selection_Controller  ← 클릭 시 Pick() → ID 패스 렌더링 → 노드 반환
    └── Gizmo_Controller      ← 드래그 시 Apply_transform_drag() → 노드 행렬 갱신
```

## renderer.py — Scene_Renderer

세 가지 렌더 경로를 보유함:

- **메인 패스** (`Render_frame`): Phong 조명 + 그라운드 그리드. 선택 메시는 와이어프레임 하이라이트 오버레이.
- **ID 패스** (`Render_id_pass`): 메시별 고유 RGB 색상 인코딩. 라이팅/디더/멀티샘플 OFF 후 컬러키 → `Base_Node` 딕셔너리 반환. `Selection_Controller`가 사용함.
- **카메라 기즈모**: `Camera_Node` 순회 시 `Draw_camera_gizmo`를 호출하여 프러스텀과 바디를 와이어프레임으로 함께 렌더링함.

메시 드로우는 `graphics/core/draw.Draw_mesh`에 위임하며, `GPU_Resource_Manager`로 VBO 캐싱을 활성화함. `render_mode`("SOLID"/"WIREFRAME") 토글을 지원함.

## view.py — Orbit_Camera

편집기 전용 내비게이션 카메라. 씬에 배치되는 `Camera_Node`(prim_type="Camera")와는 **별개의 객체**임.

| 조작 | 메서드 | 설명 |
|---|---|---|
| 궤도 회전 | `Rotate(dx, dy)` | Yaw/Pitch 극좌표 갱신 (Pitch ±89° 클램핑) |
| 패닝 | `Pan(dx, dy)` | Right/Up 벡터 산출 후 거리 비례 보정 |
| 줌 | `Zoom(delta)` | 타겟 거리 증감 (최소 0.1 보호) |
| 투영 | `Update_projection(w, h)` | gluPerspective 갱신 |
| 뷰 적용 | `Apply_view()` | gluLookAt 호출 (매 프레임) |

## transform.py — Transform_Math

마우스 드래그 → 3D 변환 행렬 변환의 순수 수학 유틸리티. 모든 메서드는 정적이며, 호출 전 `GL_MODELVIEW_MATRIX`가 `카메라 뷰 * 객체 월드` 상태여야 함.

| 메서드 | 기법 |
|---|---|
| `_Get_screen_direction(axis)` | `gluProject`로 3D 축의 화면 투영 방향 산출 |
| `Get_translation_delta(axis, dx, dy, sens)` | 마우스 벡터와 화면 축 방향의 내적 → 평행이동 행렬 |
| `Get_rotation_delta(key, axis, dx, dy, sx, sy)` | 객체 중심 기준 atan2 각도 + 뷰 Z축 부호 보정 → 회전 행렬 |
| `Apply_delta(local, delta)` | `M_new = M_old @ M_delta` (객체 로컬 기준) |

회전 산출은 접선 내적 대신 atan2 기반 각도 변위를 사용하여 마우스 위치 무관하게 CAD 스타일 일관성을 보장함.

## tool/

### gizmo.py — Gizmo_Controller

자체적으로 픽킹용 렌더링과 시각적 오버레이 렌더링을 모두 수행함.

- `Pick_gizmo_axis(x, y, …)`: 라이팅/블렌드/멀티샘플 OFF + 굵은 선(15px)으로 ID 색상 패스 → 1px 픽셀 → `_pick_colors` 매핑으로 활성 축 결정. 이동 축은 `(255,0,0)`/`(0,255,0)`/`(0,0,255)`, 회전 호는 `(128,0,0)`/…
- `Render_overlay(…)`: 깊이 테스트 OFF + 블렌드 ON으로 항상 위에 표시. 카메라 거리에 비례한 다이나믹 스케일링으로 줌과 무관한 일정 크기 유지.
- `Apply_transform_drag(…)`: 활성 축에 따라 `Transform_Math.Get_translation_delta` 또는 `Get_rotation_delta` 호출 후 `Apply_delta`로 노드 `local_matrix` 갱신.

### camera_gizmo.py — Draw_camera_gizmo

`Camera_Node` 시각화 전용 함수 (컨트롤러 클래스 없음). `fov`/`img_w`/`img_h`로 프러스텀을 산출하여 OpenGL `-Z` 관례에 맞춰 와이어프레임 바디(작은 직육면체) + 프러스텀 라인 + 원거리 사각형 + Up 인디케이터(상단 삼각형)를 그림. 호출 전 `glMultMatrixf`로 노드 변환이 적용된 상태여야 함.

### selection.py — Selection_Controller

`Scene_Renderer.Render_id_pass()`를 호출하여 ID 색상 맵을 받고, `glReadPixels`로 1px 픽셀을 읽어 매핑 딕셔너리에서 `Base_Node`를 역추적함.

> **좌표계 주의**: OpenGL 윈도우 좌표 원점은 좌측 하단임. Qt 마우스 이벤트의 y는 호출 측에서 `(위젯_높이 - y)`로 반전 후 전달해야 함.

`Set_selection(node)`은 외부 패널(Outliner 트리)에서 선택 상태를 명시적으로 주입할 때 사용됨.
