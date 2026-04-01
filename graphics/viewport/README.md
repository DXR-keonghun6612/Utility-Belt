# graphics/viewport

편집기의 실시간 3D 뷰포트. 씬 시각화, 카메라 내비게이션, 객체 선택 및 기즈모 조작을 처리함.

## 구조

```
viewport/
├── renderer.py    # Scene_Renderer — 메인 렌더 패스 + ID 픽킹 패스
├── view.py        # Orbit_Camera — 극좌표계 기반 궤도 카메라
├── transform.py   # Transform_Math — 마우스 2D 델타 → 3D 행렬 변환
└── tool/
    ├── gizmo.py   # Gizmo_Controller — 3축 이동/회전 핸들
    └── selection.py # Selection_Controller — ID 기반 객체 픽킹
```

## 모듈 관계

```
Viewer_Panel (ui/editor/viewer.py)
    │
    ├── Orbit_Camera          ← 마우스 이벤트로 회전/패닝/줌
    ├── Scene_Renderer        ← 매 프레임 Render_frame() 호출
    ├── Selection_Controller  ← 클릭 시 Pick() → ID 패스 렌더링 → 노드 반환
    └── Gizmo_Controller      ← 드래그 시 Apply_transform_drag() → 노드 행렬 갱신
```

## renderer.py

두 가지 렌더 패스를 제공함:

- **메인 패스** (`Render_frame`): Phong 조명 기반 씬 시각화. 선택된 노드에 와이어프레임 하이라이트 오버레이.
- **ID 패스** (`Render_id_pass`): 노드별 고유 RGB 색상 인코딩. `Selection_Controller`의 픽킹에 사용.

메쉬 렌더링은 `graphics/core/draw.Draw_mesh`에 위임함.

## view.py — Orbit_Camera

편집기 전용 내비게이션 카메라. 씬에 배치되는 `Scene_Node(prim_type="Camera")`와는 별개의 객체임.

| 조작 | 메서드 | 설명 |
|---|---|---|
| 궤도 회전 | `Rotate(dx, dy)` | Yaw/Pitch 극좌표 갱신 (Gimbal Lock 방지 클램핑) |
| 패닝 | `Pan(dx, dy)` | 시선 직교 평면에서 타겟 이동 (거리 비례 보정) |
| 줌 | `Zoom(delta)` | 타겟 거리 증감 (최소 0.1 보호) |

## transform.py — Transform_Math

마우스 드래그 → 3D 변환 행렬 변환의 수학 로직. `gluProject`를 이용하여 3D 축이 화면에서 향하는 방향을 산출한 뒤, 마우스 이동량과의 내적으로 변환량을 결정함.

- `Get_translation_delta()`: 축 방향 평행 이동 행렬
- `Get_rotation_delta()`: 축 기준 회전 행렬 (접선 벡터 기반)
- `Apply_delta()`: 로컬 행렬에 변화량 우측 곱셈 적용

## tool/

- **gizmo.py**: 자체적으로 픽킹용 렌더링(굵은 선, 고유 색상)과 시각적 오버레이 렌더링을 모두 수행함. 축 활성화 상태에 따라 `Transform_Math`를 호출하여 노드 행렬을 갱신.
- **selection.py**: `Scene_Renderer.Render_id_pass()`를 호출하여 1px 픽셀을 읽고 ID 맵에서 노드를 역추적함.
