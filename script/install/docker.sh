#!/bin/bash
# ==============================================================================
# 파일명: docker.sh
# 설명: Docker Engine 및 NVIDIA Container Toolkit 설치 로직
# 가이드: 
#   - Docker: https://docs.docker.com/engine/install/ubuntu/
#   - NVIDIA: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
# ==============================================================================

# -----------------------------------------------------------------------------
# @description Docker 및 NVIDIA Container Toolkit 설치 여부 확인 및 설정 동기화
# @return 0: 설치됨, 1: 설치 안 됨
# -----------------------------------------------------------------------------
is_installed_docker() {
    local installed=1
    if command -v docker &> /dev/null; then
        installed=0
    fi

    # [Sync Config] 설치 상태 동기화
    if [[ -n "${G_STATE_FILE}" ]]; then
        if [[ $installed -eq 0 ]]; then
            local current_val
            current_val=$(get_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "docker")
            if [[ -z "${current_val}" ]]; then
                local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
                add_config_section "${G_STATE_FILE}" "APPLICATION_LIST"
                set_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "docker" "${timestamp}"
            fi
        else
            delete_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "docker"
            delete_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "nvidia-docker"
        fi
    fi

    return $installed
}

# -----------------------------------------------------------------------------
# @description Docker 저장소를 설정합니다. (내부 함수)
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
_setup_docker_repo() {
    if ! install_apt_gpg_key "https://download.docker.com/linux/ubuntu/gpg" "/etc/apt/keyrings/docker.asc" "false"; then
        return 1
    fi

    local arch=$(dpkg --print-architecture)
    source /etc/os-release
    local repo_line="deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable"
    
    if ! setup_apt_repository "docker" "${repo_line}"; then
        return 1
    fi

    return 0
}

# -----------------------------------------------------------------------------
# @description NVIDIA Container Toolkit 저장소를 설정합니다. (내부 함수)
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
_setup_nvidia_toolkit_repo() {
    local gpg_key_url="https://nvidia.github.io/libnvidia-container/gpgkey"
    local repo_list_url="https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list"
    local gpg_keyring="/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"

    if ! install_apt_gpg_key "${gpg_key_url}" "${gpg_keyring}" "true"; then
        log_error "Failed to setup NVIDIA GPG key."
        return 1
    fi

    local repo_content
    if ! repo_content=$(curl -s -L "${repo_list_url}" | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g'); then
        log_error "Failed to download or process NVIDIA repository list."
        return 1
    fi

    if [[ -z "$repo_content" ]]; then
        log_error "NVIDIA repository content is empty."
        return 1
    fi

    if ! setup_apt_repository "nvidia-container-toolkit" "${repo_content}"; then
        return 1
    fi

    return 0
}

# -----------------------------------------------------------------------------
# @description Docker 및 NVIDIA Container Toolkit 설치 로직
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
install_docker_logic() {
    ensure_packages_installed "SYSTEM_TOOLS" "Docker Installation Dependencies" "ca-certificates" "curl" "gnupg" || return 1

    if [[ $(get_package_manager_type) != "dpkg" ]]; then
        log_error "Docker installation script currently supports Debian/Ubuntu-based systems only."
        return 1
    fi

    if ! _setup_docker_repo; then
        return 1
    fi

    log_info "Installing Docker Engine packages..."
    local docker_pkgs=("docker-ce" "docker-ce-cli" "containerd.io" "docker-buildx-plugin" "docker-compose-plugin")
    if ! sync_package "APPLICATION_LIST" "docker" "${docker_pkgs[@]}"; then
        log_error "Failed to install Docker packages."
        return 1
    fi

    if ! _setup_nvidia_toolkit_repo; then
        log_warn "Failed to setup NVIDIA repository. Skipping NVIDIA Toolkit installation."
    else
        log_info "Installing NVIDIA Container Toolkit..."
        if sync_package "APPLICATION_LIST" "nvidia-docker" "nvidia-container-toolkit"; then
            log_info "Configuring Docker to use NVIDIA runtime..."
            if ${G_SUDO_PREFIX} nvidia-ctk runtime configure --runtime=docker; then
                log_info "Restarting Docker daemon..."
                ${G_SUDO_PREFIX} systemctl restart docker
            else
                log_error "Failed to configure NVIDIA runtime."
            fi
        else
            log_error "Failed to install NVIDIA Container Toolkit."
        fi
    fi

    if [[ -n "${SUDO_USER}" ]] || [[ "${EUID}" -ne 0 ]]; then
        local target_user="${SUDO_USER:-$USER}"
        log_info "Adding user '${target_user}' to 'docker' group..."
        if ${G_SUDO_PREFIX} usermod -aG docker "${target_user}"; then
            log_info "User added to docker group. You may need to log out and back in for this to take effect."
        else
            log_warn "Failed to add user to docker group."
        fi
    fi

    log_success "Docker installation and configuration completed."
    return 0
}
