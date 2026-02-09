#!/bin/bash
# ==============================================================================
# 파일명: cudnn_library.sh
# 설명: NVIDIA cuDNN Library 설치 로직 (CUDA 버전 연동 및 정밀 선택)
# ==============================================================================

# -----------------------------------------------------------------------------
# @description cuDNN 설치 여부 확인
# @return 0: 설치됨, 1: 설치 안 됨
# -----------------------------------------------------------------------------
is_installed_cudnn_library() {
    if dpkg-query -W -f='${Status}' "libcudnn*" 2>/dev/null | grep -q "install ok installed"; then
        _sync_local_cudnn_to_config
        return 0
    fi
    return 1
}

# -----------------------------------------------------------------------------
# @description 로컬에 설치된 cuDNN 정보를 설정 파일에 동기화
# -----------------------------------------------------------------------------
_sync_local_cudnn_to_config() {
    local installed_pkgs
    installed_pkgs=$(dpkg-query -W -f='${Package} ${Version}\n' "libcudnn[0-9]" 2>/dev/null)
    
    if [[ -n "$installed_pkgs" ]]; then
        while read -r pkg ver; do
            [[ -z "$ver" ]] && continue
            local clean_ver="${ver%%-*}"
            [[ -z "$clean_ver" ]] && continue
            
            local conf_key="cudnn-library-${clean_ver}"
            if [[ -z "$(get_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "${conf_key}")" ]]; then
                local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
                set_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "${conf_key}" "${timestamp}"
            fi
        done <<< "$installed_pkgs"
    fi
}

# -----------------------------------------------------------------------------
# @description 현재 활성화된 CUDA 메이저 버전을 감지합니다.
# @return CUDA 메이저 버전 (예: 12, 11) 또는 "unknown"
# -----------------------------------------------------------------------------
_get_active_cuda_major_version() {
    local cuda_path="/usr/local/cuda"
    if [[ -L "${cuda_path}" ]]; then
        local target
        target=$(readlink -f "${cuda_path}")
        if [[ "$target" =~ cuda-([0-9]+) ]]; then
            echo "${BASH_REMATCH[1]}"
            return
        fi
    fi
    
    if command -v nvcc &>/dev/null; then
        local ver
        ver=$(nvcc --version | grep -oP 'release \K[0-9]+')
        echo "${ver%%.*}"
        return
    fi
    
    echo "unknown"
}

# -----------------------------------------------------------------------------
# @description 설치 가능한 cuDNN 버전 목록 조회 (CUDA 버전 필터링 적용)
# @param $1 cuda_major (선택: 필터링할 CUDA 메이저 버전)
# @return stdout "패키지명=버전 설명" 목록
# -----------------------------------------------------------------------------
_get_available_cudnn_versions() {
    local cuda_major="$1"
    local base_pkgs
    
    if [[ "$cuda_major" != "unknown" && -n "$cuda_major" ]]; then
        # 현재 CUDA 버전에 맞는 패키지 우선 검색 (예: libcudnn9-cuda-12)
        base_pkgs=$(apt-cache pkgnames "libcudnn" | grep -E "^libcudnn[0-9]-cuda-${cuda_major}$")
    fi
    
    # 만약 전용 패키지가 없거나 버전이 지정되지 않은 경우 전체 검색
    if [[ -z "$base_pkgs" ]]; then
        base_pkgs=$(apt-cache pkgnames "libcudnn" | grep -E "^libcudnn[0-9](-cuda-[0-9]+)?$")
    fi
    
    if [[ -z "$base_pkgs" ]]; then return; fi

    apt-cache madison ${base_pkgs} | sort -Vr | awk -F'|' '{
        pkg=$1; gsub(/ /, "", pkg);
        full_ver=$2; gsub(/ /, "", full_ver);
        clean_ver=full_ver; gsub(/-.*$/, "", clean_ver);
        
        # 가독성을 위해 CUDA 호환 정보 표시
        cuda_info=""
        if (pkg ~ /cuda-/) {
            split(pkg, parts, "-cuda-");
            cuda_info = " [for CUDA " parts[2] "]";
        }
        
        print pkg "=" full_ver " cuDNN_v" clean_ver cuda_info
    }'
}

# -----------------------------------------------------------------------------
# @description cuDNN Library 설치 로직 (Main Entry)
# -----------------------------------------------------------------------------
install_cudnn_library_logic() {
    local target_choice="$1"

    if ! apt-cache pkgnames "libcudnn" | grep -q "."; then
        ui_message_box "NVIDIA repository is not found.\nPlease install 'CUDA Toolkit' first to setup the repository." "Repository Missing"
        return 1
    fi

    # 1. 현재 CUDA 버전 감지
    local cuda_major
    cuda_major=$(_get_active_cuda_major_version)

    # 2. 버전 선택
    if [[ -z "${target_choice}" ]]; then
        local version_list_raw
        version_list_raw=$(_get_available_cudnn_versions "${cuda_major}")
        
        if [[ -z "${version_list_raw}" ]]; then
            ui_message_box "No compatible cuDNN packages found for CUDA ${cuda_major}.\nShowing all available packages..." "Notice"
            version_list_raw=$(_get_available_cudnn_versions "unknown")
        fi

        if [[ -z "${version_list_raw}" ]]; then
            ui_message_box "No cuDNN packages found in the repository." "Error"; return 1
        fi

        local menu_options=()
        while read -r tag item; do
            menu_options+=("${tag}" "${item}")
        done <<< "${version_list_raw}"

        local prompt="Detected active CUDA major version: ${cuda_major}\n\nPlease select a compatible cuDNN version:"
        [[ "$cuda_major" == "unknown" ]] && prompt="Could not detect active CUDA version.\nPlease select a cuDNN version:"

        target_choice=$(ui_create_menu "cuDNN Installation" "Select Compatible Version" "${prompt}" 18 80 10 "${menu_options[@]}")
        [[ "$target_choice" == "CANCEL" ]] && return 1
    fi

    # 3. 설치 수행
    local pkg_name="${target_choice%%=*}"
    local full_ver="${target_choice#*=}"
    local clean_ver="${full_ver%%-*}"

    # 개발용 패키지명 결정 (libcudnn9 -> libcudnn9-dev / libcudnn9-cuda-12 -> libcudnn9-dev-cuda-12)
    local dev_pkg=""
    if [[ "$pkg_name" =~ -cuda- ]]; then
        dev_pkg="${pkg_name/-cuda/-dev-cuda}"
    else
        dev_pkg="${pkg_name}-dev"
    fi
    local dev_target="${dev_pkg}=${full_ver}"

    clear
    echo "========================================================"
    echo " Installing ${pkg_name} version ${full_ver}"
    echo "========================================================"

    if ${G_SUDO_PREFIX} apt-get install --allow-downgrades -y "${target_choice}" "${dev_target}"; then
        local conf_key="cudnn-library-${clean_ver}"
        local timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
        
        if command -v _record_state &>/dev/null; then
             _record_state "${CONFIG_FILE}" "APPLICATION_LIST" "cuDNN Library" "${timestamp}" "${conf_key}"
        else
             set_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "${conf_key}" "${timestamp}"
        fi
        
        ui_message_box "cuDNN Library ${clean_ver} and its headers installed successfully." "Success"
        return 0
    else
        ui_message_box "Failed to install cuDNN packages.\nPlease check the terminal for errors." "Error"
        return 1
    fi
}