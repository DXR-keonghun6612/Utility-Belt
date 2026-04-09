# ASAP 사용 예시 모음 (COOKBOOK)

실제 서버 운영 시나리오별 단계별 가이드입니다. 각 예시는 독립적으로 참고할 수 있습니다.

---

## 목차

1. [신규 서버 초기 세팅 (End-to-End)](#1-신규-서버-초기-세팅)
2. [스토리지 구성](#2-스토리지-구성)
3. [네트워크 구성](#3-네트워크-구성)
4. [GPU 서버 구축](#4-gpu-서버-구축)
5. [개발 환경 구성](#5-개발-환경-구성)
6. [자동화 모드 사용](#6-자동화-모드-사용)
7. [트러블슈팅](#7-트러블슈팅)

---

## 1. 신규 서버 초기 세팅

Ubuntu 22.04가 설치된 베어메탈 서버를 처음 셋업하는 전체 흐름입니다.

### 1-1. ASAP 설치

```bash
git clone <Repository_URL> ASAP
cd ASAP
git submodule update --init --recursive
chmod +x ASAP.sh
```

### 1-2. 실행 및 메뉴 탐색

```bash
./ASAP.sh
```

root로 실행하면 시스템 관리 메뉴(스토리지, 네트워크, 계정)가 전부 활성화됩니다.  
일반 사용자로 실행하면 사용자 수준 항목(SSH, Git 설정)만 표시됩니다.

### 1-3. 권장 초기화 순서

```
1. [시스템] 계정 관리     → 운영 계정 생성, sudo 권한 부여
2. [시스템] 네트워크      → 고정 IP 설정
3. [시스템] 스토리지      → 데이터 디스크 마운트
4. [설치]   BASE 레이어   → CMake, GCC 최신화
5. [설치]   소프트웨어    → 필요한 애플리케이션 설치
```

---

## 2. 스토리지 구성

### 2-1. 단순 디스크 마운트 (Direct)

추가 디스크(`/dev/sdb`)를 `/data`에 마운트하는 경우.

**config.conf 설정:**

```ini
[STORAGE_PROFILE_DATA]
TYPE=direct
DEVICE_PTUUID=<디스크의 PTUUID>
PARTITION=1
MOUNT_POINT=/data
FS_TYPE=ext4
```

> **PTUUID 확인 방법:**
> ```bash
> lsblk -o NAME,PTUUID,UUID,MOUNTPOINT
> ```

TUI에서 `[시스템] → [스토리지] → [프로필 적용]`을 선택하면 자동으로 마운트하고 `/etc/fstab`에 등록합니다.

### 2-2. LVM 구성

4개 디스크를 묶어 LVM 볼륨을 생성하는 경우.

```ini
[STORAGE_PROFILE_VGDATA]
TYPE=lvm
VG_NAME=vg_data
PV_PTUUID=<disk1_PTUUID>,<disk2_PTUUID>,<disk3_PTUUID>,<disk4_PTUUID>
LV_NAME=lv_data
LV_SIZE=100%FREE
MOUNT_POINT=/mnt/storage
FS_TYPE=ext4
```

### 2-3. CIFS 원격 마운트 (NAS)

NAS의 공유 폴더를 마운트하는 경우.

```ini
[STORAGE_PROFILE_NAS]
TYPE=cifs
REMOTE_PATH=//192.168.1.100/shared
MOUNT_POINT=/mnt/nas
CRED_PATH=/etc/samba/cred_nas  # credentials 파일 경로
```

credentials 파일 형식:
```
username=<NAS 사용자명>
password=<NAS 비밀번호>
```

TUI가 credentials 파일 생성 위치를 안내하며, 파일 권한(`600`)은 자동으로 설정됩니다.

### 2-4. SSD 캐시 풀 (LVM Cache)

SSD를 캐시로 활용해 HDD 성능을 끌어올리는 구성.

```ini
[STORAGE_PROFILE_CACHED]
TYPE=lvm_cache
VG_NAME=vg_data
CACHE_LV_PTUUID=<SSD_PTUUID>
DATA_LV_PTUUID=<HDD_PTUUID>
MOUNT_POINT=/mnt/cached_storage
```

---

## 3. 네트워크 구성

### 3-1. 고정 IP 설정

```
TUI: [시스템] → [네트워크] → [인터페이스 선택] → [고정 IP 설정]
```

입력 항목:
- IP 주소: `192.168.1.50/24`
- 게이트웨이: `192.168.1.1`
- DNS: `8.8.8.8,8.8.4.4`

설정 후 `/etc/hosts`에 호스트명 매핑도 자동으로 추가합니다.

### 3-2. 본딩 구성 (Active-Backup)

네트워크 장애 대비용 이중화 구성.

```
TUI: [시스템] → [네트워크] → [본딩 설정] → [Active-Backup]
```

- Primary 인터페이스: `eth0`
- Secondary 인터페이스: `eth1`
- 본딩 인터페이스 이름: `bond0`

### 3-3. LACP 본딩 (대역폭 합산)

스위치가 LACP(802.3ad)를 지원하는 경우 사용.

```
TUI: [시스템] → [네트워크] → [본딩 설정] → [LACP]
```

> 스위치 포트에도 LACP(Port-Channel) 설정이 필요합니다.

---

## 4. GPU 서버 구축

딥러닝 워크스테이션 또는 추론 서버 구축의 전형적인 순서입니다.

### 4-1. 사전 확인

```bash
# GPU 감지 여부 확인
lspci | grep -i nvidia

# 현재 드라이버 상태
nvidia-smi  # 드라이버 미설치 시 오류 발생
```

### 4-2. 설치 순서 (계층 준수)

```
Layer 1 - BASE:
  TUI: [설치] → [BASE] → [빌드 도구 최신화]
  → CMake, GCC/G++ 최신 버전 확보

Layer 2 - PLATFORM:
  TUI: [설치] → [GPU] → [NVIDIA Driver]
  → (재부팅)
  TUI: [설치] → [GPU] → [CUDA Toolkit]
  TUI: [설치] → [GPU] → [cuDNN]

Layer 3 - DEV_STACK:
  TUI: [설치] → [소프트웨어] → [Miniconda]
  TUI: [설치] → [소프트웨어] → [OpenCV]  ← CUDA 연동 빌드
```

### 4-3. CUDA 버전 호환성

| NVIDIA Driver | CUDA |
|---|---|
| ≥ 525 | CUDA 12.x |
| ≥ 470 | CUDA 11.x |

ASAP는 설치 전 Stage 2(Dependency)에서 드라이버-CUDA 호환성을 자동으로 검증합니다.

---

## 5. 개발 환경 구성

### 5-1. Python 개발 환경 (Conda)

```
TUI: [설치] → [소프트웨어] → [Miniconda]
```

설치 후 환경 생성:
```bash
conda create -n myenv python=3.11
conda activate myenv
```

### 5-2. ROS 2 설치

Ubuntu 22.04 기준 ROS 2 Humble 설치.

```
TUI: [설치] → [소프트웨어] → [ROS 2]
```

ROS 2는 Ubuntu 버전에 따라 지원 배포판이 다릅니다. ASAP Stage 1에서 OS 버전을 감지해 적합한 배포판을 자동으로 선택합니다.

| Ubuntu | ROS 2 배포판 |
|---|---|
| 22.04 | Humble |
| 24.04 | Jazzy |

### 5-3. VS Code 원격 개발 환경

```
TUI: [설치] → [소프트웨어] → [VS Code]
```

설치 항목:
- VS Code 서버 (code-server) 또는 데스크탑 패키지
- VS Code 프로필 및 확장 기능 (설정 파일 기반)

### 5-4. Git 및 SSH 설정

일반 사용자로 실행 시 사용 가능한 사용자 수준 설정.

```
TUI: [사용자] → [Git 설정]    → 이름, 이메일, 기본 브랜치 설정
TUI: [사용자] → [SSH 키 관리] → 키 생성 및 공개키 출력
```

---

## 6. 자동화 모드 사용

`ASAP_auto.sh`는 TUI 없이 설정 파일만으로 서버를 프로비저닝합니다. CI/CD 파이프라인이나 cloud-init 환경에 적합합니다.

### 6-1. 설정 파일 준비

```bash
cp template/config_for_auto.conf my_server.conf
```

`my_server.conf` 구조:

```ini
[PACKAGES_LIST]
curl
git
htop
vim

[DRIVER_LIST]
nvidia_driver
cuda

[SOFTWARE_LIST]
conda
opencv
```

스토리지/네트워크 프로필은 동일한 파일 내 별도 섹션으로 정의합니다.

### 6-2. 실행

```bash
./ASAP_auto.sh my_server.conf

# 에러 로그 저장
./ASAP_auto.sh my_server.conf 2> provision.log
```

### 6-3. cloud-init 연동 예시

```yaml
# cloud-init user-data
runcmd:
  - git clone <Repository_URL> /opt/ASAP
  - cd /opt/ASAP && git submodule update --init --recursive
  - /opt/ASAP/ASAP_auto.sh /opt/my_server.conf
```

---

## 7. 트러블슈팅

### dialog 화면이 깨지는 경우

터미널 크기가 너무 작을 때 발생합니다.

```bash
# 터미널을 80x24 이상으로 확장 후 재실행
./ASAP.sh
```

### 서브모듈 초기화 오류

```bash
# 강제 재초기화
git submodule deinit -f --all
git submodule update --init --recursive
```

### 스토리지 마운트 실패

UUID가 변경되었을 가능성이 있습니다. ASAP의 자가 치유 기능으로 복구합니다.

```
TUI: [시스템] → [스토리지] → [설정 재동기화]
```

자가 치유가 실패하는 경우 수동으로 확인:

```bash
lsblk -o NAME,PTUUID,UUID,MOUNTPOINT
# 출력된 PTUUID를 config.conf에 업데이트
```

### 설치 스크립트가 중간에 실패한 경우

`state.conf`에 설치 상태가 기록되어 있어 재실행 시 완료된 단계는 건너뜁니다.

```bash
# state.conf 위치
cat conf/state.conf

# 특정 항목 강제 재설치: state.conf에서 해당 항목 삭제 후 재실행
```

### 권한 오류

```bash
# ASAP.sh는 실행 권한이 필요
chmod +x ASAP.sh

# 특정 시스템 작업은 root 또는 sudo 필요
sudo ./ASAP.sh
```
