# Ubuntu Samba 관리 매뉴얼

Utility Belt의 Samba 관리 모듈은 Windows 및 타 OS와의 파일 공유를 위한 Samba(SMB) 서버 설정을 직관적으로 관리할 수 있게 해줍니다.

## 1. 개요

- **UI 스크립트**: `ui/ubuntu/proc_samba.sh`
- **백엔드 로직**: `script/system/ubuntu/02_samba.sh`
- **설정 파일**: `/etc/samba/smb.conf` 및 개별 포함 파일
- **주요 기능**:
  - 공유 폴더(Share) 생성, 수정, 삭제
  - 공유 프로필 활성화/비활성화
  - Samba 사용자 추가 및 암호 관리

## 2. 사용 방법

메인 메뉴에서 **Samba Management**를 선택하여 진입합니다.

### A. 공유 폴더 관리 (Share Management)

#### 1. Add New Share Profile
새로운 네트워크 공유 폴더를 생성합니다.
- **Share Name**: 네트워크에 표시될 공유 이름.
- **Share Path**: 실제 서버 내의 디렉토리 경로 (예: `/srv/samba/public`). 없으면 자동 생성 여부를 묻습니다.
- **권한 설정 (Wizard)**:
  - **Writable**: 쓰기 권한 허용 여부.
  - **Browseable**: 네트워크 목록 노출 여부.
  - **Guest Ok**: 로그인 없는 게스트 접근 허용 여부.
  - **Valid/Admin Users**: 접근 가능한 사용자 및 관리자 지정.

#### 2. Manage Share Profiles (Enable/Disable)
등록된 공유 폴더들의 활성화 상태를 토글합니다.
- 체크리스트에서 선택(V)된 공유는 활성화되고, 해제된 공유는 비활성화됩니다.
- 변경 사항 적용 시 Samba 서비스가 자동으로 재시작됩니다.

#### 3. Modify/Delete Share Profile
기존 공유 설정을 수정하거나 영구적으로 삭제합니다.

### B. Samba 사용자 관리 (User Management)

Samba는 시스템 계정과 별도로 자체적인 암호 데이터베이스를 가집니다.

#### 1. Add New Samba User
기존 시스템 사용자(`System User`)를 Samba 사용자로 등록합니다.
- 목록에는 "시스템에는 존재하지만 Samba에는 등록되지 않은" 사용자만 표시됩니다.
- Samba 접속용 전용 암호를 설정해야 합니다.

#### 2. List/Delete Samba User
현재 등록된 Samba 사용자 목록을 조회하거나 제거합니다.
