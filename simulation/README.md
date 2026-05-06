# simulation

`simulation/`은 FOCUS의 오프라인 캡처 어댑터 계층임. 실제 랜덤화 규약, 캡처 엔진, 결과 저장 포맷은 `submodules/spatial_toolbox/spatial_toolbox/simulation/`이 제공하고, 이 디렉터리는 프로젝트 진입점과 UI 연동을 담당함.

```text
submodules/spatial_toolbox.simulation  ──►  simulation/
```

## 역할

- `engine.py`는 `Sim_Config` JSON을 읽고 씬을 로드한 뒤 `Blender_Capture_Engine` 호출까지 연결함
- `__init__.py`는 `spatial_toolbox.simulation` 공개 API를 재수출함
- `capture_cli.py`와 `ui/panels/simulation/`이 이 모듈을 공통 진입점으로 사용함

## 구조

```text
simulation/
├── __init__.py        # spatial_toolbox.simulation public API re-export
├── README.md
└── engine.py          # Run_batch_capture(config_path, progress_callback)
```

## 실행 흐름

```text
Sim_Config JSON
    │
    ▼
simulation.engine.Run_batch_capture(...)
    │
    ├── Read_from(config_path) -> Sim_Config(**data)
    ├── Controller().Import(scene_path)
    └── Blender_Capture_Engine().Capture(...)
```

`Run_batch_capture()`는 출력 폴더를 `scene_path` 기준으로 `<scene_stem>/`에 생성하고, 진행 상황 콜백을 그대로 엔진에 전달함.

## 문서

- 상위 사용 흐름: [COOKBOOK.md](./COOKBOOK.md)
- 캡처 엔진/랜덤화 세부 규약: [submodules/spatial_toolbox/spatial_toolbox/simulation/README.md](../submodules/spatial_toolbox/spatial_toolbox/simulation/README.md)
- 캡처 레시피: [submodules/spatial_toolbox/spatial_toolbox/simulation/COOKBOOK.md](../submodules/spatial_toolbox/spatial_toolbox/simulation/COOKBOOK.md)
