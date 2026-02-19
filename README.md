# Automated Server Administration Platform (ASAP)

ASAP는 리눅스 서버 초기 설정과 유지보수를 위한 TUI 기반 자동화 플랫폼입니다. `bash`와 `dialog`를 활용해 복잡한 관리 작업을 직관적인 인터페이스로 통합합니다.

## 프로젝트 개요

- 목표: 서버 인프라 구축의 코드 기반 자동화
- 설계 원칙:
  - 선언적 관리: `.conf` 프로필 기반의 상태 정의
  - 멱등성 유지: 반복 실행 시에도 시스템 무결성 보장
  - 자가 치유(Self-Healing): UUID/PTUUID 추적을 통한 스토리지 경로 보호
- OS: Ubuntu/Debian 기반 리눅스 지원

## 주요 기능 (Key Features)

### 1. 지능형 권한 제어

- 권한 자동 감지: 실행 사용자(Root/일반)에 따른 메뉴 구성 최적화
- 최소 권한 원칙: 필요한 시점에만 `sudo`를 호출하여 보안성 강화

### 2. 선언적 스토리지 관리

- 프로필 기반 자동화: `LVM`, `CIFS`, `Direct Disk` 마운트 통합 관리
- 자가 치유 매커니즘: 디스크 경로 변동 시 PTUUID/UUID 기반 설정 자동 갱신
- 고급 LVM 구성: PV/VG/LV 생성 및 SSD 캐시(Cache Pool) 연동 지원

### 3. 하이브리드 네트워크 스택

- 듀얼 스택 지원: `network-manager`와 `systemd-networkd` 환경 자동 대응
- 고급 토폴로지: 본딩(Active-Backup, LACP) 및 티밍 설정을 TUI로 처리
- 연결 설정: 고정 IP, 게이트웨이, DNS, `/etc/hosts` 매핑 자동화

### 4. 모듈형 소프트웨어 프로비저닝

- 표준화된 파이프라인: 4단계(검증-의존성-빌드-설치) 표준 구조 기반의 설치 로직 적용
- 스마트 업그레이드: 시스템 도구(CMake 등) 버전 미달 시 최신 바이너리 자동 확보 및 빌드 환경 최적화
- 계층형 아키텍처: 인프라 기초(BASE), 실행 환경(PLATFORM), 개발 도구(DEV)로 구분된 단계적 설치
- 패키지 관리: APT 의존성 자동 확인 및 대량 설치/제거 지원

### 5. 시스템 텔레메트리

- 하드웨어 감사: CPU, GPU, 메모리, 보드 정보를 심층 스캔
- 데이터 직렬화: 수집된 자산 정보를 외부 연동용 `JSON`으로 내보내기

## 소프트웨어 설치 표준 (Installation Standard)

ASAP는 유지보수성과 확장성을 위해 모든 소프트웨어 설치에 **4단계 표준 파이프라인**을 적용합니다.

### 1. 4단계 파이프라인 (4-Stage Pipeline)

1. **Stage 1: Verification (환경 검증)** - OS, 아키텍처, 최소 요구 사양 및 기설치 여부 확인
2. **Stage 2: Dependency (의존성 해결)** - 필수 패키지 설치 및 빌드 도구(CMake 등)의 스마트 업그레이드
3. **Stage 3: Build (빌드 및 준비)** - 소스 컴파일 또는 바이너리 확보 및 빌드 메타데이터 기록
4. **Stage 4: Installation (설치 및 동기화)** - 시스템 배치, 환경 변수 설정 및 `state.conf` 상태 기록

### 2. 계층형 구조 (Layered Architecture)

- **Layer 1: BASE** - 인프라 기초 및 공용 빌드 도구 (System Utils, CMake, GCC 등)
- **Layer 2: PLATFORM** - 하드웨어 가속 및 런타임 (NVIDIA Stack, Docker 등)
- **Layer 3: DEV_STACK** - 사용자 개발 환경 및 라이브러리 (Conda, ROS 2, OpenCV 등)

## 요구사항

- OS: Ubuntu 20.04+ / Debian 계열
- Shell: Bash 4.0 이상
- 의존성: `dialog`, `lvm2`, `parted`, `cifs-utils`, `network-manager`

## 설치 및 실행

### 1. 설치

```bash
git clone <Repository_URL> ASAP
cd ASAP
git submodule update --init --recursive
```

### 2. 사용법 (Usage) & 디버깅

기본 실행: 스크립트에 실행 권한을 부여한 후 실행

```bash
chmod +x ASAP.sh
./ASAP.sh
```

로그 저장 (Logging): 실행 중 발생하는 오류나 전체 출력을 파일로 기록

```bash
# 에러 메시지만 'error.log'에 저장 (권장)
./ASAP.sh 2> error.log

# 모든 출력(표준 출력 + 에러)을 'output.log'에 저장
./ASAP.sh > output.log 2>&1
```

디버그 모드 (Debugging): 스크립트의 상세 실행 과정을 추적

```bash
# 실행 과정을 화면에 출력
bash -x ./ASAP.sh

# 실행 과정을 파일로 저장 (분석용)
bash -x ./ASAP.sh 2> debug_trace.log
```

## 프로젝트 구조

- `ASAP.sh`: 메인 엔트리포인트 및 권한 분기
- `script/core/`: 핵심 라이브러리 (파서, 공통 함수)
- `script/system/`: 시스템 관리 로직 (계정, 네트워크, 스토리지)
- `script/install/`: 애플리케이션 자동 설치 스크립트
- `ui/`: `dialog` 기반 TUI 인터페이스 모듈
- `conf/` & `template/`: 설정 파일 및 기본 템플릿

## TODO

- [x] Driver 설치 결과의 Config 파일 연동성 강화
- [x] 원격 마운트 시 Credential 저장 위치 선택 옵션 추가
- [ ] 소프트웨어 설치 표준 구조 적용 (4-Stage Pipeline)
  - [ ] 1단계: 소스코드 확인 및 환경 검증 (Source Verification)
  - [ ] 2단계: OS/배포판/버전별 의존성 파악 및 해결 (Dependency Resolution)
  - [ ] 3단계: 컴파일 및 빌드 프로세스 수행 (Build)
  - [ ] 4단계: 시스템 설치 및 상태 동기화 (Installation)
- [ ] 기존 설치 스크립트(OpenCV, CUDA, Docker 등)의 표준 구조 준수 여부 검토 및 리팩토링
- [ ] Docker/경량 환경을 위한 최적화
  - [ ] 설정 파일 프로필에 따른 백엔드 모듈 선택적 초기화 (Selective Initialization) 로직 도입
  - [ ] 컨테이너 환경 감지 및 시스템 수준 의존성(network-manager 등) 설치 스킵 옵션 추가
