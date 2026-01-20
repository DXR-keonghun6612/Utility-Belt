# Automated Server Administration Platform: 자동화된 서버 관리 플랫폼

## 개요

- 정의: 크로스플랫폼 서버 관리 자동화 도구
- OS: Linux (TUI), Windows (GUI) 동시 지원
- 기술 스택:
  - Linux: `bash` + `dialog` (텍스트 인터페이스)
  - Windows: `PowerShell` + `Windows Forms` (그래픽 인터페이스)
- 주요 기능: 시스템 설정, 소프트웨어 설치, 모니터링, 스토리지 관리

## 주요 기능 상세

### 크로스플랫폼 지원 (Cross-Platform)

- Linux (Ubuntu/Debian): `dialog` 유틸리티를 활용한 직관적인 TUI 제공.
- Windows (10, 11, Server): `Windows Forms`를 통해 친숙한 GUI 제공.
- 구조: OS별 독립된 스크립트 구조로 기능 추가 및 유지보수가 용이.

### 지능형 권한 관리 (Intelligent Permissions)

- 권한 자동 감지: 스크립트 실행 시 관리자(root/Admin) 여부 확인 후 최적 모드(관리자/사용자)로 전환.
- 필요 시점 권한 상승:
  - Linux: `sudo`를 통해 꼭 필요한 명령어에 대해서만 `root` 권한 사용.
  - Windows: 관리자 권한이 필요한 기능 실행 전 사용자에게 안내.

### 프로필 기반 상태 관리 (Profile-based Management)

- 선언적 관리: `.conf` 설정 파일에 원하는 상태를 '프로필'로 정의.
- 스토리지:
  - 프로필 종류: `direct`(단일 디스크), `lvm`(Linux), `Storage Spaces`(Windows), `cifs`(원격 공유).
  - UI를 통해 프로필을 선택하여 마운트/언마운트 상태를 손쉽게 동기화.
- Samba/SMB:
  - 공유 설정을 프로필 단위로 `.conf` 파일에 저장.
  - UI에서 각 공유 프로필을 활성화/비활성화.

### 모듈화된 기능 (Modular Functions)

- 시스템 모니터링:
  - 조회 항목: CPU, 메인보드, GPU, 메모리, 스토리지 상세 정보.
  - 내보내기: 수집된 하드웨어 정보를 `JSON` 형식 파일로 저장.
- 소프트웨어 설치:
  - Linux: `apt` 패키지, NVIDIA 드라이버, Miniconda 자동 설치.
  - Windows: `winget` 패키지, NVIDIA 드라이버, Miniconda 자동 설치.
- 시스템 설정:
  - 계정: 로컬 사용자 및 그룹 생성, 삭제, 수정.
  - 네트워크: 고정 IP 설정, 네트워크 본딩/팀 구성, Hosts 파일 관리.
- 사용자 도구:
  - Git: 사용자 정보(이름/이메일), 인증 도우미 설정.
  - SSH: `ed25519`/`rsa` 키 생성, `ssh-agent` 관리.

## 요구사항

- Linux:
  - OS: Ubuntu, Debian 기반 시스템
  - 필수: `bash`, `git`, `dialog`, `sudo`
- Windows:
  - OS: Windows 10/11, Windows Server 2016 이상
  - 필수: `PowerShell 5.1+`, `.NET Framework 4.5+`
  - 권장: `Git for Windows`, `Winget` 클라이언트

## 설치

1. 저장소 복제:

   ```bash
   git clone <URL> Utility_Belt && cd Utility_Belt
   ```

2. 서브모듈 초기화 (필요 시):

   ```bash
   git submodule update --init --recursive
   ```

## 사용법 (Usage) & 디버깅 (Debugging)

### Linux (Bash)

**1. 기본 실행**
가장 일반적인 실행 방법입니다. `dialog` 패키지가 없으면 자동으로 설치를 시도합니다.
```bash
bash ./ASAP.sh
```

**2. 로그 저장 (Logging)**
실행 중 발생하는 오류 메시지를 파일로 저장하려면 표준 에러(stderr)를 리다이렉션합니다.
```bash
# 에러 메시지만 'error.log'에 저장
bash ./ASAP.sh 2> error.log

# 모든 출력(표준 출력 + 에러)을 'output.log'에 저장
bash ./ASAP.sh > output.log 2>&1
```

**3. 디버그 모드 (Debugging)**
스크립트의 실행 과정을 한 줄씩 추적(Trace)하려면 `-x` 옵션을 사용합니다.
```bash
# 실행 과정을 화면에 출력하며 실행
bash -x ./ASAP.sh

# 실행 과정을 파일로 저장 (분석용)
bash -x ./ASAP.sh 2> debug_trace.log
```

---

### Windows (PowerShell)

**1. 기본 실행**
PowerShell을 **관리자 권한**으로 실행한 후, 스크립트 실행 정책을 우회하여 실행합니다.
```powershell
# 실행 정책(Execution Policy)을 일시적으로 Bypass로 설정하여 실행
powershell.exe -ExecutionPolicy Bypass -File .\ASAP.ps1
```

**2. 로그 기록 (Transcript)**
PowerShell의 `Start-Transcript` 기능을 사용하여 콘솔의 모든 내용을 기록할 수 있습니다.
```powershell
# 기록 시작
Start-Transcript -Path "log.txt"

# 스크립트 실행
.\ASAP.ps1

# 기록 종료 (로그 파일 저장 완료)
Stop-Transcript
```

**3. 디버그 모드 (Debugging)**
스크립트 실행 중 변수 할당이나 조건문 분기 등을 추적하려면 `Set-PSDebug`를 사용합니다.
```powershell
# 디버그 추적 레벨 설정 (1: 기본, 2: 상세)
Set-PSDebug -Trace 1

# 스크립트 실행
.\ASAP.ps1

# 디버그 모드 해제
Set-PSDebug -Off
```

## 프로젝트 구조

- 진입점: `ASAP.sh` (Linux), `ASAP.ps1` (Windows)
- 설정: `template/` (템플릿), `*.conf` (실행 설정)
- 백엔드 로직: `script/`
  - `core/<os>`: 핵심 라이브러리 (권한 감지, 파서, UI 툴킷).
  - `system/<os>`: 시스템 관리 로직 (계정, 네트워크, 스토리지).
  - `user/<os>`: 사용자 도구 로직 (Git, SSH).
  - `install/<os>`: 소프트웨어 설치 로직.
- 프론트엔드 UI: `ui/<os>`
  - `ui/ubuntu`: TUI (`dialog`) 스크립트.
  - `ui/windows`: GUI (`Windows Forms`) 스크립트.