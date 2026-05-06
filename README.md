# FOCUS

FOCUS는 3D 씬을 편집하고, 같은 장면으로 실시간 검토와 오프라인 데이터셋 캡처를 수행하는 Python 기반 도구임.

핵심 구성은 세 파트로 나뉨.

- `viewport/`: 편집기 내부의 실시간 OpenGL 뷰포트
- `simulation/`: `Sim_Config` 기반 오프라인 캡처 진입점
- `ui/`: PySide6 편집기 레이어

실제 씬 그래프, 렌더 백엔드, 캡처 엔진의 기반 코어는 `submodules/spatial_toolbox/`가 제공함.

```text
submodules/spatial_toolbox
    ├── scene/
    ├── render/
    └── simulation/
             ▲
             │
    viewport/ simulation/
             ▲
             │
            ui/
```

## 설계 경계

- `spatial_toolbox`는 재사용 가능한 코어 라이브러리이고, FOCUS는 이를 소비하는 애플리케이션 계층임
- `viewport/`는 편집기 전용 실시간 검토 도구이며, scene graph 저장 규약에는 관여하지 않음
- `simulation/`은 캡처 실행 진입점만 담당하고, 샘플링/저장 규약은 `spatial_toolbox.simulation`에 둠
- `ui/`는 `EVENT_BUS` 기반으로 패널을 느슨하게 연결함

## 패키지 구조

```text
FOCUS/
├── app.py
├── capture_cli.py
├── README.md
├── COOKBOOK.md
├── ui/
│   ├── README.md
│   └── COOKBOOK.md
├── viewport/
│   ├── README.md
│   └── COOKBOOK.md
├── simulation/
│   ├── README.md
│   └── COOKBOOK.md
└── submodules/
    └── spatial_toolbox/
```

## 실행

Python `3.11+` 기준.

```bash
pip install -e .
python app.py
```

헤드리스 배치 캡처는 아래처럼 실행함.

```bash
python capture_cli.py --render_cfg path/to/sim_config.json
```

## 문서

| 문서 | 역할 |
|---|---|
| [COOKBOOK.md](./COOKBOOK.md) | 상위 실행 흐름과 빠른 시작 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 설계 의사결정 및 구조 메모 |
| [ROADMAP.md](./ROADMAP.md) | 진행 현황과 TODO |
| [ui/README.md](./ui/README.md) | 편집기 UI 레이어 개요 |
| [ui/COOKBOOK.md](./ui/COOKBOOK.md) | UI 실행/이벤트/패널 확장 예제 |
| [viewport/README.md](./viewport/README.md) | 실시간 뷰포트 코어 개요 |
| [viewport/COOKBOOK.md](./viewport/COOKBOOK.md) | 카메라/픽킹/기즈모 사용 예제 |
| [simulation/README.md](./simulation/README.md) | 오프라인 캡처 진입점 개요 |
| [simulation/COOKBOOK.md](./simulation/COOKBOOK.md) | CLI/코드 기반 배치 캡처 예제 |
| [submodules/spatial_toolbox/README.md](./submodules/spatial_toolbox/README.md) | 코어 라이브러리 전체 개요 |
| [submodules/spatial_toolbox/COOKBOOK.md](./submodules/spatial_toolbox/COOKBOOK.md) | 코어 라이브러리 빠른 시작 |
