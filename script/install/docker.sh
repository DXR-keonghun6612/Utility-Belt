#!/bin/bash
# ==============================================================================
# 파일명: docker.sh
# 설명: Docker Engine 및 NVIDIA Container Toolkit 설치 로직
# 가이드: 
#   - Docker: https://docs.docker.com/engine/install/ubuntu/
#   - NVIDIA: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
# ==============================================================================

# -----------------------------------------------------------------------------
# @description Docker 저장소를 설정합니다. (내부 함수)
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
_setup_docker_repo() {
    # 1. Docker GPG 키 다운로드 및 설치 (Armored 상태 유지, dearmor=false)
    if ! install_apt_gpg_key "https://download.docker.com/linux/ubuntu/gpg" "/etc/apt/keyrings/docker.asc" "false"; then
        return 1
    fi

    # 2. Docker 저장소 추가 및 업데이트
    local arch=$(dpkg --print-architecture)
    # /etc/os-release 파일에서 VERSION_CODENAME을 가져옴
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
    # 1. NVIDIA GPG 키 설치
    local gpg_key_url="https://nvidia.github.io/libnvidia-container/gpgkey"
    local repo_list_url="https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list"
    local gpg_keyring="/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"

    # GPG 키 처리 (Dearmor 필요)
    if ! install_apt_gpg_key "${gpg_key_url}" "${gpg_keyring}" "true"; then
        echo "[ERROR] Failed to setup NVIDIA GPG key." >&2
        return 1
    fi

    # 2. 저장소 정의 내용 가져오기 및 가공
    local repo_content
    # curl로 가져온 뒤 sed로 signed-by 옵션 주입
    if ! repo_content=$(curl -s -L "${repo_list_url}" | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g'); then
        echo "[ERROR] Failed to download or process NVIDIA repository list." >&2
        return 1
    fi

    if [[ -z "$repo_content" ]]; then
        echo "[ERROR] NVIDIA repository content is empty." >&2
        return 1
    fi

    # 3. 저장소 추가 및 업데이트
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
    # 0. 필수 의존성 확인 (curl, gnupg 등)
    ensure_packages_installed "SYSTEM_TOOLS" "Docker Installation Dependencies" "ca-certificates" "curl" "gnupg" || return 1

    # 1. 배포판 의존성 확인 (dpkg 기반 시스템만 지원)
    if [[ $(get_package_manager_type) != "dpkg" ]]; then
        echo "[ERROR] Docker installation script currently supports Debian/Ubuntu-based systems only." >&2
        return 1
    fi

    # 2. Docker 저장소 설정
    if ! _setup_docker_repo; then
        return 1
    fi

    # 3. Docker Engine 패키지 설치 및 기록
    echo "[INFO] Installing Docker Engine packages..."
    local docker_pkgs=("docker-ce" "docker-ce-cli" "containerd.io" "docker-buildx-plugin" "docker-compose-plugin")
    if ! sync_package "APPLICATION_LIST" "docker" "${docker_pkgs[@]}"; then
        echo "[ERROR] Failed to install Docker packages." >&2
        return 1
    fi

    # 4. NVIDIA Container Toolkit 저장소 설정
    if ! _setup_nvidia_toolkit_repo; then
        echo "[WARN] Failed to setup NVIDIA repository. Skipping NVIDIA Toolkit installation."
        # NVIDIA 설정 실패가 Docker 설치 실패는 아니므로 진행
    else
        # 5. NVIDIA Container Toolkit 설치
        echo "[INFO] Installing NVIDIA Container Toolkit..."
        if sync_package "APPLICATION_LIST" "nvidia-docker" "nvidia-container-toolkit"; then
            
            # 6. Docker 데몬 설정 (NVIDIA Runtime)
            echo "[INFO] Configuring Docker to use NVIDIA runtime..."
            if ${G_SUDO_PREFIX} nvidia-ctk runtime configure --runtime=docker; then
                echo "[INFO] Restarting Docker daemon..."
                ${G_SUDO_PREFIX} systemctl restart docker
            else
                echo "[ERROR] Failed to configure NVIDIA runtime." >&2
            fi
        else
            echo "[ERROR] Failed to install NVIDIA Container Toolkit." >&2
        fi
    fi

    # 7. 현재 사용자를 docker 그룹에 추가 (sudo 없이 docker 사용)
    if [[ -n "${SUDO_USER}" ]] || [[ "${EUID}" -ne 0 ]]; then
        local target_user="${SUDO_USER:-$USER}"
        echo "[INFO] Adding user '${target_user}' to 'docker' group..."
        if ${G_SUDO_PREFIX} usermod -aG docker "${target_user}"; then
            echo "[INFO] User added to docker group. You may need to log out and back in for this to take effect."
        else
            echo "[WARN] Failed to add user to docker group."
        fi
    fi

    echo "[SUCCESS] Docker installation and configuration completed."
    return 0
}
