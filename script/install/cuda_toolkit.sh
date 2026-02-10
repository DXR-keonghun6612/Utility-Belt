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
# @param $1 target_arch (선택: aarch64의 경우 "sbsa" 또는 "arm64")
# -----------------------------------------------------------------------------
_setup_cuda_repo() {
    local target_arch_arg="$1"
    source /etc/os-release
    local distro="${ID}${VERSION_ID//./}"
    local machine_arch=$(uname -m)
    local target_arch="x86_64"

    case "${machine_arch}" in
        x86_64)
            target_arch="x86_64"
            ;;
        aarch64)
            if [[ -n "${target_arch_arg}" ]]; then
                target_arch="${target_arch_arg}"
            else
                # 인자가 없으면 기본값 설정 (Headless 대응)
                target_arch="sbsa"
            fi
            ;;
        *)
            echo "[ERROR] Unsupported architecture: ${machine_arch}" >&2
            return 1
            ;;
    esac

    local keyring_url="https://developer.download.nvidia.com/compute/cuda/repos/${distro}/${target_arch}/cuda-keyring_1.1-1_all.deb"
    local keyring_tmp="/tmp/cuda-keyring.deb"

    echo "[INFO] Setting up NVIDIA repository for ${target_arch}..."
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
        echo "[INFO] Switched active CUDA to ${target_ver}"
        return 0
    fi
    return 1
}

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 설치 로직 (저장소 방식 + 정밀 버전)
# @param $1 target_choice (pkg=ver 형식)
# @param $2 target_arch (aarch64용 아키텍처 옵션)
# -----------------------------------------------------------------------------
_install_cuda_pkg() {
    local target_choice="$1"
    local target_arch="$2"

    # 1. 저장소 확보
    if ! apt-cache pkgnames "cuda-toolkit-" | grep -q "."; then
        _setup_cuda_repo "${target_arch}" || return 1
    fi

    # 2. 버전 선택 (인자가 없으면 에러 또는 최신 자동 선택)
    if [[ -z "${target_choice}" ]]; then
        echo "[ERROR] No CUDA version specified for installation." >&2
        return 1
    fi

    # 3. 설치 수행
    local pkg_name="${target_choice%%=*}"
    local full_ver="${target_choice#*=}"
    local clean_ver="${full_ver%%-*}"

    echo "========================================================"
    echo " Installing ${pkg_name} version ${full_ver}"
    echo "========================================================"
    
    if ${G_SUDO_PREFIX} apt-get install --allow-downgrades -y "${target_choice}"; then
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
        
        echo "[SUCCESS] CUDA Toolkit ${clean_ver} installed successfully."
        return 0
    else
        echo "[ERROR] APT failed to install ${target_choice}." >&2
        return 1
    fi
}

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 관리 로직 (Main Entry)
# @param $1 action ("INSTALL" or "SWITCH")
# @param $2 target_choice/target_ver
# @param $3 target_arch (aarch64 전용)
# -----------------------------------------------------------------------------
install_cuda_toolkit_logic() {
    local action="$1"
    local target="$2"
    local arch="$3"

    [[ $(get_package_manager_type) != "dpkg" ]] && { echo "[ERROR] Only Debian/Ubuntu supported." >&2; return 1; }

    # 인자가 넘어온 경우에만 동작
    if [[ -n "${action}" ]]; then
        case "${action}" in
            "INSTALL") _install_cuda_pkg "${target}" "${arch}" ;;
            "SWITCH")  _switch_cuda_version "${target}" ;;
        esac
    fi
    return 0
}