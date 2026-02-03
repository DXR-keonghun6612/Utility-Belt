#!/bin/bash
# ==============================================================================
# 파일명: cuda_toolkit.sh
# 설명: NVIDIA CUDA Toolkit 설치 로직 (Official NVIDIA Repository)
# ==============================================================================

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 설치 여부 확인
# @return 0: 설치됨, 1: 설치 안 됨
# -----------------------------------------------------------------------------
is_installed_cuda_toolkit() {
    # 1. PATH에 nvcc가 있는지 확인
    if command -v nvcc &> /dev/null; then
        return 0
    fi

    # 2. 일반적인 설치 경로 확인 (/usr/local/cuda/bin/nvcc)
    if [[ -x "/usr/local/cuda/bin/nvcc" ]]; then
        return 0
    fi

    return 1
}

# -----------------------------------------------------------------------------
# @description NVIDIA 저장소 설정 (Keyring 설치)
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
_setup_cuda_repo() {
    echo "[INFO] Setting up NVIDIA CUDA repository..."

    # 1. 시스템 정보 감지
    if [[ ! -f /etc/os-release ]]; then
        echo "[ERROR] Cannot detect OS version. /etc/os-release not found." >&2
        return 1
    fi
    source /etc/os-release

    # ID: ubuntu, VERSION_ID: 22.04 -> ubuntu2204
    local distro="${ID}${VERSION_ID//./}"
    local arch=$(uname -m)

    # NVIDIA Repo에서 지원하는 아키텍처 매핑
    case "${arch}" in
        x86_64) ;;
        aarch64)
            # ARM64의 경우 sbsa(Server)와 generic arm64(Jetson/Desktop)로 나뉨
            if command -v ui_create_menu &>/dev/null; then
                local choice
                choice=$(ui_create_menu "CUDA Architecture Selection" "Select Architecture Variant" \
                    "Detected 'aarch64'. Choose the repository target:" 15 70 2 \
                    "sbsa" "Server Base System Architecture (Servers)" \
                    "arm64" "Generic ARM64 (Jetson, Desktop, RPi)")
                
                if [[ "$choice" == "CANCEL" ]]; then
                    echo "[WARN] Architecture selection canceled."
                    return 1
                fi
                arch="${choice}"
            else
                # UI가 없는 경우 기본값 sbsa (서버용 스크립트 특성상)
                echo "[WARN] Non-interactive mode: Defaulting aarch64 to 'sbsa'."
                arch="sbsa"
            fi
            ;;
        *)
            echo "[ERROR] Unsupported architecture for CUDA repo setup: ${arch}" >&2
            return 1
            ;;
    esac

    # 2. Keyring 다운로드 및 설치
    # URL 패턴: https://developer.download.nvidia.com/compute/cuda/repos/<distro>/<arch>/cuda-keyring_1.1-1_all.deb
    local keyring_url="https://developer.download.nvidia.com/compute/cuda/repos/${distro}/${arch}/cuda-keyring_1.1-1_all.deb"
    local keyring_tmp="/tmp/cuda-keyring.deb"

    echo "[INFO] Downloading CUDA keyring from: ${keyring_url}"
    if ! wget "${keyring_url}" -O "${keyring_tmp}"; then
        echo "[ERROR] Failed to download CUDA keyring. Please check if your OS version (${distro}) is supported." >&2
        return 1
    fi

    echo "[INFO] Installing CUDA keyring..."
    if ! ${G_SUDO_PREFIX} dpkg -i "${keyring_tmp}"; then
        echo "[ERROR] Failed to install CUDA keyring." >&2
        rm -f "${keyring_tmp}"
        return 1
    fi
    rm -f "${keyring_tmp}"

    # 3. 저장소 업데이트
    echo "[INFO] Updating package lists..."
    if ! ${_PKG_UPDATE_CMD}; then
        echo "[WARN] 'apt update' completed with errors." >&2
        # 일부 에러가 있어도 진행 가능할 수 있음
    fi

    return 0
}

# -----------------------------------------------------------------------------
# @description 사용 가능한 CUDA Toolkit 버전 목록을 조회합니다.
# @return stdout "패키지명 설명" 목록 (sort -Vr 정렬됨)
# -----------------------------------------------------------------------------
_get_available_cuda_versions() {
    # 'cuda-toolkit-X-Y' 형식 또는 'cuda-toolkit-X-Y-Z' 형식의 패키지 검색
    # 예: cuda-toolkit-12-0, cuda-toolkit-12-6
    # 정규식 업데이트: 버전이 3부분인 경우도 대비 (예: cuda-toolkit-13-0-1)
    apt-cache search "^cuda-toolkit-[0-9]+-[0-9]+(-[0-9]+)?$" | \
        grep -E "^cuda-toolkit-[0-9]+-[0-9]+(-[0-9]+)?" | \
        sort -Vr | \
        awk '{print $1 " " $1}' # 메뉴 생성용으로 "패키지명 패키지명" 형식 출력
}

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 설치 로직
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
install_cuda_toolkit_logic() {
    # 0. 필수 의존성 확인
    ensure_packages_installed "SYSTEM_TOOLS" "CUDA Dependencies" "wget" "build-essential" || return 1

    # 1. 배포판 확인 (Debian/Ubuntu 계열만 지원)
    if [[ $(get_package_manager_type) != "dpkg" ]]; then
        echo "[ERROR] CUDA Toolkit installation is currently supported on Debian/Ubuntu-based systems only." >&2
        return 1
    fi

    # 2. 이미 설치되어 있는지 확인
    if is_installed_cuda_toolkit; then
        echo "[WARN] CUDA Toolkit appears to be already installed."
        # 설정 파일 동기화 (기본값으로 체크)
        sync_package "APPLICATION_LIST" "cuda-toolkit" "cuda-toolkit"
        return 0
    fi

    # 3. NVIDIA 저장소 설정
    if ! _setup_cuda_repo; then
        return 1
    fi

    # 4. 설치할 버전 선택
    local selected_version=""
    local version_list_raw
    
    echo "[INFO] Fetching available CUDA Toolkit versions..."
    version_list_raw=$(_get_available_cuda_versions)
    
    if [[ -n "$version_list_raw" ]]; then
        local version_list
        mapfile -t version_list <<< "${version_list_raw}"
        
        # 메뉴 항목 구성 (패키지명 설명)
        local menu_options=()
        for item in "${version_list[@]}"; do
             menu_options+=($item) # $item은 "pkg pkg" 형태이므로 분리되어 들어감
        done
        
        selected_version=$(ui_create_menu "CUDA Toolkit Selection" "Select CUDA Version" \
            "Choose specific CUDA Toolkit version to install:" 15 60 5 \
            "${menu_options[@]}")
            
        if [[ "$selected_version" == "CANCEL" ]]; then
            echo "[WARN] Installation canceled by user."
            return 1
        fi
    else
        echo "[WARN] Could not detect specific CUDA versions. Using default 'cuda-toolkit'."
        selected_version="cuda-toolkit"
    fi

    # 5. CUDA Toolkit 설치
    echo "[INFO] Installing CUDA Toolkit (${selected_version})..."
    if sync_package "APPLICATION_LIST" "cuda-toolkit" "${selected_version}"; then
        # 환경 변수 설정 안내 또는 자동 설정
        local cuda_path="/usr/local/cuda/bin"
        local profile_script="/etc/profile.d/cuda.sh"
        
        echo "[INFO] Creating environment profile: ${profile_script}"
        echo 'export PATH=/usr/local/cuda/bin:${PATH}' | ${G_SUDO_PREFIX} tee "${profile_script}" > /dev/null
        echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}' | ${G_SUDO_PREFIX} tee -a "${profile_script}" > /dev/null
        
        echo "[SUCCESS] CUDA Toolkit installed successfully."
        echo "         Please log out and log back in, or run 'source ${profile_script}' to update your PATH."
        return 0
    else
        echo "[ERROR] Failed to install CUDA Toolkit." >&2
        return 1
    fi
}
