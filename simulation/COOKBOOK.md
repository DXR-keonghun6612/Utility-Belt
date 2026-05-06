# Simulation Cookbook

`simulation/`은 프로젝트 레벨에서 배치 캡처를 시작하는 가장 얇은 진입점임. 실제 샘플링과 저장 규약은 `spatial_toolbox.simulation` 문서를 따르고, 여기서는 FOCUS에서 어떻게 호출되는지만 정리함.

## 관련 문서

| 문서 | 설명 |
|---|---|
| [루트 COOKBOOK](../COOKBOOK.md) | 프로젝트 상위 실행 흐름 |
| [submodules/spatial_toolbox/spatial_toolbox/simulation/COOKBOOK.md](../submodules/spatial_toolbox/spatial_toolbox/simulation/COOKBOOK.md) | 엔진/출력 포맷/랜덤화 규약 |

## 레시피 1: CLI로 배치 캡처 실행

```bash
python capture_cli.py --render_cfg path/to/sim_config.json
```

`capture_cli.py`는 `QApplication`을 준비한 뒤 `simulation.engine.Run_batch_capture()`를 호출함. Blender 또는 Qt 폴백 경로에서 GUI 런타임이 필요한 경우를 대비한 구성임.

## 레시피 2: 코드에서 직접 실행

```python
from pathlib import Path

from simulation.engine import Run_batch_capture

Run_batch_capture(Path("result/sim_config.json"))
```

이 호출은 아래 순서로 진행됨.

1. `Sim_Config` JSON 역직렬화
2. `scene_path` 기반 씬 파일 import
3. `scene_path.parent / scene_path.stem` 경로 계산
4. `Blender_Capture_Engine.Capture(...)` 실행

## 레시피 3: 진행 상황 콜백 연결

```python
from pathlib import Path

from simulation.engine import Run_batch_capture

def on_progress(current: int, total: int, message: str) -> None:
    print(f"{current}/{total}: {message}")

Run_batch_capture(
    Path("result/sim_config.json"),
    progress_callback=on_progress,
)
```

UI의 `Simulation_Worker`와 CLI의 `cli_progress()`가 모두 이 콜백 시그니처를 사용함.

## 레시피 4: 설정 파일 작성 규약

`simulation/` 자체는 설정 스키마를 정의하지 않음. 반드시 `spatial_toolbox.simulation.Sim_Config` 형식을 따라야 함.

```python
from python_toolbox.project import Write_to_file
from spatial_toolbox.simulation import Randomize_Range, Sim_Config

config = Sim_Config(
    scene_path="scene.json",
    target_label="target",
    camera_labels=["main_camera"],
    num_samples=8,
    seed=1234,
    obj=Randomize_Range(ry=[-10.0, 10.0]),
)

Write_to_file(config, "sim_config.json")
```

필드 의미와 출력 구조는 `spatial_toolbox` simulation cookbook을 참조.
