#!/bin/bash
# ==============================================================================
# 파일명: cuda_toolkit.sh
# 설명: NVIDIA CUDA Toolkit 설치 로직 (Network Repository + 정밀 버전 방식)
# ==============================================================================

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 설치 여부 확인 및 로컬 버전 동기화
# -----------------------------------------------------------------------------
is_installed_cuda_toolkit() {
    local installed=1
    if command -v nvcc &> /dev/null || [[ -x "/usr/local/cuda/bin/nvcc" ]]; then
        installed=0
    fi

    local local_vers
    local_vers=$(_get_local_cuda_versions)
    
    # [Cleanup] 삭제된 버전 정리
    if command -v get_config_keys &>/dev/null; then
        local all_cuda_keys
        all_cuda_keys=$(get_config_keys "APPLICATION_LIST" "${CONFIG_FILE}" | grep "^cuda-toolkit-")
        for key in ${all_cuda_keys}; do
            local ver_in_key="${key#cuda-toolkit-}"
            ver_in_key="${ver_in_key//-/.}"
            
            local dir_exists=false
            for lver in $local_vers; do
                local normalized_lver="$lver"
                [[ "$lver" =~ ^[0-9]+\.[0-9]+$ ]] && normalized_lver="${lver}.0"
                if [[ "$normalized_lver" == "$ver_in_key" ]]; then
                    dir_exists=true; break
                fi
            done
            [[ "$dir_exists" == "false" ]] && delete_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "${key}"
        done
    fi

    # [Update] 신규 버전 등록
    if [[ -n "$local_vers" ]]; then
        for ver in $local_vers; do
            local normalized_ver="$ver"
            [[ "$ver" =~ ^[0-9]+\.[0-9]+$ ]] && normalized_ver="${ver}.0"
            local pkg_key="cuda-toolkit-${normalized_ver//./-}"
            
            if [[ -z "$(get_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "${pkg_key}")" ]]; then
                local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
                set_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "${pkg_key}" "${timestamp}"
            fi
        done
    fi
    return $installed
}

# -----------------------------------------------------------------------------
# @description NVIDIA 저장소 설정 (Keyring 설치)
# -----------------------------------------------------------------------------
_setup_cuda_repo() {
    source /etc/os-release
    local distro="${ID}${VERSION_ID//./}"
    local machine_arch=$(uname -m)
    local target_arch="x86_64"

    case "${machine_arch}" in
        x86_64)
            target_arch="x86_64"
            ;;
        aarch64)
            # ARM64의 경우 sbsa(Server)와 generic arm64(Desktop/Jetson) 선택 필요
            target_arch=$(ui_create_menu "CUDA Architecture Selection" "Select ARM Variant" \
                "Detected ARM64 (aarch64). Choose the repository target:" 15 70 2 \
                "sbsa" "Server Base System Architecture (Standard Servers)" \
                "arm64" "Generic ARM64 (Jetson, Desktop, RPi)")
            
            [[ "${target_arch}" == "CANCEL" ]] && return 1
            ;;
        *)
            echo "[ERROR] Unsupported architecture: ${machine_arch}" >&2
            return 1
            ;;
    esac

    local keyring_url="https://developer.download.nvidia.com/compute/cuda/repos/${distro}/${target_arch}/cuda-keyring_1.1-1_all.deb"
    local keyring_tmp="/tmp/cuda-keyring.deb"

    if ! wget -q "${keyring_url}" -O "${keyring_tmp}"; then
        echo "[ERROR] Failed to download keyring from ${keyring_url}" >&2
        return 1
    fi

    ${G_SUDO_PREFIX} dpkg -i "${keyring_tmp}" > /dev/null 2>&1
    rm -f "${keyring_tmp}"
    ${_PKG_UPDATE_CMD} > /dev/null 2>&1
    return 0
}

# -----------------------------------------------------------------------------
# @description 사용 가능한 상세 패치 버전 목록을 조회합니다.
# -----------------------------------------------------------------------------
_get_available_cuda_versions() {
    local base_pkgs
    base_pkgs=$(apt-cache pkgnames "cuda-toolkit-" | grep -E "^cuda-toolkit-[0-9]+-[0-9]+$")
    
    if [[ -z "$base_pkgs" ]]; then
        apt-cache search "^cuda-toolkit-[0-9]+-[0-9]+$" | awk '{print $1 " " $1}'
        return
    fi

    # madison을 사용하여 동일 패키지 내의 모든 패치 버전 추출
    apt-cache madison ${base_pkgs} | sort -Vr | awk -F'|' '{
        pkg=$1; gsub(/ /, "", pkg);
        full_ver=$2; gsub(/ /, "", full_ver);
        clean_ver=full_ver; gsub(/-.*$/, "", clean_ver);
        print pkg "=" full_ver " CUDA_Toolkit_" clean_ver
    }'
}

# -----------------------------------------------------------------------------
# @description 로컬에 설치된 CUDA 버전 목록을 확인합니다.
# -----------------------------------------------------------------------------
_get_local_cuda_versions() {
    find /usr/local -maxdepth 1 -type d -name "cuda-*" ! -name "cuda" 2>/dev/null | \
        sed 's|/usr/local/cuda-||' | sort -Vr
}

# -----------------------------------------------------------------------------
# @description 활성 CUDA 버전(심볼릭 링크)을 변경합니다.
# -----------------------------------------------------------------------------
_switch_cuda_version() {
    local target_ver="$1"
    local target_path="/usr/local/cuda-${target_ver}"
    local link_path="/usr/local/cuda"

    if [[ ! -d "${target_path}" ]]; then
        # 12.4.0 요청 시 12.4 디렉토리가 있을 수 있음
        local alt_path="/usr/local/cuda-${target_ver%.0}"
        [[ -d "${alt_path}" ]] && target_path="${alt_path}"
    fi

    if [[ -d "${target_path}" ]]; then
        [[ -L "${link_path}" || -d "${link_path}" ]] && ${G_SUDO_PREFIX} rm -rf "${link_path}"
        ${G_SUDO_PREFIX} ln -s "${target_path}" "${link_path}"
    fi
}

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 설치 로직 (저장소 방식 + 정밀 버전)
# -----------------------------------------------------------------------------
_install_cuda_pkg() {
    local target_choice="$1" # pkg=ver 형식

    # 1. 저장소 확보
    if ! apt-cache pkgnames "cuda-toolkit-" | grep -q "."; then
        _setup_cuda_repo || { ui_message_box "Failed to setup NVIDIA repository." "Error"; return 1; }
    fi

    # 2. 버전 선택
    if [[ -z "${target_choice}" ]]; then
        local version_list
        mapfile -t version_list < <(_get_available_cuda_versions)
        
        if [[ ${#version_list[@]} -eq 0 ]]; then
            ui_message_box "Could not find any CUDA packages in the repository." "Error"; return 1
        fi

        target_choice=$(ui_create_menu "CUDA Toolkit Selection" "Select Precise Version" \
            "Choose specific patch version to install via APT:" 18 80 10 "${version_list[@]}")
        [[ "$target_choice" == "CANCEL" ]] && return 1
    fi

    # 3. 설치 수행
    local pkg_name="${target_choice%%=*}"
    local full_ver="${target_choice#*=}"
    local clean_ver="${full_ver%%-*}" # 리비전 제거 (12.4.1)

    clear
    echo "========================================================"
    echo " Installing ${pkg_name} version ${full_ver}"
    echo "========================================================"
    
    # --allow-downgrades 옵션으로 자유로운 버전 이동 보장
    if ${G_SUDO_PREFIX} apt-get install --allow-downgrades -y "${target_choice}"; then
        
        # 3단계 버전 정규화 (12.4 -> 12.4.0)
        local normalized_ver="${clean_ver}"
        [[ "${normalized_ver}" =~ ^[0-9]+\.[0-9]+$ ]] && normalized_ver="${normalized_ver}.0"
        
        local pkg_key="cuda-toolkit-${normalized_ver//./-}"
        local timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
        
        if command -v _record_state &>/dev/null; then
             _record_state "${CONFIG_FILE}" "APPLICATION_LIST" "CUDA Toolkit" "${timestamp}" "${pkg_key}"
        else
             set_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "${pkg_key}" "${timestamp}"
        fi

        _switch_cuda_version "${clean_ver}"
        
        # 환경변수 설정
        local profile_script="/etc/profile.d/cuda.sh"
        if [[ ! -f "${profile_script}" ]]; then
            {
                echo 'export PATH=/usr/local/cuda/bin:${PATH}'
                echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}'
            } | ${G_SUDO_PREFIX} tee "${profile_script}" > /dev/null
        fi
        
        ui_message_box "Successfully installed CUDA Toolkit ${clean_ver}." "Installation Complete"
        return 0
    else
        ui_message_box "APT failed to install ${target_choice}.\nPlease check repository access." "Installation Failed"
        return 1
    fi
}

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 관리 로직 (Main Entry)
# -----------------------------------------------------------------------------
install_cuda_toolkit_logic() {
    [[ $(get_package_manager_type) != "dpkg" ]] && { echo "[ERROR] Only Debian/Ubuntu supported." >&2; return 1; }

    is_installed_cuda_toolkit > /dev/null 2>&1
    
    while true; do
        local local_versions=$(_get_local_cuda_versions)
        [[ -z "${local_versions}" ]] && { _install_cuda_pkg ""; return $?; }

        local current_link_target=""
        [[ -L "/usr/local/cuda" ]] && current_link_target=$(readlink -f /usr/local/cuda)

        local menu_desc="Currently installed versions:\n"
        for ver in $local_versions; do
            local mark=""; [[ "$current_link_target" == *"/cuda-${ver}" ]] && mark=" (*Active)"
            menu_desc+="  - ${ver}${mark}\n"
        done

        local action=$(ui_create_menu "CUDA Version Manager" "Manage CUDA" "${menu_desc}" 20 80 6 \
            "INSTALL" "Install a NEW version (via Network Repo)" \
            "SWITCH"  "Switch active version (Update Symlink)" \
            "EXIT"    "Return")

        case "$action" in
            "INSTALL") _install_cuda_pkg "" ;;
            "SWITCH")
                local ver_opts=()
                for ver in $local_versions; do ver_opts+=("$ver" "Set as active"); done
                local ver_choice=$(ui_create_menu "Switch Version" "Select Version" "Choose version to link:" 15 70 5 "${ver_opts[@]}")
                [[ "$ver_choice" != "CANCEL" ]] && _switch_cuda_version "$ver_choice"
                ;;
            *) break ;;
        esac
    done
    return 0
}
