# ASAP 로드맵 (ROADMAP)

개발 방향과 리팩토링 계획을 정리합니다. 기술 부채 해소와 기능 확장을 병행하며 점진적으로 진행합니다.

---

## 현재 상태 (v1.x)

현재 브랜치(`equipped`)가 안정 버전입니다.

**완료된 항목:**
- [x] 4단계 파이프라인 설계 및 OpenCV 기준 구현
- [x] 드라이버 설치 결과의 Config 파일 연동성 강화
- [x] 원격 마운트 시 Credential 저장 위치 선택 옵션 추가
- [x] VS Code 관련 기능 구현

**현재 한계:**
- 기존 설치 스크립트(CUDA, Docker 등)가 4단계 파이프라인을 완전히 준수하지 않음
- Docker/컨테이너 환경에서 일부 시스템 수준 모듈이 불필요하게 초기화됨
- 설치 스크립트와 UI 레이어가 `v1` 구조에 혼재

---

## 리팩토링 전략

기존 시스템의 안정성을 유지하면서 대규모 구조 재편을 수행하기 위해 **스테이징 전략(Staging & Atomic Switch)** 을 사용합니다.

- **격리된 작업 공간**: `script/install_v2/` 및 `ui/install_v2/` 에서 신규 로직 작성
- **독립성 유지**: `v2` 모듈은 기존 `v1` 모듈에 의존하지 않고, 4단계 파이프라인을 100% 준수
- **일괄 전환**: 모든 레이어 구현 완료 후 메인 엔트리포인트의 로드 경로를 `v2`로 일괄 변경

---

## 4단계 표준 파이프라인 상세

`v2` 이후 모든 설치 스크립트가 준수해야 하는 표준입니다.

### Stage 1: Verification (환경 검증)
- OS 버전(Ubuntu 20.04+) 및 CPU 아키텍처(x86_64, aarch64) 확인
- 대상 소프트웨어 빌드에 필요한 최소 빌드 도구 버전 정의
- `is_installed_<app>` 함수로 기존 설치 여부 및 버전 파악

### Stage 2: Dependency (의존성 해결)
- 필수 APT 의존성 및 외부 GPG/저장소 설정
- **Smart Upgrade**: 시스템 CMake 버전 미달 시 최신 바이너리 자동 확보 및 `/usr/local` 배치
- GPU 스택(CUDA/cuDNN) 및 Python 환경과의 버전 호환성 교차 검증

### Stage 3: Build (빌드 및 준비)
- 소스 컴파일(CMake/Make) 또는 바이너리 인스톨러 확보
- 사용된 도구 버전 및 컴파일 옵션을 `.ini` 파일로 메타데이터 기록
- 빌드 실패 시 환경 정리 및 부분 재시도 로직

### Stage 4: Installation (설치 및 동기화)
- 바이너리 경로 설정 및 실행 권한 부여
- `PATH`, `LD_LIBRARY_PATH` 등을 `bashrc` 또는 `profile.d`에 반영
- `state.conf`에 최종 설치 결과 동기화 및 TUI 메뉴 반영

---

## 설치 방식 분류 (Installation Backend)

4단계 파이프라인은 공통 골격이지만, **설치 방식(Backend)** 에 따라 Stage 2·3의 구현이 명확히 달라집니다.  
`v2`부터는 각 스크립트가 어떤 방식으로 소프트웨어를 확보하는지를 명시적으로 선언합니다.

### Backend 유형

| 유형 | 방식 | 대표 도구 | 적합한 소프트웨어 |
|---|---|---|---|
| `pkg` | 패키지 매니저로 바이너리 직접 설치 | `apt`, `pip`, `conda` | Docker, VS Code, 일반 APT 패키지 |
| `build` | 소스에서 직접 컴파일하여 설치 | `cmake` + `make` | OpenCV, 커스텀 빌드가 필요한 라이브러리 |
| `installer` | 공식 인스톨러 스크립트 실행 | `.sh`, `.run` 인스톨러 | NVIDIA Driver, CUDA Toolkit, Miniconda |

### Backend별 파이프라인 동작 차이

```
[ pkg 방식 ]
  Stage 2: APT 저장소/GPG 등록, 의존 패키지 설치
  Stage 3: apt install 또는 pip/conda 명령 실행 (빌드 없음)

[ build 방식 ]
  Stage 2: 빌드 의존성(CMake, GCC 등) Smart Upgrade 포함 설치
  Stage 3: cmake 구성 → make → 빌드 메타데이터(.ini) 기록

[ installer 방식 ]
  Stage 2: 인스톨러 바이너리/스크립트 다운로드 및 체크섬 검증
  Stage 3: 인스톨러 실행 (silent/unattended 옵션 적용)
```

### 스크립트 선언 규칙 (v2 표준)

각 설치 스크립트 상단에 Backend 유형을 선언하여 파이프라인 로더가 올바른 Stage 구현을 선택합니다.

```bash
# install_v2/dev/opencv.sh 예시
INSTALL_BACKEND="build"
INSTALL_LAYER="dev"
INSTALL_DEPS_LAYER=("base" "platform")  # 이 패키지 설치 전 완료되어야 할 레이어
```

---

## 레이어 누적 구조 (Layer Stacking)

소프트웨어 설치는 레이어를 **한 번에 하나씩 순서대로** 쌓아 올리는 구조를 따릅니다.  
각 레이어는 이전 레이어의 완료 상태를 전제로 하며, `state.conf`가 각 레이어의 완료 여부를 추적합니다.

```
설치 흐름:

  ┌─────────────────────────────────────┐
  │  Layer 1: BASE                      │  ← 1순위. 이 레이어가 완료되어야
  │  CMake · GCC · 시스템 유틸리티      │    다음 레이어 진입 가능
  └────────────────┬────────────────────┘
                   │ (완료 확인)
  ┌────────────────▼────────────────────┐
  │  Layer 2: PLATFORM                  │  ← 레이어 내부에서도 순서 존재
  │  Driver → CUDA → cuDNN → Docker    │    (Driver 없이 CUDA 불가)
  └────────────────┬────────────────────┘
                   │ (완료 확인)
  ┌────────────────▼────────────────────┐
  │  Layer 3: DEV_STACK                 │  ← 개발 목적에 따라 선택적 설치
  │  Conda · OpenCV · ROS 2 · VS Code  │
  └─────────────────────────────────────┘
```

### 레이어 내 설치 순서 (PLATFORM 예시)

PLATFORM 레이어 안에서도 의존 관계가 있어 순서를 강제합니다.

```
NVIDIA Driver  (pkg: apt / installer: .run)
      ↓
CUDA Toolkit   (installer: .run — Driver 버전과 호환성 검증 후 진행)
      ↓
cuDNN          (pkg: apt — CUDA 버전에 연동된 저장소 사용)
      ↓
Docker Engine  (pkg: apt — CUDA와 독립적, Driver 이후면 OK)
```

### 상태 추적 및 재개

각 패키지 설치 완료 시 `state.conf`에 레이어와 패키지 정보를 기록합니다.  
중단 후 재실행 시 완료된 패키지는 건너뛰고, 실패 지점부터 재개합니다.

```ini
# state.conf 예시
[BASE]
cmake=3.28.1
gcc=12.3.0

[PLATFORM]
nvidia_driver=535.183.01
cuda=12.2
cudnn=8.9.7
```

---

## 계층형 아키텍처 재편

`install_v2/`의 디렉토리 구조는 의존 계층을 명확히 반영합니다.

```
install_v2/
├── base/        # Layer 1: CMake, GCC, 시스템 유틸리티
├── platform/    # Layer 2: NVIDIA Driver, CUDA, cuDNN, Docker
└── dev/         # Layer 3: Conda, ROS 2, OpenCV, VS Code
```

---

## 구현 단계별 계획

### Phase 1: v2 스테이징 환경 구축
- [ ] `install_v2/` 하위 3개 계층 폴더 구조 생성
- [ ] 재귀적 모듈 로더(Recursive Loader) 구현 및 `v2/init.sh` 작성

### Phase 2: BASE 레이어 구현
- [ ] `install_v2/base/cmake.sh` 신규 생성 (Smart Upgrade 로직 포함)
- [ ] `script/core/package/` 내 버전 비교 유틸리티 함수 보강

### Phase 3: PLATFORM 및 DEV_STACK 리팩토링
- [ ] `cuda.sh`, `docker.sh`, `opencv.sh` 등을 4단계 표준으로 `v2`에 재작성
- [ ] `ui/install_v2/`를 계층 구조에 맞춰 신규 구현

### Phase 4: 일괄 전환 및 검증
- [ ] 메인 로드 경로를 `install_v2`로 변경하여 통합 테스트
- [ ] 안정성 검증 후 기존 `v1` 제거 및 `v2` 정규화

---

## 향후 목표

### 컨테이너 환경 대응
- 설정 파일 프로필에 따른 백엔드 모듈 선택적 초기화(Selective Initialization) 도입
- 컨테이너 환경 자동 감지 및 시스템 수준 의존성(`network-manager` 등) 설치 스킵 옵션

### 확장 가능성
- 새로운 소프트웨어 설치 스크립트 추가 시 4단계 파이프라인 템플릿 제공
- APT 외 패키지 매니저(dnf, pacman) 지원 확대
