#!/bin/bash
# ==============================================================================
# 파일명: vscode.sh
# 설명: Visual Studio Code 설치 로직
# 가이드: https://code.visualstudio.com/docs/setup/linux#_install-vs-code-on-linux
# ==============================================================================

# -----------------------------------------------------------------------------
# @description Microsoft의 APT 저장소를 설정합니다. (내부 함수)
# @return 0: 성공 또는 이미 설정됨, 1: 실패
# -----------------------------------------------------------------------------
_setup_vscode_repo() {
    # 저장소 설정 파일이 이미 있는지 확인
    if [[ -f "/etc/apt/sources.list.d/vscode.list" ]]; then
        echo "[INFO] VS Code repository is already configured."
        return 0
    fi

    echo "[INFO] Setting up Visual Studio Code APT repository (following official guide)..."
    
    # 1. 필수 의존성 설치 (wget, gpg, apt-transport-https)
    # 가이드 Step 1 & 6 통합
    ensure_packages_installed "SYSTEM_TOOLS" "wget" "gpg" "apt-transport-https" || return 1

    # 2. Microsoft GPG 키 다운로드 및 변환 (가이드 Step 2)
    local tmp_gpg="/tmp/packages.microsoft.gpg"
    echo "[INFO] Downloading Microsoft GPG key..."
    if ! wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > "${tmp_gpg}"; then
        echo "[ERROR] Failed to download or dearmor Microsoft GPG key." >&2
        return 1
    fi

    # 3. GPG 키를 /etc/apt/keyrings로 안전하게 이동 및 권한 설정 (가이드 Step 3)
    # install 명령은 디렉토리 생성(-D), 소유자(-o), 그룹(-g), 권한(-m) 설정을 한 번에 수행함
    echo "[INFO] Installing GPG key to /etc/apt/keyrings/..."
    if ! ${G_SUDO_PREFIX} install -D -o root -g root -m 644 "${tmp_gpg}" /etc/apt/keyrings/packages.microsoft.gpg; then
        echo "[ERROR] Failed to install GPG key using 'install' command." >&2
        rm -f "${tmp_gpg}"
        return 1
    fi
    rm -f "${tmp_gpg}"

    # 4. VS Code 저장소 추가 (가이드 Step 4)
    echo "[INFO] Adding VS Code repository to sources.list.d..."
    # 가이드는 amd64, arm64, armhf를 명시하지만, 현재 시스템 아키텍처를 동적으로 사용하는 것이 더 안전함
    local arch=$(dpkg --print-architecture)
    local repo_line="deb [arch=${arch} signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main"
    
    if ! echo "${repo_line}" | ${G_SUDO_PREFIX} tee /etc/apt/sources.list.d/vscode.list > /dev/null; then
        echo "[ERROR] Failed to write vscode.list." >&2
        return 1
    fi

    # 5. 패키지 목록 업데이트 (가이드 Step 7)
    echo "[INFO] Updating package list..."
    if ! ${_PKG_UPDATE_CMD}; then
        echo "[ERROR] apt update failed after adding VS Code repository." >&2
        return 1
    fi
    
    echo "[SUCCESS] VS Code repository configured successfully."
    return 0
}

# -----------------------------------------------------------------------------
# @description Visual Studio Code 설치 로직.
#           - APT 저장소를 설정하고, `sync_package`를 통해 설치 및 상태 기록.
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
install_vscode_logic() {
    # 1. 이미 설치되어 있는지 확인
    if is_package_installed "code"; then
        echo "[INFO] Visual Studio Code is already installed."
        # 설정 파일 기록 동기화 (기록이 없을 경우에만 수행됨)
        sync_package "APPLICATION_LIST" "code"
        return 0
    fi

    # 2. VS Code 저장소 설정
    if ! _setup_vscode_repo; then
        return 1
    fi

    # 3. VS Code 설치 (가이드 Step 8) 및 기록
    echo "[INFO] Installing Visual Studio Code ('code' package)..."
    if sync_package "APPLICATION_LIST" "code"; then
        echo "[SUCCESS] Visual Studio Code installed successfully."
        return 0
    else
        echo "[ERROR] Failed to install Visual Studio Code." >&2
        return 1
    fi
}
