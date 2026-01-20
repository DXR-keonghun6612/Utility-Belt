# Ubuntu 네트워크 관리 매뉴얼

Utility Belt의 네트워크 관리 모듈은 IP 설정, 연결 테스트, 본딩(Bonding) 구성, 호스트 파일 관리 등 네트워크 관련 작업을 TUI 환경에서 지원합니다.

## 1. 개요

- **UI 스크립트**: `ui/ubuntu/proc_network.sh`
- **백엔드 로직**: `script/system/ubuntu/02_network.sh`
- **주요 기능**:
  - IP 정보 조회 및 연결 상태 확인
  - 고정 IP (Static IP) 설정
  - 네트워크 인터페이스 본딩(팀 구성)
  - `/etc/hosts` 파일 편집

## 2. 사용 방법

메인 메뉴에서 **Network Management**를 선택하여 진입합니다.

### A. 기본 기능

#### 1. View Current IP Info
현재 시스템의 모든 네트워크 인터페이스에 할당된 IP 주소, MAC 주소 등의 정보를 요약하여 보여줍니다.

#### 2. Check Connection Status (Ping)
외부 호스트와의 연결 상태를 점검합니다.
- 기본값으로 `8.8.8.8` (Google DNS)에 Ping을 보냅니다.
- 다른 IP나 도메인을 입력하여 테스트할 수 있습니다.

### B. 네트워크 설정 (IP & Bonding)

#### 1. Set Static IP
특정 네트워크 인터페이스에 고정 IP를 할당합니다.
- **Select Interface**: 설정할 인터페이스(예: `eth0`)를 선택합니다.
- **입력 항목**:
  - **IP/CIDR**: 예) `192.168.1.100/24`
  - **Gateway**: 예) `192.168.1.1`
  - **DNS**: 예) `8.8.8.8 8.8.4.4`
- **적용**: 설정 즉시 `netplan` 등을 통해 네트워크가 재설정됩니다. (SSH 접속 중일 경우 연결이 끊길 수 있음)

#### 2. Create Network Bond
여러 네트워크 인터페이스를 하나로 묶어 대역폭을 늘리거나 안정성을 높입니다.
- **Select Slaves**: 본딩에 참여할 물리 인터페이스들을 선택합니다.
- **Bond Name**: 본딩 인터페이스 이름 (예: `bond0`).
- **Mode Selection**:
  - `active-backup`: 장애 허용 (하나가 끊겨도 다른 하나로 통신).
  - `802.3ad`: LACP (대역폭 확장, 스위치 지원 필요).
  - `balance-rr`: 로드 밸런싱.

### C. 호스트 파일 관리 (Hosts File)

`/etc/hosts` 파일을 관리하여 로컬 DNS 매핑을 설정합니다.

#### 1. Add/Edit Host Mapping
IP 주소와 호스트네임 쌍을 추가하거나 수정합니다.
- 예: `192.168.1.50  myserver.local`

#### 2. Edit File Directly
`nano` 에디터를 열어 `/etc/hosts` 파일을 직접 수정합니다.
