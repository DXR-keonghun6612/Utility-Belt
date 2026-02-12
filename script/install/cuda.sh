#!/bin/bash
# ==============================================================================
# 파일명: cuda.sh
# 설명: NVIDIA CUDA Toolkit 및 cuDNN Library 설치/관리 로직 통합 모듈
# ==============================================================================

# =================================================================-------------
# [공통/유틸리티]
# =================================================================-------------

# -----------------------------------------------------------------------------
# @description NVIDIA 저장소 설정 (Keyring 설치)
# @param $1 target_arch (선택: aarch64의 경우 "sbsa" 또는 "arm64")
# -----------------------------------------------------------------------------
setup_nvidia_repo() {
    local target_arch_arg="$1"
    source /etc/os-release
    local distro="${ID}${VERSION_ID//./}"
    local machine_arch=$(uname -m)
    local target_arch="x86_64"

    case "${machine_arch}" in
        x86_64)  target_arch="x86_64" ;;
        aarch64) target_arch="${target_arch_arg:-sbsa}" ;;
        *) log_error "Unsupported architecture: ${machine_arch}"; return 1 ;;
    esac

    local keyring_url="https://developer.download.nvidia.com/compute/cuda/repos/${distro}/${target_arch}/cuda-keyring_1.1-1_all.deb"
    local keyring_tmp="/tmp/cuda-keyring.deb"

    log_info "Setting up NVIDIA repository for ${target_arch}..."
    if ! wget -q "${keyring_url}" -O "${keyring_tmp}"; then
        log_error "Failed to download keyring from ${keyring_url}"
        return 1
    fi

    ${G_SUDO_PREFIX} dpkg -i "${keyring_tmp}" > /dev/null 2>&1
    rm -f "${keyring_tmp}"
    ${_PKG_UPDATE_CMD} > /dev/null 2>&1
    return 0
}

# =================================================================-------------
# [CUDA Toolkit 관련]
# =================================================================-------------

# -----------------------------------------------------------------------------
# @description 현재 활성화된 CUDA Toolkit 설치 경로를 감지합니다.
# -----------------------------------------------------------------------------
detect_cuda_toolkit_path() {
    local default_path="/usr/local/cuda"
    
    if [[ -d "${default_path}" ]]; then
        echo "${default_path}"
    elif command -v nvcc &>/dev/null; then
        local nvcc_path; nvcc_path=$(which nvcc)
        echo "${nvcc_path%/bin/nvcc}"
    fi
}

# -----------------------------------------------------------------------------
# @description CUDA Toolkit의 정밀 버전(Patch 레벨 포함)을 감지합니다.
# @param $1 cuda_path (선택: 지정하지 않으면 활성 경로에서 감지)
# -----------------------------------------------------------------------------
# shellcheck disable=SC2120
detect_cuda_version() {
    local cuda_path="${1:-$(detect_cuda_toolkit_path)}"
    [[ -z "${cuda_path}" ]] && return

    local nvcc_bin="${cuda_path}/bin/nvcc"
    if [[ ! -x "${nvcc_bin}" ]]; then
        nvcc_bin=$(command -v nvcc)
    fi

    if [[ -n "${nvcc_bin}" ]]; then
        "${nvcc_bin}" --version | grep "V[0-9]" | sed 's/.*V\([0-9.]*\).*/\1/'
    fi
}

# -----------------------------------------------------------------------------
# @description 로컬에 설치된 CUDA 버전 목록을 확인합니다 (경로명 기반).
# @return "12.4 11.8" 형태의 목록
# -----------------------------------------------------------------------------
get_local_cuda_versions() {
    find /usr/local -maxdepth 1 -type d -name "cuda-*" ! -name "cuda" 2>/dev/null | 
        sed 's|/usr/local/cuda-||' | sort -Vr
}

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 설치 여부 확인 및 로컬 버전 동기화
# -----------------------------------------------------------------------------
is_installed_cuda_toolkit() {
    local active_path; active_path=$(detect_cuda_toolkit_path)
    local local_vers; local_vers=$(get_local_cuda_versions)
    
    # 설정 파일 동기화 (삭제된 버전 정리 및 신규 등록)
    if command -v get_config_keys &>/dev/null; then
        local all_keys; all_keys=$(get_config_keys "APPLICATION_LIST" "${G_STATE_FILE}" | grep "^cuda-toolkit-")
        for key in ${all_keys}; do
            local ver_in_key="${key#cuda-toolkit-}"; ver_in_key="${ver_in_key//-/.}"
            local exists=false
            for v in ${local_vers}; do
                local nv="$v"; [[ "$v" =~ ^[0-9]+\.[0-9]+$ ]] && nv="${v}.0"
                [[ "$nv" == "$ver_in_key" ]] && { exists=true; break; }
            done
            [[ "$exists" == "false" ]] && delete_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "${key}"
        done
    fi

    for v in ${local_vers}; do
        local nv="$v"; [[ "$v" =~ ^[0-9]+\.[0-9]+$ ]] && nv="${v}.0"
        local pkg_key="cuda-toolkit-${nv//./-}"
        if [[ -z "$(get_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "${pkg_key}")" ]]; then
            set_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "${pkg_key}" "$(date "+%Y-%m-%dT%H:%M:%S")"
        fi
    done

    [[ -n "${active_path}" ]]
}

# -----------------------------------------------------------------------------
# @description 사용 가능한 상세 패치 버전 목록을 조회합니다 (APT 기반).
# -----------------------------------------------------------------------------
get_available_cuda_versions() {
    local pkg_prefix="cuda-toolkit-"
    local base_pkgs; base_pkgs=$(apt-cache pkgnames "${pkg_prefix}" | grep -E "^${pkg_prefix}[0-9]+-[0-9]+$")
    
    [[ -z "$base_pkgs" ]] && { 
        apt-cache search "^${pkg_prefix}[0-9]+-[0-9]+$" | awk '{print $1 "=" $1 " " $1}'
        return 
    }

    apt-cache madison ${base_pkgs} | sort -Vr | awk -F'|' '{
        pkg=$1; gsub(/ /, "", pkg);
        ver=$2; gsub(/ /, "", ver);
        
        # 패키지 명에서 X.Y 버전 추출
        match(pkg, /cuda-toolkit-([0-9]+)-([0-9]+)/, arr);
        short_ver = arr[1] "." arr[2];
        
        clean_ver=ver; gsub(/-.*$/, "", clean_ver);
        print pkg "=" ver " CUDA_Toolkit_" clean_ver " (Path: cuda-" short_ver ")"
    }'
}

# -----------------------------------------------------------------------------
# @description 활성 CUDA 버전(심볼릭 링크)을 변경합니다.
# -----------------------------------------------------------------------------
switch_cuda_toolkit_version() {
    local target_ver="$1"
    local target_path="/usr/local/cuda-${target_ver}"
    local link_path="/usr/local/cuda"

    if [[ ! -d "${target_path}" ]]; then
        # 12.4.0 형태가 아닌 12.4 형태의 디렉토리도 확인
        local alt_path="/usr/local/cuda-${target_ver%.0}"
        [[ -d "${alt_path}" ]] && target_path="${alt_path}"
    fi

    if [[ -d "${target_path}" ]]; then
        ${G_SUDO_PREFIX} rm -rf "${link_path}"
        ${G_SUDO_PREFIX} ln -s "${target_path}" "${link_path}"
        log_info "Switched active CUDA to ${target_ver}"
        return 0
    fi
    log_error "CUDA path not found: ${target_path}"; return 1
}

# -----------------------------------------------------------------------------
# @description CUDA Toolkit을 설치합니다.
# -----------------------------------------------------------------------------
install_cuda_toolkit() {
    local target="$1"
    local target_arch="$2"

    if ! apt-cache pkgnames "cuda-toolkit-" | grep -q "."; then
        setup_nvidia_repo "${target_arch}" || return 1
    fi

    [[ -z "${target}" ]] && { log_error "No CUDA version specified."; return 1; }

    local choice=""
    # 1. 이미 pkg=ver 형식인 경우
    if [[ "$target" == *"="* ]]; then
        choice="$target"
    else
        # 2. 버전 번호 정규화: 12.4 -> 12.4.0 (2마디인 경우만 .0 추가)
        local norm_target="${target}"
        [[ "${norm_target}" =~ ^[0-9]+\.[0-9]+$ ]] && norm_target="${target}.0"
        
        log_info "Attempting to resolve package for CUDA version: ${norm_target}"
        
        # 3. 정규화된 버전으로 완전 일치 검색 시도
        choice=$(get_available_cuda_versions | grep "CUDA_Toolkit_${norm_target} " | head -n 1 | awk '{print $1}')
        
        # 4. 실패 시, Path 기반 검색 (입력된 메이저.마이너 버전의 최신 패키지)
        if [[ -z "$choice" ]]; then
             choice=$(get_available_cuda_versions | grep "(Path: cuda-${target})" | head -n 1 | awk '{print $1}')
        fi
        
        [[ -n "$choice" ]] && log_info "Resolved to: ${choice}"
    fi

    [[ -z "$choice" ]] && { log_error "Could not resolve CUDA package for ${target}."; return 1; }

    local pkg_name="${choice%%=*}"
    local full_ver="${choice#*=}"
    local clean_ver="${full_ver%%-*}"

    log_info "Installing ${pkg_name} version ${full_ver}..."
    if ${G_SUDO_PREFIX} apt-get install --allow-downgrades -y "${choice}"; then
        # 기록 시에도 동일한 정규화 규칙 적용 (12.4 -> 12.4.0)
        local state_ver="${clean_ver}"
        [[ "${state_ver}" =~ ^[0-9]+\.[0-9]+$ ]] && state_ver="${state_ver}.0"
        
        local pkg_key="cuda-toolkit-${state_ver//./-}"
        set_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "${pkg_key}" "$(date "+%Y-%m-%dT%H:%M:%S")"
        
        local profile_script="/etc/profile.d/cuda.sh"
        if [[ ! -f "${profile_script}" ]]; then
            echo -e 'export PATH=/usr/local/cuda/bin:${PATH}\nexport LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}' | ${G_SUDO_PREFIX} tee "${profile_script}" > /dev/null
        fi
        log_success "CUDA Toolkit ${clean_ver} installed."; return 0
    fi
    return 1
}

# =================================================================-------------
# [cuDNN Library 관련]
# =================================================================-------------

# -----------------------------------------------------------------------------
# @description 설치된 cuDNN 버전을 감지합니다.
# -----------------------------------------------------------------------------
detect_cudnn_version() {
    if command -v dpkg &>/dev/null; then
        dpkg-query -W -f='${Status} ${Version}\n' "libcudnn*" 2>/dev/null | 
            grep "install ok installed" | awk '{print $4}' | head -n 1 | cut -d'-' -f1
    fi
}

is_installed_cudnn_library() {
    local ver; ver=$(detect_cudnn_version)
    if [[ -n "${ver}" ]]; then
        sync_local_cudnn_to_config
        return 0
    fi
    return 1
}

sync_local_cudnn_to_config() {
    local pkgs; pkgs=$(dpkg-query -W -f='${Package} ${Version}\n' "libcudnn[0-9]" 2>/dev/null)
    [[ -z "$pkgs" ]] && return
    while read -r _ ver; do
        local clean_ver="${ver%%-*}"; [[ -z "$clean_ver" ]] && continue
        local key="cudnn-library-${clean_ver}"
        if [[ -z "$(get_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "${key}")" ]]; then
            set_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "${key}" "$(date "+%Y-%m-%dT%H:%M:%S")"
        fi
    done <<< "$pkgs"
}

get_active_cuda_major_version() {
    local ver; ver=$(detect_cuda_version)
    [[ -n "${ver}" ]] && echo "${ver%%.*}" || echo "unknown"
}

get_available_cudnn_versions() {
    local major="$1"
    local base_pkgs
    [[ "$major" != "unknown" && -n "$major" ]] && base_pkgs=$(apt-cache pkgnames "libcudnn" | grep -E "^libcudnn[0-9]-cuda-${major}$")
    [[ -z "$base_pkgs" ]] && base_pkgs=$(apt-cache pkgnames "libcudnn" | grep -E "^libcudnn[0-9](-cuda-[0-9]+)?$")
    [[ -z "$base_pkgs" ]] && return

    apt-cache madison ${base_pkgs} | sort -Vr | awk -F'|' '{
        pkg=$1; gsub(/ /, "", pkg);
        ver=$2; gsub(/ /, "", ver);
        clean_ver=ver; gsub(/-.*$/, "", clean_ver);
        info=""; if (pkg ~ /cuda-/) { split(pkg, parts, "-cuda-"); info = " [for CUDA " parts[2] "]"; }
        print pkg "=" ver " cuDNN_v" clean_ver info
    }'
}

install_cudnn_library() {
    local target="$1"
    if ! apt-cache pkgnames "libcudnn" | grep -q "."; then log_error "NVIDIA repository not found."; return 1; fi
    [[ -z "${target}" ]] && { log_error "No cuDNN version specified."; return 1; }

    local choice=""
    if [[ "$target" == *"="* ]]; then
        choice="$target"
    else
        local major; major=$(get_active_cuda_major_version)
        choice=$(get_available_cudnn_versions "${major}" | grep "cuDNN_v${target}" | head -n 1 | awk '{print $1}')
        [[ -z "$choice" ]] && choice=$(get_available_cudnn_versions "unknown" | grep "cuDNN_v${target}" | head -n 1 | awk '{print $1}')
    fi

    [[ -z "$choice" ]] && { log_error "Could not resolve cuDNN package for ${target}."; return 1; }

    local pkg_name="${choice%%=*}"
    local full_ver="${choice#*=}"
    local clean_ver="${full_ver%%-*}"
    local dev_pkg; [[ "$pkg_name" =~ -cuda- ]] && dev_pkg="${pkg_name/-cuda/-dev-cuda}" || dev_pkg="${pkg_name}-dev"

    # --- 기존 충돌 패키지 제거 로직 추가 ---
    log_info "Checking for existing cuDNN packages to prevent conflicts..."
    local installed_pkgs; mapfile -t installed_pkgs < <(dpkg-query -W -f='${Status} ${Package}\n' 'libcudnn*' 2>/dev/null | awk '/^install ok installed/ {print $4}')
    
    local to_remove=()
    for pkg in "${installed_pkgs[@]}"; do
        if [[ "${pkg}" != "${pkg_name}" && "${pkg}" != "${dev_pkg}" ]]; then
            to_remove+=("${pkg}")
        fi
    done

    if [[ ${#to_remove[@]} -gt 0 ]]; then
        log_info "Removing conflicting cuDNN packages: ${to_remove[*]}"
        ${_PKG_REMOVE_CMD} "${to_remove[@]}" > /dev/null 2>&1
        [[ -n "$_PKG_AUTOREMOVE_CMD" ]] && ${_PKG_AUTOREMOVE_CMD} > /dev/null 2>&1
    fi
    # --------------------------------------

    log_info "Installing ${pkg_name} version ${full_ver}..."
    if ${G_SUDO_PREFIX} apt-get install --allow-downgrades -y "${choice}" "${dev_pkg}=${full_ver}"; then
        set_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "cudnn-library-${clean_ver}" "$(date "+%Y-%m-%dT%H:%M:%S")"
        log_success "cuDNN Library ${clean_ver} installed."; return 0
    fi
    return 1
}
