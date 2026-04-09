# Automated Server Administration Platform (ASAP)

> 리눅스 서버의 초기 구성과 유지보수를 위한 TUI 기반 자동화 플랫폼

`bash`와 `dialog`만으로 구동되며, 복잡한 인프라 관리 작업을 선언적 설정 파일과 직관적인 인터페이스로 통합합니다.

---

## 설계 이념 (Design Philosophy)

ASAP의 모든 설계 결정은 다음 원칙에서 출발합니다.

### 선언형 관리 (Declarative Management)
"무엇을 실행할 것인가"가 아닌 **"시스템이 어떤 상태여야 하는가"** 를 `.conf` 프로필로 정의합니다. 스토리지 구성, 네트워크 토폴로지, 설치 목록 모두 설정 파일이 진실의 원천(Source of Truth)입니다.

### 멱등성 보장 (Idempotence)
모든 동작은 몇 번을 반복 실행해도 동일한 결과를 냅니다. `state.conf`로 설치 상태를 추적하여 중복 작업과 충돌을 방지합니다.

### 자가 치유 (Self-Healing)
디스크 경로(`/dev/sdX`)는 재부팅마다 바뀔 수 있습니다. ASAP는 장치를 `PTUUID`/`UUID`로 추적하여, 경로가 변경되더라도 설정을 자동으로 복구합니다.

### 최소 권한 원칙 (Least Privilege)
`sudo`는 반드시 필요한 순간에만 요청합니다. 실행 사용자(root/일반 사용자)를 감지하여 메뉴와 기능을 맥락에 맞게 구성합니다.

### 계층형 의존성 (Layered Architecture)
소프트웨어 설치는 의존 관계에 따라 세 계층으로 분리됩니다. 상위 계층은 하위 계층의 완성을 전제합니다.

```
┌─────────────────────────────────────────┐
│  Layer 3: DEV_STACK                     │
│  Conda · ROS 2 · OpenCV · VS Code       │
├─────────────────────────────────────────┤
│  Layer 2: PLATFORM                      │
│  NVIDIA Driver · CUDA · cuDNN · Docker  │
├─────────────────────────────────────────┤
│  Layer 1: BASE                          │
│  CMake · GCC · 시스템 유틸리티          │
└─────────────────────────────────────────┘
```

---

## 주요 기능

| 영역 | 기능 |
|---|---|
| 스토리지 | LVM (RAID0, SSD 캐시), CIFS 원격 마운트, Direct Disk |
| 네트워크 | 고정 IP, 본딩(Active-Backup / LACP), systemd-networkd / NetworkManager |
| 소프트웨어 | 4단계 표준 파이프라인 기반 설치 (검증→의존성→빌드→설치) |
| 계정 관리 | 사용자/그룹 생성, SSH 키 관리, sudo 권한 |
| 모니터링 | CPU/GPU/메모리 하드웨어 감사, JSON 내보내기 |
| 자동화 | `ASAP_auto.sh`로 설정 파일 기반 무인(Unattended) 프로비저닝 |

---

## 프로젝트 구조

```
ASAP/
├── ASAP.sh              # 메인 진입점 (대화형)
├── ASAP_auto.sh         # 자동화 진입점 (무인 프로비저닝)
├── template/            # 설정 파일 템플릿
│   ├── config.conf          # 대화형 모드용 기본 프로필
│   └── config_for_auto.conf # 자동화 모드용 프로필
├── script/
│   ├── core/            # 핵심 라이브러리 (git 서브모듈)
│   │   ├── base/            # 시스템 컨텍스트, 로깅, 프로필 파싱
│   │   ├── package/         # 패키지 관리 추상화 (apt 등)
│   │   └── ui/              # dialog 위젯 공통 함수
│   ├── system/          # 시스템 관리 로직
│   │   ├── 02_account.sh
│   │   ├── 02_network.sh
│   │   ├── 02_storage.sh
│   │   └── 02_samba.sh
│   └── install/         # 소프트웨어 설치 스크립트
│       ├── cuda.sh
│       ├── docker.sh
│       ├── opencv.sh    # 4단계 파이프라인 구현 예시
│       └── ...
├── ui/                  # TUI 인터페이스 레이어 (dialog 래퍼)
│   ├── system/
│   ├── install/
│   └── user/
└── manual/              # 서비스별 수동 설치 가이드
```

---

## 요구사항

- **OS**: Ubuntu 20.04+ / Debian 계열
- **Shell**: Bash 4.0 이상
- **런타임 의존성**: `dialog`, `lvm2`, `parted`, `cifs-utils`, `network-manager`

---

## 설치 및 실행

### 설치

```bash
git clone <Repository_URL> ASAP
cd ASAP
git submodule update --init --recursive
```

### 대화형 실행

```bash
chmod +x ASAP.sh
./ASAP.sh
```

### 자동화 실행

설정 파일을 준비한 뒤 비대화형으로 실행합니다.

```bash
# 템플릿 복사 후 수정
cp template/config_for_auto.conf my_server.conf
vim my_server.conf

./ASAP_auto.sh my_server.conf
```

### 디버깅

```bash
# 에러 로그만 저장
./ASAP.sh 2> error.log

# 전체 실행 추적
bash -x ./ASAP.sh 2> debug_trace.log
```

---

## 문서

- **[ROADMAP.md](ROADMAP.md)** — 개발 방향, 리팩토링 계획, 향후 목표
- **[COOKBOOK.md](COOKBOOK.md)** — 실제 사용 시나리오 및 단계별 예시
- **[manual/](manual/)** — 서비스별 상세 설치 가이드
