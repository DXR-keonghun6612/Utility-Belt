#!/bin/bash
# ==============================================================================
# 파일명: vscode.sh
# 설명: Visual Studio Code 설치 로직
# 가이드: https://code.visualstudio.com/docs/setup/linux#_install-vs-code-on-linux
# ==============================================================================

# -----------------------------------------------------------------------------
# @description Visual Studio Code 설치 여부 확인 및 설정 동기화
# @return 0: 설치됨, 1: 설치 안 됨
# -----------------------------------------------------------------------------
is_installed_vscode() {
    local installed=1
    if command -v code &> /dev/null; then
        installed=0
    fi

    # [Sync Config] 설치 상태 동기화
    if [[ -n "${G_STATE_FILE}" ]]; then
        if [[ $installed -eq 0 ]]; then
            local current_val
            current_val=$(get_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "code")
            if [[ -z "${current_val}" ]]; then
                local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
                add_config_section "${G_STATE_FILE}" "APPLICATION_LIST"
                set_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "code" "${timestamp}"
            fi
        else
            delete_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "code"
        fi
    fi

    return $installed
}

# -----------------------------------------------------------------------------
# @description Microsoft의 APT 저장소를 설정합니다. (내부 함수)
# @return 0: 성공 또는 이미 설정됨, 1: 실패
# -----------------------------------------------------------------------------
_setup_vscode_repo() {
    log_info "Setting up Visual Studio Code APT repository..."
    
    if ! install_apt_gpg_key "https://packages.microsoft.com/keys/microsoft.asc" "/etc/apt/keyrings/packages.microsoft.gpg" "true"; then
        return 1
    fi

    local arch=$(dpkg --print-architecture)
    local repo_line="deb [arch=${arch} signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main"
    
    if ! setup_apt_repository "vscode" "${repo_line}"; then
        return 1
    fi
    
    return 0
}

# -----------------------------------------------------------------------------
# @description Visual Studio Code 설치 로직.
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
install_vscode_logic() {
    ensure_packages_installed "SYSTEM_TOOLS" "VS Code Installation Dependencies" "curl" "gpg" "apt-transport-https" || return 1

    if is_package_installed "code"; then
        log_info "Visual Studio Code is already installed."
        sync_package "APPLICATION_LIST" "code"
        return 0
    fi

    if ! _setup_vscode_repo; then
        return 1
    fi

    log_info "Installing Visual Studio Code ('code' package)..."
    if sync_package "APPLICATION_LIST" "code"; then
        log_success "Visual Studio Code installed successfully."
        return 0
    else
        log_error "Failed to install Visual Studio Code."
        return 1
    fi
}
