# Architecture

프로젝트 구조의 설계 근거, 공통 패턴, 확장 방향을 기록함.

현재 상태에 대한 설명은 각 모듈의 `README.md`를 참조.

## 1. 구조적 의사결정

### 서브모듈(`spatial_toolbox`)과 프로젝트 레이어 분리 기준

**원칙: 프로젝트 고유 정책이 아닌, 재사용 가능한 도메인·렌더 코어는 서브모듈로 분리함.**

- `spatial_toolbox.scene` — 씬 그래프(`Base_Node`·`Controller`), 에셋 캐시(`ASSET_CACHE`), 파일 I/O(`Geometry_Process`). 프로젝트 외부에서도 독립적으로 사용 가능하므로 서브모듈에 배치함.
- `spatial_toolbox.graphics` — `Base_Renderer`/`Base_Pass` 추상 + `OpenGL_Renderer`와 RGB/Depth/Normal/Segmentation 패스 구현. 렌더 API 전환(Vulkan/Metal 등) 선택권을 유지하기 위해 프로젝트와 분리함.
- 최상위 `viewport/`·`simulation/`·`ui/` — FOCUS 전용 편집기 UX·데이터셋 수집 정책·Qt 통합 코드로, 재사용 가능성이 낮아 프로젝트에 잔존함.

이 경계가 깨지면 서브모듈이 편집기 상태나 Qt를 끌고 들어오게 됨. 서브모듈 내부에 `PySide6`·`viewport`·`simulation`·`ui` import를 추가하지 말 것.

### `viewport/` 와 `simulation/` 를 합치지 않은 이유

동일한 렌더 코어(`spatial_toolbox.graphics.openGL.OpenGL_Renderer`)를 공유하지만 관심사가 다름:

| | `viewport/` | `simulation/` |
| --- | --- | --- |
| 카메라 입력 | `Orbit_Camera` (마우스 극좌표) | `Camera` 씬 노드 (`world_matrix` 역행렬) |
| 상태 의존 | `selected_node`, `render_mode`, 기즈모 | 없음 (stateless 패스 실행) |
| 실행 환경 | `QOpenGLWidget` (디스플레이 필수) | EGL / `QOffscreenSurface` (헤드리스 가능) |
| 출력 | 화면 픽셀 | PNG / NPY / JSON 파일 |

합칠 경우 헤드리스 모드에서 편집기 상태(`selected_node` 등)에 대한 의존성을 끌고 가야 하고, 편집기 렌더러에 데이터 생성 로직이 섞이게 됨.

### `Camera_Intrinsic` 과 `Orbit_Camera` 분리

- `Camera_Intrinsic` (`spatial_toolbox.scene.node.camera`): 물리 카메라의 광학 파라미터 **정의**. `Camera` 노드의 `intrinsic` 필드에 연결되어 씬의 일부로 직렬화됨.
- `Orbit_Camera` (`viewport/view.py`): 편집기 내비게이션 **도구**. 극좌표 → `gluLookAt` 변환만 수행하며 씬에 포함되지 않음.

가상 촬영 시 카메라는 `Camera`(`prim_type="Camera"`) 노드로 씬에 배치되며, `Orbit_Camera`는 해당 노드를 바라보는 편집기 시점일 뿐임. 단, `Orbit_Camera.Update_projection`은 fov 파라미터를 fx/fy로 역산 후 `spatial_toolbox.scene.node.camera.Build_gl_projection`을 호출하여 편집기/씬 카메라가 동일 투영 빌더를 공유함.

### 씬 그래프가 `graphics/`가 아닌 `scene/`에 있는 이유

`Base_Node`는 프로젝트 전체의 핵심 데이터 구조이며 소비자가 렌더러(`graphics/`), 뷰포트, 시뮬레이션 파이프라인, UI 편집기에 걸쳐 있음. 렌더 서브모듈 내부(`graphics/scene/`)에 두면 `graphics/` 내부 모듈 간 의존이 복잡해지고, 향후 USD 익스포터 등 씬 데이터를 직접 처리하는 모듈이 렌더링 레이어를 역참조하게 됨. `scene/`을 독립 서브모듈로 분리한 결과 `graphics/`는 `scene/`을 소비만 하고, `scene/`은 외부 서브모듈 의존이 없는 단방향 경계가 유지됨.

## 2. python_toolbox 활용 패턴

`submodules/python_toolbox/`의 베이스 클래스가 프로젝트·서브모듈 양쪽에서 사용됨.

### Data_Schema

선언적 직렬화를 제공하는 dataclass 베이스. `__exclude_serialize__`, `__custom_keys__`, `__custom_serializers__`로 필드별 직렬화 정책을 지정함.

```python
from python_toolbox.data_schema import Data_Schema

@dataclass
class My_Node(Data_Schema):
    local_matrix: np.ndarray = ...
    __custom_keys__ = {"local_matrix": "local_matrix_meta"}
    __custom_serializers__ = {"local_matrix": lambda m: m.flatten().tolist()}
```

현재 사용처:

- `Base_Node`·`Base_Asset`·`Camera_Intrinsic`·`Asset_Cache` (`spatial_toolbox.scene.*`)

### Base_Config

설정값 직렬화 및 파일 I/O를 위한 dataclass 베이스.

```python
from python_toolbox.project import Base_Config

@dataclass
class My_Config(Base_Config):
    value: int = 0

cfg = My_Config(value=42)
cfg.Serialize()              # → {"value": 42}
cfg.Write_to("config.json", save_dir)
```

현재 사용처:

- `Render_Config`·`Randomize_Range` (`simulation/config.py`)

### Registry

타입 안전 모듈 등록 시스템. 데코레이터 기반으로 클래스를 등록하고 문자열 키로 조회함.

```python
from python_toolbox.registry import Registry

registry = Registry[type[Base_Class]]("name", Base_Class)

@registry.Register_module("key")
class My_Class(Base_Class): ...

instance = registry.Get("key")()
```

현재 사용처:

- `ASSET_REGISTRY`·`NODE_REGISTRY` (`spatial_toolbox.scene.register`) — 노드/에셋 JSON 역직렬화 시 `prim_type` → 클래스 해석에 사용
- `Pass_Registry` (`spatial_toolbox.graphics.registry`) — 렌더 패스 등록

### Project_Template

Setup → Run 생명주기를 강제하는 프로젝트 실행 템플릿. 타임스탬프 기반 고유 워크스페이스를 자동 생성함.

```python
from python_toolbox.project import Project_Template

class My_Project(Project_Template):
    def __init__(self):
        super().__init__("project_name")

    def Run(self):
        # self.workspace → Path("./result/project_name/<timestamp>_<uuid>")
        ...
```

현재 사용처:

- `Capture_Project` (`simulation/engine.py`) — 헤드리스 데이터 생성

## 3. 네이밍 규칙

| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| 클래스 | Pascal_Case (언더스코어 구분) | `Base_Node`, `Controller` |
| 공개 메서드 | Pascal_Case | `Add_node()`, `Render_frame()` |
| 비공개 메서드 | _Pascal_Case | `_Draw_mesh()`, `_Setup_ui()` |
| 지역 변수 | _snake_case (언더스코어 접두사) | `_target`, `_new_node` |
| 인스턴스 변수 | snake_case | `self.root`, `self.active_axis` |
| 모듈/파일 | snake_case | `scene_tree.py`, `openGL/pass_/base.py` |

사용자의 네이밍 스타일을 변경하지 않음. 오타만 수정.

## 4. 향후 확장 지점

### 동적 분석기

단위시간 간격 시뮬레이션. 예상 배치 위치:

```txt
submodules/spatial_toolbox/spatial_toolbox/
└── scene/
    └── physics/          # 물리 파라미터 정의 (중력, 충돌 속성 등, Data_Schema 기반)

simulation/
└── dynamics/             # 시뮬레이션 루프, 시간 스텝 관리
    ├── engine.py         # 물리 엔진 래퍼
    └── recorder.py       # 프레임별 상태 기록 (pipeline 연동)
```

`Render_Pipeline`을 프레임별로 반복 호출하여 시계열 데이터셋을 생성하는 구조가 자연스러움.

### AI 모델 학습기

예상 배치 위치:

```txt
training/             # 프로젝트 최상위 독립 모듈
├── dataset.py        # simulation/exporter 출력물을 PyTorch Dataset으로 래핑
├── model/            # 모델 정의
└── trainer.py        # 학습 루프 (Project_Template 상속)
```

`spatial_toolbox`나 `simulation`에 대한 의존 없이 `Result_Exporter`가 생성한 파일(PNG, npy, JSON)만 소비하는 구조가 이상적임.

### 새 파일 포맷 추가

`spatial_toolbox.scene.file.loader` 의 `_REGISTRY` 딕셔너리에 확장자 → `Geometry_Process` 서브클래스를 등록:

```python
_REGISTRY: dict[str, type[Geometry_Process]] = {
    ".obj": Obj,
    ".gltf": Gltf,   # 새 포맷 추가
}
```

서브클래스는 `Read_from(file) -> trimesh.Geometry` 클래스메서드를 구현해야 함. 에셋/노드 도메인 객체로의 조립은 `Asset_Cache.Add_from_file` 과 `Controller.Add_from_file` 이 담당하므로 포맷 레이어는 raw 변환만 책임짐.

### 새 렌더 패스 추가

`spatial_toolbox.graphics.openGL.pass_.base.OpenGL_Base_Pass` 를 상속하여 클래스 속성 선언형으로 정의함. 자세한 템플릿은 [submodules/spatial_toolbox/spatial_toolbox/graphics/openGL/COOKBOOK.md](submodules/spatial_toolbox/spatial_toolbox/graphics/openGL/COOKBOOK.md) 참조.

```python
from spatial_toolbox.graphics.openGL.pass_.base import OpenGL_Base_Pass
from spatial_toolbox.graphics.registry import Pass_Registry

@Pass_Registry.Register_module("optical_flow")
class Optical_Flow_Pass(OpenGL_Base_Pass):
    name = "optical_flow"
    _use_lighting = False
    _readback_format = "rgb"
```

`Render_Config.passes` 리스트에 이름을 추가하면 파이프라인이 자동으로 인스턴스화 + `Configure` 훅 호출 + 순차 실행을 수행함.
