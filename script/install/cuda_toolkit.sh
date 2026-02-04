#!/bin/bash
# ==============================================================================
# 파일명: cuda_toolkit.sh
# 설명: NVIDIA CUDA Toolkit 설치 로직 (NVIDIA Local Installer 방식)
# ==============================================================================

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 설치 여부 확인 및 로컬 버전 동기화
# @return 0: 설치됨, 1: 설치 안 됨
# -----------------------------------------------------------------------------
is_installed_cuda_toolkit() {
    local installed=1
    
    # 1. 설치 여부 확인
    if command -v nvcc &> /dev/null || [[ -x "/usr/local/cuda/bin/nvcc" ]]; then
        installed=0
    fi

    # 2. [Sync] 로컬에 설치된 버전들을 설정 파일에 동기화
    local local_vers
    local_vers=$(_get_local_cuda_versions)
    
    # 2a. [Cleanup] 삭제된 버전 정리
    if command -v get_config_keys &>/dev/null; then
        local all_cuda_keys
        all_cuda_keys=$(get_config_keys "${CONFIG_FILE}" "APPLICATION_LIST" | grep "^cuda-toolkit-")
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
            if [[ "$dir_exists" == "false" ]]; then
                delete_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "${key}"
            fi
        done
    fi

    # 2b. [Update] 신규 버전 등록
    if [[ -n "$local_vers" ]]; then
        for ver in $local_vers; do
            local normalized_ver="$ver"
            [[ "$ver" =~ ^[0-9]+\.[0-9]+$ ]] && normalized_ver="${ver}.0"

            local pkg_key="cuda-toolkit-${normalized_ver//./-}"
            local current_val
            current_val=$(get_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "${pkg_key}")
            
            if [[ -z "${current_val}" ]]; then
                local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
                set_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "${pkg_key}" "${timestamp}"
            fi
        done
    fi

    return $installed
}

# -----------------------------------------------------------------------------
# @description NVIDIA 서버에서 사용 가능한 버전 목록을 반환합니다.
# -----------------------------------------------------------------------------
_get_available_cuda_versions() {
    local known_versions=(
        "13.1.0" "13.0.2" "13.0.1" "13.0.0"
        "12.8.0" "12.6.3" "12.6.2" "12.6.1" "12.6.0"
        "12.5.1" "12.5.0"
        "12.4.1" "12.4.0"
        "12.3.2" "12.3.1" "12.3.0"
        "12.2.2" "12.2.1" "12.2.0"
        "12.1.1" "12.1.0"
        "12.0.1" "12.0.0"
        "11.8.0" "11.7.1" "11.7.0"
        "11.6.2" "11.6.1" "11.6.0"
        "11.5.2" "11.5.1" "11.5.0"
        "11.4.4" "11.4.3" "11.4.2" "11.4.1" "11.4.0"
    )
    for ver in "${known_versions[@]}"; do
        echo "$ver"
    done
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
        echo "[ERROR] CUDA ${target_ver} not found at ${target_path}"
        return 1
    fi

    echo "[INFO] Switching CUDA symlink to version ${target_ver}..."
    if [[ -L "${link_path}" || -d "${link_path}" ]]; then
        ${G_SUDO_PREFIX} rm -rf "${link_path}"
    fi
    ${G_SUDO_PREFIX} ln -s "${target_path}" "${link_path}"
}

# -----------------------------------------------------------------------------
# @description 선택된 버전의 Local Installer URL을 생성합니다.
# -----------------------------------------------------------------------------
_find_installer_url() {
    local version="$1"
    local base_url="https://developer.download.nvidia.com/compute/cuda/${version}/local_installers"
    
    source /etc/os-release
    local os_tag="ubuntu${VERSION_ID//./}"
    local arch=$(uname -m)
    [[ "$arch" == "x86_64" ]] && arch="amd64"

    local suffix=""
    case "${version}" in
        "13.1.0") suffix="590.48.01-1" ;;
        "13.0.2") suffix="580.95.05-1" ;;
        "13.0.1") suffix="580.82.07-1" ;;
        "13.0.0") suffix="580.65.06-1" ;;
        # 12.x
        "12.8.0") suffix="570.86.10-1" ;;
        "12.6.3") suffix="560.35.05-1" ;;
        "12.6.2") suffix="560.35.03-1" ;;
        "12.6.1") suffix="560.35.02-1" ;;
        "12.6.0") suffix="560.28.03-1" ;;
        "12.5.1") suffix="555.42.06-1" ;;
        "12.5.0") suffix="555.42.02-1" ;;
        "12.4.1") suffix="550.54.15-1" ;;
        "12.4.0") suffix="550.54.14-1" ;;
        "12.3.2") suffix="545.23.08-1" ;;
        "12.3.1") suffix="545.23.08-1" ;;
        "12.3.0") suffix="545.23.06-1" ;;
        "12.2.2") suffix="535.104.05-1" ;;
        "12.2.1") suffix="535.86.10-1" ;;
        "12.2.0") suffix="535.54.03-1" ;;
        "12.1.1") suffix="530.30.02-1" ;;
        "12.1.0") suffix="530.30.02-1" ;;
        "12.0.1") suffix="525.85.12-1" ;;
        "12.0.0") suffix="525.60.13-1" ;;
        # 11.x (Ubuntu 22.04 기준 일부 다를 수 있음, 20.04/22.04 호환성 주의)
        "11.8.0") suffix="520.61.05-1" ;;
        *) return 1 ;;
    esac

    local ver_major_minor="${version%.*}"
    local ver_path_fmt="${ver_major_minor//./-}"
    local filename="cuda-repo-${os_tag}-${ver_path_fmt}-local_${version}-${suffix}_${arch}.deb"
    
    echo "${base_url}/${filename}"
}

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 설치 로직 (Progress Bar 및 개선된 UI)
# -----------------------------------------------------------------------------
_install_cuda_pkg() {
    local target_ver="$1"

    ensure_packages_installed "SYSTEM_TOOLS" "CUDA Dependencies" "wget" "curl" "build-essential" || return 1

    # 1. 버전 선택
    if [[ -z "${target_ver}" ]]; then
        local version_list
        mapfile -t version_list < <(_get_available_cuda_versions)
        
        local menu_options=()
        for ver in "${version_list[@]}"; do
             menu_options+=("$ver" "CUDA Toolkit ${ver}")
        done
        
        target_ver=$(ui_create_menu "CUDA Toolkit Selection" "Select Version" \
            "Select specific version to download and install:" 18 80 10 "${menu_options[@]}")
        [[ "$target_ver" == "CANCEL" ]] && return 1
    fi

    # 2. 인스톨러 URL 생성
    local installer_url
    installer_url=$(_find_installer_url "${target_ver}")
    
    if [[ -z "${installer_url}" ]]; then
        ui_message_box "Mapping for version ${target_ver} is missing in the script.\n\nPlease check and update the '_find_installer_url' function in 'cuda_toolkit.sh'." "Configuration Error"
        return 1
    fi

    # 3. 다운로드 (Progress Bar 적용)
    local tmp_deb="/tmp/cuda-installer-${target_ver}.deb"
    
    # curl을 이용한 진행률 표시 (백그라운드 처리 없이 파이프로 직접 연결)
    (
        curl -L -o "${tmp_deb}" "${installer_url}" 2>&1 | \
        stdbuf -o0 tr '\r' '\n' | \
        stdbuf -o0 sed -u 's/^.* \([0-9]*\)%.*$/\1/' | \
        dialog --backtitle "ASAP Utility - CUDA Installation" \
               --title "Downloading CUDA Toolkit ${target_ver}" \
               --gauge "\nURL: ${installer_url}\n\nThis may take several minutes (approx. 2-3GB)..." 13 80 0
    )

    if [[ ! -f "${tmp_deb}" || ! -s "${tmp_deb}" ]]; then
        ui_message_box "Download failed. Please check your internet connection." "Error"
        return 1
    fi

    # 4. 설치 프로세스 (불필요한 안내창 제거)
    if ! ${G_SUDO_PREFIX} dpkg -i "${tmp_deb}"; then
        ui_message_box "Failed to install the .deb package." "Error"
        rm -f "${tmp_deb}"
        return 1
    fi
    rm -f "${tmp_deb}"

    # Keyring 설정 및 리스트 업데이트 (조용히 처리)
    ${G_SUDO_PREFIX} cp /var/cuda-repo-*-local/cuda-*-keyring.gpg /usr/share/keyrings/ 2>/dev/null
    ${_PKG_UPDATE_CMD} > /dev/null 2>&1

    # 메인 패키지 설치
    local major_minor="${target_ver%.*}"
    local pkg_suffix="${major_minor//./-}"
    local pkg_name="cuda-toolkit-${pkg_suffix}"

    clear
    echo "========================================================"
    echo " Installing ${pkg_name} via APT"
    echo "========================================================"
    if ${G_SUDO_PREFIX} apt-get install -y "${pkg_name}"; then
        # 설정 기록
        local pkg_key="cuda-toolkit-${target_ver//./-}"
        local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
        
        if command -v _record_state &>/dev/null; then
             _record_state "${CONFIG_FILE}" "APPLICATION_LIST" "CUDA Toolkit" "${timestamp}" "${pkg_key}"
        else
             set_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "${pkg_key}" "${timestamp}"
        fi

        _switch_cuda_version "${target_ver}"
        
        # 환경변수 설정
        local profile_script="/etc/profile.d/cuda.sh"
        if [[ ! -f "${profile_script}" ]]; then
            {
                echo 'export PATH=/usr/local/cuda/bin:${PATH}'
                echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}'
            } | ${G_SUDO_PREFIX} tee "${profile_script}" > /dev/null
        fi
        
        ui_message_box "CUDA Toolkit ${target_ver} has been installed successfully." "Success"
        return 0
    else
        ui_message_box "APT installation failed for ${pkg_name}." "Error"
        return 1
    fi
}

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 관리 로직 (Main Entry)
# -----------------------------------------------------------------------------
install_cuda_toolkit_logic() {
    if [[ $(get_package_manager_type) != "dpkg" ]]; then
        echo "[ERROR] Only Debian/Ubuntu systems are supported." >&2
        return 1
    fi

    # 초기 스캔 (조용히 처리)
    is_installed_cuda_toolkit > /dev/null 2>&1
    
    while true; do
        local local_versions
        local_versions=$(_get_local_cuda_versions)
        
        if [[ -z "${local_versions}" ]]; then
            _install_cuda_pkg ""
            return $?
        fi

        local current_link_target=""
        [[ -L "/usr/local/cuda" ]] && current_link_target=$(readlink -f /usr/local/cuda)

        local menu_desc="Currently installed versions on this system:\n"
        for ver in $local_versions; do
            local mark=""
            [[ "$current_link_target" == *"/cuda-${ver}" ]] && mark=" (*Active)"
            menu_desc+="  - ${ver}${mark}\n"
        done
        menu_desc+="\nSelect an action to perform:"

        local action
        action=$(ui_create_menu "CUDA Version Manager" "Manage CUDA" "${menu_desc}" 20 80 6 \
            "INSTALL" "Download & Install a NEW version" \
            "SWITCH"  "Switch active version (Update Symlink)" \
            "EXIT"    "Return to main menu")

        case "$action" in
            "INSTALL")
                _install_cuda_pkg ""
                ;;
            "SWITCH")
                local ver_opts=()
                for ver in $local_versions; do
                    ver_opts+=("$ver" "Set as active version")
                done
                local ver_choice
                ver_choice=$(ui_create_menu "Switch Version" "Select Version" "Choose version to link to /usr/local/cuda" 15 70 5 "${ver_opts[@]}")
                [[ "$ver_choice" != "CANCEL" ]] && _switch_cuda_version "$ver_choice"
                ;;
            *) break ;;
        esac
    done
    return 0
}