# graphics

3D 시각화, 렌더링, 편집기 UI를 담당하는 도메인. `data/` 레이어의 유일한 소비자임.

## 의존 방향

```
data/  ←──  graphics/core/
       ←──  graphics/viewport/  ←──  graphics/ui/
       ←──  graphics/render/    ←──  graphics/ui/
```

- `core/` : `data/scene/node` 참조
- `viewport/`, `render/` : `data/` + `core/` 참조
- `ui/` : 최상위 소비자, 나머지 전부 참조

순환 참조 없음. `graphics/` 내부에서도 단방향 흐름이 유지됨.

## 구조

```
graphics/
├── core/
│   └── draw.py           # Draw_mesh, Walk_scene — OpenGL 고정 파이프라인 공용 드로우
├── viewport/             # 편집기 실시간 뷰포트 (→ viewport/README.md)
│   ├── renderer.py
│   ├── view.py
│   ├── transform.py
│   └── tool/
├── render/               # 학습 데이터 오프라인 생성 (→ render/README.md)
│   ├── config.py
│   ├── pass_/
│   ├── pipeline.py
│   └── exporter.py
└── ui/                   # PySide6 편집기 UI
    └── editor/
        ├── main.py       # Main_Window — 레이아웃 사령탑
        ├── viewer.py     # Viewer_Panel — QOpenGLWidget 기반 3D 뷰포트
        └── sidebar/
            ├── widget.py # Main_Sidebar — 크기 조절 가능한 사이드바 컨테이너
            └── panels/
                ├── engine.py        # Navigation — Activity/Side Bar 레이아웃 엔진
                ├── scene/           # Scene Explorer (Outliner + Inspector)
                └── asset/browser.py # Asset Browser (Import/Instantiate)
```

## core/

`viewport/`와 `render/` 양쪽에서 사용하는 OpenGL 드로우 코어를 분리한 모듈.

| 함수 | 역할 |
|---|---|
| `Draw_mesh(mesh)` | Trimesh 데이터를 glVertexPointer/glDrawElements로 렌더링 |
| `Walk_scene(node)` | 씬 트리를 재귀 순회하며 local_matrix 적용 + Draw_mesh 호출 |

## ui/

편집기의 위젯 조립 구조. 시그널/슬롯 기반 단방향 데이터 흐름:

```
Asset Browser  ──(instantiate_requested)──→  Main_Window  ──→  Stage + Viewer
Scene Tree     ──(selection_changed)──────→  Main_Window  ──→  Viewer + Inspector
Inspector      ──(property_changed)───────→  Main_Window  ──→  Viewer.update()
Viewer         ──(node_selected_signal)───→  Main_Window  ──→  Scene Tree
```

`Main_Window`가 중재자(Mediator) 역할을 수행하여 위젯 간 직접 참조를 방지함.
