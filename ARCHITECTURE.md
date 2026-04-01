# Architecture

프로젝트 구조의 설계 근거, 공통 패턴, 확장 방향을 기록함.

현재 상태에 대한 설명은 각 모듈의 `README.md`를 참조.

## 1. 구조적 의사결정

### data/ 와 graphics/ 분리 기준

**원칙: OpenGL 호출이 존재하는가?**

- `Scene_Node`, `Stage_Controller`, `Camera_Intrinsic`은 전부 순수 dataclass 또는 트리 조작 로직임. OpenGL 코드가 한 줄도 없으므로 `data/`에 배치.
- `data/`는 프로젝트 내 어떤 모듈에도 의존하지 않음. 이 단방향 원칙이 깨지면 순환 참조가 발생하므로 `data/`에 `graphics/` 임포트를 추가하지 말 것.

### viewport/ 와 render/ 를 합치지 않은 이유

동일한 드로우 코어(`core/draw.py`)를 공유하지만 관심사가 다름:

| | viewport/ | render/ |
| --- | --- | --- |
| 카메라 입력 | `Orbit_Camera` (마우스 극좌표) | `Scene_Node` (world_matrix 역행렬) |
| 상태 의존 | `selected_node`, `render_mode`, 기즈모 | 없음 (stateless 패스 실행) |
| 실행 환경 | QOpenGLWidget (디스플레이 필수) | QOffscreenSurface (헤드리스 가능) |

합칠 경우 헤드리스 모드에서 편집기 상태(`selected_node` 등)에 대한 의존성을 끌고 가야 하고, 편집기 렌더러에 데이터 생성 로직이 섞이게 됨.

### Camera_Intrinsic 과 Orbit_Camera 분리

- `Camera_Intrinsic` (`data/model/camera.py`): 물리 카메라의 광학 파라미터 **정의**. `Scene_Node.intrinsic` 필드에 연결되어 씬의 일부로 직렬화됨.
- `Orbit_Camera` (`graphics/viewport/view.py`): 편집기 내비게이션 **도구**. 극좌표 → gluLookAt 변환만 수행하며 씬에 포함되지 않음.

가상 촬영 시 카메라는 `Scene_Node(prim_type="Camera")`로 씬에 배치되며, `Orbit_Camera`는 해당 노드를 바라보는 편집기 시점일 뿐임.

### scene/ 이 graphics/ 가 아닌 data/ 에 있는 이유

`Scene_Node`는 프로젝트 전체의 핵심 데이터 구조이며 소비자가 `graphics/` 내부의 모든 하위 모듈(viewport, render, ui)에 걸쳐 있음. `graphics/scene/`에 두면 `graphics/` 내부 모듈 간의 의존 관계가 복잡해지고, 향후 `data/`에서 씬 데이터를 직접 처리하는 모듈(USD 익스포터 등)이 `graphics/`를 역참조하게 됨.

## 2. python_toolbox 활용 패턴

`submodules/python_toolbox/`의 세 가지 베이스 클래스가 프로젝트 전반에서 사용됨.

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
- `Render_Config` (`graphics/render/config.py`)
- `Camera_Intrinsic` (`data/model/camera.py`)

### Registry

타입 안전 모듈 등록 시스템. 데코레이터 기반으로 클래스를 등록하고 문자열 키로 조회함.

```python
from python_toolbox.project import Registry

registry = Registry("name", Base_Class)

@registry.Register_module("key")
class My_Class(Base_Class): ...

instance = registry.Get("key")()
```

현재 사용처:
- `pass_registry` (`graphics/render/pass_/base.py`) — 렌더 패스 등록

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

project = My_Project()
project._Setup()  # 워크스페이스 디렉토리 생성
project.Run()
```

현재 사용처:
- `Capture_Project` (`capture_cli.py`) — 헤드리스 데이터 생성

## 3. 네이밍 규칙

| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| 클래스 | Pascal_Case (언더스코어 구분) | `Scene_Node`, `Stage_Controller` |
| 공개 메서드 | Pascal_Case | `Add_node()`, `Render_frame()` |
| 비공개 메서드 | _Pascal_Case | `_Draw_mesh()`, `_Setup_ui()` |
| 지역 변수 | _snake_case (언더스코어 접두사) | `_target`, `_new_node` |
| 인스턴스 변수 | snake_case | `self.root`, `self.active_axis` |
| 모듈/파일 | snake_case | `scene_tree.py`, `pass_/base.py` |

사용자의 네이밍 스타일을 변경하지 않음. 오타만 수정.

## 4. 향후 확장 지점

### 동적 분석기

단위시간 간격 시뮬레이션. 예상 배치 위치:

```txt
data/
└── physics/          # 물리 파라미터 정의 (중력, 충돌 속성 등)

graphics/
└── simulator/        # 시뮬레이션 루프, 시간 스텝 관리
    ├── engine.py     # 물리 엔진 래퍼
    └── recorder.py   # 프레임별 상태 기록 (render/pipeline 연동)
```

`render/pipeline`을 프레임별로 반복 호출하여 시계열 데이터셋을 생성하는 구조가 자연스러움.

### AI 모델 학습기

예상 배치 위치:

```txt
training/             # graphics/ 외부 독립 모듈
├── dataset.py        # render/exporter 출력물을 PyTorch Dataset으로 래핑
├── model/            # 모델 정의
└── trainer.py        # 학습 루프 (Project_Template 상속)
```

`graphics/`에 대한 의존 없이 `render/exporter`가 생성한 파일(PNG, npy, JSON)만 소비하는 구조가 이상적임.

### 새 파일 포맷 추가

`data/io/loader.py`의 `_LOADER_REGISTRY` 딕셔너리에 확장자 → 파서 함수를 등록:

```python
_LOADER_REGISTRY = {
    ".obj": load_obj,
    ".gltf": load_gltf,  # 새 파서 추가
}
```

파서 함수는 `Path → Scene_Node`를 반환해야 함.

### 새 렌더 패스 추가

`graphics/render/README.md`의 "새 패스 추가 방법" 섹션 참조. `Base_Pass` 상속 + `@pass_registry.Register_module()` 데코레이터 + `Render_Config.passes` 목록에 이름 추가.
