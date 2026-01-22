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
    echo "[INFO] Setting up Visual Studio Code APT repository (following official guide)..."
    
    # 1. Microsoft GPG 키 다운로드 및 설치 (install_apt_gpg_key 활용)
    # 가이드 Step 2 & 3 통합
    if ! install_apt_gpg_key "https://packages.microsoft.com/keys/microsoft.asc" "/etc/apt/keyrings/packages.microsoft.gpg" "true"; then
        return 1
    fi

    # 2. VS Code 저장소 추가 (가이드 Step 4 & 7)
    local arch=$(dpkg --print-architecture)
    local repo_line="deb [arch=${arch} signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main"
    
    if ! setup_apt_repository "vscode" "${repo_line}"; then
        return 1
    fi
    
    return 0
}

# -----------------------------------------------------------------------------
# @description Visual Studio Code 설치 로직.
#           - APT 저장소를 설정하고, `sync_package`를 통해 설치 및 상태 기록.
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
install_vscode_logic() {
    # 0. 필수 의존성 확인
    ensure_packages_installed "SYSTEM_TOOLS" "VS Code Installation Dependencies" "curl" "gpg" "apt-transport-https" || return 1

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
