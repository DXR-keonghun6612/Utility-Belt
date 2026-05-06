# FOCUS Cookbook

FOCUS를 처음 다룰 때 필요한 상위 흐름만 정리한 문서임. 세부 API와 내부 규약은 각 파트 문서를 참조.

## 파트 문서

| 파트 | 설명 | 문서 |
|---|---|---|
| **UI** | PySide6 편집기, 패널 결합, 이벤트 버스 | [ui/COOKBOOK](./ui/COOKBOOK.md) |
| **Viewport** | 실시간 렌더링, Orbit 카메라, 픽킹, 기즈모 | [viewport/COOKBOOK](./viewport/COOKBOOK.md) |
| **Simulation** | 배치 캡처 진입점, CLI, progress callback | [simulation/COOKBOOK](./simulation/COOKBOOK.md) |
| **Spatial Toolbox** | scene/render/simulation 코어 라이브러리 | [submodules/spatial_toolbox/COOKBOOK](./submodules/spatial_toolbox/COOKBOOK.md) |

## 빠른 시작 1: 편집기 실행

```bash
python app.py
```

실행 후 `Main_Window`가 `Stage_Controller`, `Viewer_Panel`, Scene/Asset/Camera/Simulation 패널을 조립해 편집기를 구성함.

## 빠른 시작 2: 뷰포트에서 장면 검토

뷰포트는 `viewport/` 코어를 사용해 다음 기능을 제공함.

- 중간 버튼 드래그: orbit rotate
- `Shift` + 중간 버튼 드래그: pan
- 휠 스크롤: cursor-centered zoom
- 좌클릭: ID pass 기반 selection
- 좌클릭 드래그: gizmo 이동/회전

세부 동작은 [viewport/COOKBOOK.md](./viewport/COOKBOOK.md) 참조.

## 빠른 시작 3: 시뮬레이션 설정으로 배치 캡처

```bash
python capture_cli.py --render_cfg path/to/sim_config.json
```

또는 코드에서 직접:

```python
from pathlib import Path

from simulation.engine import Run_batch_capture

Run_batch_capture(Path("path/to/sim_config.json"))
```

이 경로는 `Sim_Config`를 읽고, `scene_path`의 씬을 import한 뒤 `Blender_Capture_Engine`으로 캡처를 수행함.

## 빠른 시작 4: 어느 문서를 먼저 볼지

- 편집기 구조와 패널 추가가 필요하면 `ui/README.md`, `ui/COOKBOOK.md`
- 카메라/픽킹/기즈모 수정이 필요하면 `viewport/README.md`, `viewport/COOKBOOK.md`
- 배치 캡처 진입점 수정이 필요하면 `simulation/README.md`, `simulation/COOKBOOK.md`
- 랜덤화 규약, 출력 포맷, 렌더 채널 같은 코어 규칙이 필요하면 `submodules/spatial_toolbox/` 문서
