# Cookbook

FOCUS 프로젝트의 실행 방법 및 사용 예시 모음임.

## 정적 편집기 실행

PySide6 기반 편집기 UI를 실행함.

```bash
python app.py
```

진입점: `app.py` → `ui/editor/main.py`의 `Main_Window`. 좌측 Activity Bar에서 Scene / Asset / Viewport / Simulation 패널을 토글할 수 있음.

## 헤드리스 데이터셋 생성

`capture_cli.py`를 통해 GUI 없이 멀티패스 렌더링을 수행함.

```bash
python capture_cli.py --render_cfg path/to/render.json
```

내부 흐름: `simulation.engine.Run_batch_capture` → `Render_Config` JSON 로드 → `Stage_Controller.Load(scene_path)` → `target` 그룹 탐색 → `Capture_Project.Render_target` 에서 객체별로 `Render_Pipeline.Setup_headless_context` → `Execute` → `Result_Exporter.Save` 순서로 반복함. EGL 초기화 실패 시 Qt `QOffscreenSurface` 백엔드로 자동 폴백함.

### 프로그램 코드로 실행

```python
from pathlib import Path
from simulation.engine import Run_batch_capture

Run_batch_capture(Path("path/to/render.json"))
```

저수준 직접 제어가 필요한 경우:

```python
from spatial_toolbox.scene import Controller as Stage_Controller
from simulation.config import Render_Config
from simulation.pipeline import Render_Pipeline
from simulation.exporter import Result_Exporter

config = Render_Config(passes=["rgb", "depth", "segmentation", "normal"])
pipeline = Render_Pipeline(config)
pipeline.Setup_headless_context(width=640, height=480, use_egl=True)

stage = Stage_Controller()
stage.Load("scene.json")
root = stage.root
camera = next(n for n in root.children if n.prim_type == "Camera")

results = pipeline.Execute(root, camera, 640, 480)

exporter = Result_Exporter("./out")
exporter.Save(frame_id=0, results=results, camera_node=camera, config=config)

pipeline.Teardown_headless_context()
```

출력 산출물 (프레임 번호는 `%06d` 패딩):

- `rgb_000000.png` — uint8 RGB
- `depth_000000.npy` — float32 선형 미터
- `segmentation_000000.png` — 인스턴스 ID RGB 인코딩
- `normal_000000.png` — 로컬 법선 RGB 인코딩
- `metadata_000000.json` — 카메라 intrinsic/extrinsic + 렌더 설정 + segmentation id_map

## UI 임베드 모드 렌더링

호출 측에서 이미 GL 컨텍스트가 활성화된 경우 `Setup_headless_context`를 호출하지 않고 바로 `Execute`함.

```python
# QOpenGLWidget.paintGL 내부 등 makeCurrent 이후
pipeline = Render_Pipeline(config)
results = pipeline.Execute(root_node, camera_node, w, h)
```

## 새 렌더 패스 추가

패스 구현체는 서브모듈 `spatial_toolbox.graphics.openGL.pass_` 에 위치함. `OpenGL_Base_Pass` 를 상속하여 클래스 속성만 선언하는 방식이 표준임.

```python
from spatial_toolbox.graphics.openGL.pass_.base import OpenGL_Base_Pass
from spatial_toolbox.graphics.registry import Pass_Registry

@Pass_Registry.Register_module("optical_flow")
class Optical_Flow_Pass(OpenGL_Base_Pass):
    name = "optical_flow"
    _use_lighting = False
    _draw_mode = "default"
    _readback_format = "rgb"
    _clear_color = (0.0, 0.0, 0.0, 1.0)
```

특수 처리가 필요하면 훅 오버라이드:

- `_On_setup()` — GL 상태 설정 (조명/디더 등)
- `_On_draw(render_queue)` — 드로우 루프 (기본: `_Draw_scene` 위임)
- `_On_readback(width, height, **kwargs)` — 결과 픽셀 읽기
- `_On_cleanup()` — 상태 복구

`_draw_mode` 값으로 `"default"`(조명/머티리얼), `"normal_color"`(법선 RGB), `"id_color"`(ID 인코딩)를 선택함. ID 모드 사용 시 `renderer.id_map` 또는 패스의 `last_id_map` 프로퍼티로 `(R,G,B) → Base_Node` 매핑을 조회할 수 있음.

`Render_Config.passes` 리스트에 이름을 추가하면 `Render_Pipeline` 이 자동으로 인스턴스화 + `Configure` 훅 호출 + 순차 실행함.

## 카메라·객체·광원 랜덤화

`Render_Config` 는 카메라 / 객체 / 광원의 6-DoF 델타를 독립 `Randomize_Range` 로 받음. 각 필드는 고정값(`float`) 또는 `[min, max]` 리스트임. `Sample_delta_matrix(range)` 가 균일 샘플링하여 4×4 델타 행렬을 생성함.

```python
from simulation.config import Render_Config, Randomize_Range

config = Render_Config(
    passes=["rgb", "depth"],
    num_samples=100,
    cam=Randomize_Range(tx=[-0.5, 0.5], ty=[-0.5, 0.5], rz=[-3.14, 3.14]),
    obj=Randomize_Range(rz=[0.0, 6.28]),
    light=Randomize_Range(tx=[-2.0, 2.0], tz=[-2.0, 2.0]),
    seed=42,
)
```

`light` 는 `tx/ty/tz` 성분만 사용되며 회전 필드는 무시됨. `seed` 를 지정하면 `np.random.seed` 에 주입되어 재현성을 확보함.

## 메시 유사도 계측

`spatial_toolbox.scene.asset.utils.similarity` 는 세 가지 비교 함수를 제공함.

```python
from spatial_toolbox.scene.asset.utils.similarity import (
    Is_exact_match,
    Calculate_match_rate,
    Calculate_scan_match_rate,
)

Is_exact_match(mesh_a, mesh_b)             # 정점/면 정확 일치 여부
Calculate_match_rate(mesh_a, mesh_b)       # 표면 샘플링 기반 일치율
Calculate_scan_match_rate(mesh_a, mesh_b)  # SVD 기반 ICP 정합 후 일치율
```

`Asset_Browser_Panel` 의 임포트 흐름은 위 함수를 사용해 중복 후보를 `Duplicate_Dialog` 에 표시함.

## 씬 · 에셋 저장 / 로드

```python
from spatial_toolbox.scene import Controller, ASSET_CACHE

stage = Controller()

# 파일에서 씬 조립 + 에셋 캐시 등록을 1회 read로 수행
stage.Add_from_file("model.obj")

# JSON으로 씬 저장 / 복원
stage.Save("scene.json")
stage.Load("scene.json")

# 캐시 조회 (동일 source_key 가진 다중 노드는 공유 인스턴스)
asset = ASSET_CACHE.Get(node.source_key, share=True)
```

`Scene` 파일의 다중 geometry는 `'{abs_path}#{geo_name}'` fragment 키로 등록되며, `Mesh` 노드는 geometry 본체 없이 `source_key` 만으로 캐시를 참조함.
