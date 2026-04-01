# graphics/render

학습 데이터 생성을 위한 오프라인 멀티패스 렌더링 파이프라인.

하나의 장면(씬 + 카메라)에서 여러 렌더 패스를 순차 실행하여 RGB, Depth, Segmentation, Normal 등의 정답 데이터를 동시에 생성함.

## 구조

```
render/
├── config.py       # Render_Config — 렌더 옵션 (Base_Config 상속)
├── pass_/
│   ├── base.py     # Base_Pass (ABC) + pass_registry (Registry)
│   ├── rgb.py      # Phong 조명 RGB 이미지 (uint8, H×W×3)
│   ├── depth.py    # 선형 미터 단위 뎁스 맵 (float32, H×W)
│   ├── segmentation.py  # RGB 인코딩 인스턴스 ID 맵 (uint8, H×W×3)
│   └── normal.py   # 로컬 법선 RGB 인코딩 맵 (uint8, H×W×3)
├── pipeline.py     # Render_Pipeline — 멀티패스 실행 + 오프스크린 컨텍스트 관리
└── exporter.py     # Result_Exporter — 이미지/메타데이터 저장
```

## 실행 흐름

```
Render_Config
    │
    ▼
Render_Pipeline.Execute(root_node, camera_node)
    │
    ├── RGB_Pass.Render()       → np.ndarray (uint8)
    ├── Depth_Pass.Render()     → np.ndarray (float32)
    ├── Segmentation_Pass.Render() → np.ndarray (uint8)
    └── Normal_Pass.Render()    → np.ndarray (uint8)
    │
    ▼
Result_Exporter.Save(frame_id, results, camera_node, config)
    │
    ├── 000000/rgb.png
    ├── 000000/depth.npy
    ├── 000000/segmentation.png
    ├── 000000/normal.png
    └── 000000/metadata.json   (camera intrinsic/extrinsic + render config)
```

## 렌더 패스 상세

| 패스 | 출력 dtype | 인코딩 |
|---|---|---|
| RGB | uint8 (H×W×3) | Phong 조명 기반 컬러 |
| Depth | float32 (H×W) | 선형 미터 단위. 배경 = 0.0 |
| Segmentation | uint8 (H×W×3) | 인스턴스 ID를 24bit RGB로 인코딩. 배경 = (0,0,0) |
| Normal | uint8 (H×W×3) | 로컬 법선 `(n+1)*127.5`. 배경 = (128,128,255) |

Segmentation 패스는 렌더링 후 `last_id_map` 속성에서 `(R,G,B) → Scene_Node` 매핑을 제공함.

## 새 패스 추가 방법

1. `pass_/` 에 새 파일 생성
2. `Base_Pass`를 상속하고 `@pass_registry.Register_module("이름")`으로 등록
3. `Name` 프로퍼티와 `Render()` 메서드 구현

```python
from graphics.render.pass_.base import Base_Pass, pass_registry

@pass_registry.Register_module("optical_flow")
class Optical_Flow_Pass(Base_Pass):
    @property
    def Name(self) -> str:
        return "optical_flow"

    def Render(self, root_node, camera_node, width, height):
        # OpenGL 드로우 콜 + glReadPixels
        ...
```

4. `Render_Config.passes` 리스트에 `"optical_flow"` 추가 — `pipeline.py` 수정 불필요

## Render_Config 주요 필드

| 필드 | 기본값 | 설명 |
|---|---|---|
| `width` / `height` | 1920 / 1080 | 출력 해상도 |
| `passes` | `["rgb", "depth", "segmentation", "normal"]` | 실행할 패스 이름 목록 |
| `output_dir` | `"./result"` | 출력 루트 디렉토리 |
| `bg_color` | `[0.0, 0.0, 0.0]` | 배경색 (RGB, 0.0~1.0) |

`Base_Config` 상속이므로 `Serialize()`, `Write_to()`, `Read_from_file()` 사용 가능.

## 실행 모드

**UI 연동 (편집기 내)**
```python
pipeline = Render_Pipeline(config)
results = pipeline.Execute(root_node, camera_node)
```

**헤드리스 (capture_cli.py)**
```python
config = Render_Config(width=640, height=480, passes=["rgb", "depth"])
project = Capture_Project(config)
project._Setup()
project.Run(root_node, camera_node)  # 오프스크린 컨텍스트 자동 생성/해제
```
