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
# @param $1 target_choice (pkg=ver 형식)
# -----------------------------------------------------------------------------
install_cudnn_library_logic() {
    local target_choice="$1"

    if ! apt-cache pkgnames "libcudnn" | grep -q "."; then
        echo "[ERROR] NVIDIA repository not found. Please install CUDA Toolkit first." >&2
        return 1
    fi

    # 1. 인자가 없으면 에러 (무인 설치 시 버전 명시 필수)
    if [[ -z "${target_choice}" ]]; then
        echo "[ERROR] No cuDNN version specified for installation." >&2
        return 1
    fi

    # 2. 설치 수행
    local pkg_name="${target_choice%%=*}"
    local full_ver="${target_choice#*=}"
    local clean_ver="${full_ver%%-*}"

    # 개발용 패키지명 결정
    local dev_pkg=""
    if [[ "$pkg_name" =~ -cuda- ]]; then
        dev_pkg="${pkg_name/-cuda/-dev-cuda}"
    else
        dev_pkg="${pkg_name}-dev"
    fi
    local dev_target="${dev_pkg}=${full_ver}"

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
        
        echo "[SUCCESS] cuDNN Library ${clean_ver} installed successfully."
        return 0
    else
        echo "[ERROR] Failed to install cuDNN packages." >&2
        return 1
    fi
}
