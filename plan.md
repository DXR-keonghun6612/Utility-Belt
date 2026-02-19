# ASAP 소프트웨어 설치 표준화 및 구조 재편 계획

본 문서는 ASAP 플랫폼의 유지보수성 향상과 설치 자동화의 신뢰성 확보를 위한 기술적 리팩토링 로드맵을 정의합니다.

## 1. 스테이징 전략 (Staging & Atomic Switch)

기존 시스템의 안정성을 저해하지 않고 대규모 리팩토링을 수행하기 위해 **Staging 환경**을 활용합니다.

- **격리된 작업 공간:** `script/install_v2/` 및 `ui/install_v2/` 디렉토리를 생성하여 모든 신규 로직을 작성합니다.
- **독립성 유지:** `v2` 모듈은 기존 `v1` 모듈에 의존하지 않으며, 신규 표준(4-Stage Pipeline)을 100% 준수합니다.
- **일괄 전환:** 모든 레이어의 구현이 완료된 후, 메인 엔트리포인트의 로드 경로를 `v2`로 일괄 전환하여 업그레이드를 완료합니다.

## 2. 4단계 표준 파이프라인 (4-Stage Pipeline)

모든 설치 스크립트는 시스템 상태를 예측 가능하게 관리하기 위해 아래의 단계를 준수합니다.

### Stage 1: Verification (환경 검증)

- **호환성 판별:** OS 버전(Ubuntu 20.04+) 및 CPU 아키텍처(x86_64, aarch64) 확인
- **사양 정의:** 대상 소프트웨어 빌드에 필요한 최소 빌드 도구 버전 정의
- **상태 감지:** 기존 설치 여부 및 버전 정보를 `is_installed_<app>` 함수로 파악

### Stage 2: Dependency (의존성 해결)

- **패키지 확보:** 필수 APT 의존성 및 외부 GPG/저장소 설정
- **Smart Upgrade:** 시스템 CMake 버전이 미달할 경우 최신 바이너리(.sh) 자동 설치 및 `/usr/local` 배치
- **교차 검증:** GPU 스택(CUDA/cuDNN) 및 Python 환경과의 버전 호환성 체크

### Stage 3: Build (빌드 및 준비)

- **프로세스 수행:** 소스 컴파일(CMake/Make) 또는 바이너리 인스톨러 확보
- **메타데이터 기록:** 사용된 도구 버전 및 컴파일 옵션을 `.ini` 파일로 저장
- **자가 치유:** 빌드 실패 시 환경 정리 및 부분 재시도 로직 실행

### Stage 4: Installation (설치 및 동기화)

- **시스템 배치:** 바이너리 경로 설정 및 실행 권한 부여
- **환경 변수:** `PATH`, `LD_LIBRARY_PATH` 등을 `bashrc` 또는 `profile.d`에 반영
- **상태 기록:** `state.conf`에 최종 설치 결과 동기화 및 TUI 메뉴 반영

---

## 3. 계층형 아키텍처 (Layered Architecture)

사용자 설치 흐름과 소프트웨어 의존 관계에 따라 UI 및 디렉토리 구조를 재편합니다.

### Layer 1: BASE (인프라 기초)

- **위치:** `install_v2/base/`
- **주요 항목:** 시스템 필수 유틸리티, 최신 CMake, GCC/G++, 빌드 도구 모음
- **역할:** 상위 계층의 모든 컴파일 및 빌드 환경 지원

### Layer 2: PLATFORM (런타임 인프라)

- **위치:** `install_v2/platform/`
- **주요 항목:** NVIDIA Driver, CUDA Toolkit, cuDNN, Docker Engine
- **역할:** 하드웨어 가속 및 컨테이너 기반 실행 환경 제공

### Layer 3: DEV_STACK (개발 환경)

- **위치:** `install_v2/dev/`
- **주요 항목:** Miniconda/Anaconda, ROS 2, OpenCV, VS Code
- **역할:** 특정 프로젝트 목적에 맞는 개발 툴킷 및 라이브러리 완성

---

## 4. 세부 구현 로드맵

### Phase 1: v2 스테이징 환경 구축

- [ ] `install_v2` 하위 3개 계층 폴더 구조 생성
- [ ] 재귀적 모듈 로더(Recursive Loader) 구현 및 `v2/init.sh` 작성

### Phase 2: 빌드 도구 및 BASE 레이어 구현

- [ ] `install_v2/base/cmake.sh` 신규 생성 (Smart Upgrade 로직 포함)
- [ ] `script/core/package/` 내 버전 비교 유틸리티 함수 보강

### Phase 3: PLATFORM 및 DEV_STACK 리팩토링

- [ ] `opencv.sh`, `cuda.sh`, `docker.sh` 등을 4단계 표준 구조로 `v2`에 재작성
- [ ] UI 레이어(`ui/install_v2/`)를 계층 구조에 맞춰 신규 구현

### Phase 4: 일괄 전환 및 검증

- [ ] 메인 로드 경로를 `install_v2`로 변경하여 통합 테스트 수행
- [ ] 안정성 검증 후 기존 `v1` 제거 및 `v2` 정규화

