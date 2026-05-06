# viewport

`viewport/`는 편집기 내부의 실시간 3D 뷰포트 코어임. `spatial_toolbox.render.openGL.OpenGL_Renderer`를 재사용해 씬 검사용 화면 렌더링과 ID 기반 픽킹을 수행하고, 로컬 카메라/기즈모/그리드 로직을 제공함.

```text
spatial_toolbox.scene + spatial_toolbox.render.openGL  ──►  viewport/
                                                          └──► ui.viewer
```

## 역할

- `orbit_cam.py`는 편집용 궤도 카메라와 projection/view 갱신을 담당함
- `renderer.py`는 메인 프레임 렌더와 ID pass 렌더를 담당함
- `utils/selection.py`는 픽셀 readback 기반 선택 컨트롤러를 제공함
- `node/`는 씬 그래프 바깥에서 그려지는 보조 뷰포트 노드들을 담음

## 구조

```text
viewport/
├── README.md
├── COOKBOOK.md
├── orbit_cam.py
├── renderer.py
├── utils/
│   └── selection.py
└── node/
    ├── grid.py
    ├── gizmo.py
    └── camera_frustum.py
```

## 렌더 흐름

```text
Viewer_Panel.paintGL()
    ├── Scene_Renderer.Render_frame(root, orbit_camera, selected_node)
    │   ├── camera.Apply_view()
    │   ├── OpenGL_Renderer.Apply_lighting()
    │   ├── Ground_Grid.Draw()
    │   ├── Mesh draw
    │   └── Camera_Frustum.Draw()
    └── Transform_Gizmo.Draw(...)
```

선택 시에는 별도로 `Scene_Renderer.Render_id_pass()`가 호출되고, `Selection_Controller.Pick()`가 `glReadPixels()` 결과를 `renderer.id_map`과 대조해 노드를 반환함.

## 문서

- 사용 예제: [COOKBOOK.md](./COOKBOOK.md)
- 기반 OpenGL 렌더 계약: [../submodules/spatial_toolbox/spatial_toolbox/render/openGL/COOKBOOK.md](../submodules/spatial_toolbox/spatial_toolbox/render/openGL/COOKBOOK.md)
