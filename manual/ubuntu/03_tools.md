# Ubuntu 개발 도구 설정 매뉴얼 (Git & SSH)

개발 환경 설정에 필수적인 Git 사용자 설정과 SSH 키 생성을 도와주는 기능입니다.

## 1. Git 관리 (Git Management)

- **UI 스크립트**: `ui/ubuntu/proc_git.sh`
- **주요 기능**:
  1. **Configure User & Email**:
     - `git config --global user.name` 및 `user.email`을 설정합니다.
     - 커밋 기록에 남을 정보를 입력합니다.
  2. **Update Auth Token**:
     - GitHub 등의 Personal Access Token (PAT)을 저장합니다.
     - `git-credential-store` 등을 설정하여 매번 비밀번호를 입력하지 않도록 돕습니다.

## 2. SSH 관리 (SSH Management)

- **UI 스크립트**: `ui/ubuntu/proc_ssh.sh`
- **주요 기능**: SSH 키 쌍 생성 및 클라이언트 배포용 패키징.

### SSH 키 생성 프로세스 (Generate New SSH Key)

1. **Key Details**:
   - **Filename**: 키 파일 이름 (예: `id_ed25519_myproject`).
   - **Comment**: 키에 포함될 주석 (예: `user@hostname`).
2. **Target OS Selection**:
   - 생성된 공개키(Public Key)를 클라이언트에서 쉽게 등록할 수 있도록 **설치 스크립트**를 함께 생성합니다.
   - **Linux Client**: `install_key.sh` 포함.
   - **Windows Client**: `install_key.ps1` 포함.
3. **결과**:
   - 홈 디렉토리의 `ssh_packages/<키이름>/` 폴더에 개인키, 공개키, 그리고 선택한 OS별 설치 스크립트가 생성됩니다.
   - 이 폴더를 클라이언트 장비로 복사하여 스크립트만 실행하면 서버 접속 설정이 완료됩니다.
