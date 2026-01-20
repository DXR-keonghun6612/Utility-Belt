# Ubuntu 소프트웨어 설치 매뉴얼

Utility Belt는 시스템 필수 패키지부터 응용 프로그램, 커스텀 서비스까지 다양한 소프트웨어의 설치와 관리를 지원합니다.

## 1. 개요

- **관련 메뉴**:
  - **Install Packages**: 기본 시스템 패키지 관리 (`proc_install_package.sh`)
  - **Install Applications**: 추가 응용 프로그램 설치 (`proc_install_application.sh`)
  - **Custom Service**: 사용자 정의 서비스 관리 (`proc_custom_service.sh`)
- **특징**: 설치 상태를 설정 파일(`ubuntu_config.conf`)에 기록하여 멱등성(Idempotency)을 보장합니다.

## 2. 패키지 관리 (Install Packages)

`apt`를 통해 설치되는 시스템 유틸리티들(예: `curl`, `git`, `htop`, `vim` 등)을 관리합니다.

1. **목록 확인**: 설정 파일의 `[PACKAGES_LIST]`에 정의된 패키지들이 표시됩니다.
2. **설치/삭제**:
   - 체크(V): 패키지 설치 (`apt install`)
   - 해제( ): 패키지 삭제 (`apt remove`)
   - 목록에 없는 패키지가 이미 시스템에 설치되어 있다면 자동으로 감지하여 체크 상태로 표시됩니다.

## 3. 어플리케이션 설치 (Install Applications)

복잡한 설치 과정이 필요한 소프트웨어를 스크립트로 자동화하여 설치합니다.

- **NVIDIA Driver**:
  - 시스템에 맞는 드라이버 버전을 자동 검색하여 추천(`recommended`)합니다.
  - 선택 시 기존 드라이버를 제거하고 새 버전을 설치합니다. (재부팅 필요)
- **Miniconda**:
  - Python 가상환경 관리를 위한 Miniconda를 설치합니다.
  - **User Mode**: 홈 디렉토리에 설치.
  - **System Mode**: `/opt`에 설치 (모든 사용자용).
- **VS Code**:
  - Microsoft Visual Studio Code를 설치합니다.

## 4. 커스텀 서비스 관리 (Custom Service)

사용자가 직접 작성한 서비스 스크립트(`custom_service/` 디렉토리 내)를 설치하거나 제거합니다.

- **구조**: `custom_service/<서비스명>/` 안에 `setup.sh`와 `uninstall.sh`가 있어야 합니다.
- **사용법**:
  - 목록에서 서비스를 체크하면 `setup.sh`가 실행되어 설치됩니다.
  - 체크를 해제하면 `uninstall.sh`가 실행되어 제거됩니다.
