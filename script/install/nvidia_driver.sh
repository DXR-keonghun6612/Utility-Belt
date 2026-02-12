#!/bin/bash
# ==============================================================================
# 파일명: nvidia_driver.sh
# 설명: NVIDIA 드라이버 확인 및 설치 로직
# ==============================================================================

# -----------------------------------------------------------------------------
# @description NVIDIA 드라이버 지원 여부 확인
# -----------------------------------------------------------------------------
is_supported_nvidia_driver() {
    # 현재는 dpkg 시스템의 ubuntu-drivers 유틸리티를 사용하는 방식만 지원
    [[ $(_get_package_manager_type) == "dpkg" ]]
}

# -----------------------------------------------------------------------------
# @description NVIDIA 드라이버 설치 여부 확인 및 설정 동기화
# @return 0: 설치됨, 1: 설치 안 됨
# -----------------------------------------------------------------------------
is_installed_nvidia_driver() {
    local installed=1
    local current_driver=""

    # 1. nvidia-smi 명령어가 있으면 설치된 것으로 간주
    if command -v nvidia-smi &> /dev/null; then
        installed=0
        # 설치된 드라이버 버전 추출 (예: 535.183.01)
        current_driver=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits | head -n 1)
    fi

    # 2. 패키지 매니저(dpkg)를 통해 확인 (nvidia-smi가 없는 경우 대비)
    if [[ $installed -ne 0 ]]; then
        if dpkg-query -W -f='${Status}' 'nvidia-driver-*' 2>/dev/null | grep -q 'install ok installed'; then
            installed=0
            current_driver=$(dpkg-query -W -f='${Package}' 'nvidia-driver-*' 2>/dev/null | grep -E '^nvidia-driver-[0-9]+$' | head -n 1)
        fi
    fi

    # [Sync Config] 설치된 상태인 경우 설정 파일 기록 확인
    if [[ $installed -eq 0 && -n "$current_driver" ]]; then
        if [[ -n "${G_STATE_FILE}" ]]; then
            local current_conf_val
            current_conf_val=$(get_config_value "${G_STATE_FILE}" "DRIVER_LIST" "nvidia-driver")
            if [[ -z "$current_conf_val" ]]; then
                local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
                add_config_section "${G_STATE_FILE}" "DRIVER_LIST"
                set_config_value "${G_STATE_FILE}" "DRIVER_LIST" "nvidia-driver" "${current_driver} (${timestamp})"
            fi
        fi
    elif [[ $installed -ne 0 ]]; then
        # 설치 안 된 경우 설정 파일에서 기록 삭제
        if [[ -n "${G_STATE_FILE}" ]]; then
            delete_config_value "${G_STATE_FILE}" "DRIVER_LIST" "nvidia-driver"
        fi
    fi

    return $installed
}

# -----------------------------------------------------------------------------
# @description 설치 가능한 NVIDIA 드라이버 목록을 반환합니다.
#           - 내부적으로 ubuntu-drivers-common 패키지가 필요합니다.
# @return 0: 성공, 1: 지원하지 않는 시스템 또는 드라이버 없음
# @stdout "driver_name recommended" 형식의 목록
# -----------------------------------------------------------------------------
get_available_nvidia_drivers() {
    # 1. 배포판 의존성 확인
    if [[ $(_get_package_manager_type) != "dpkg" ]]; then
        log_error "'ubuntu-drivers' utility is only supported on Debian/Ubuntu-based systems."
        return 1
    fi

    # 2. 필수 패키지 확인 (이미 있으면 apt 호출 건너뜀)
    if ! command -v ubuntu-drivers &> /dev/null; then
        ensure_packages_installed "PACKAGES_LIST" "ubuntu-drivers-common" || return $?
    fi

    # 3. 드라이버 목록 추출 및 정렬
    local drivers
    # ubuntu-drivers list 결과가 없는 경우 apt-cache로 대체 시도
    drivers=$(ubuntu-drivers list 2>/dev/null | grep "nvidia-driver-")
    
    if [[ -z "$drivers" ]]; then
        log_warn "No drivers found via 'ubuntu-drivers'. Searching via 'apt-cache' (Faster but less hardware-aware)..."
        drivers=$(apt-cache search "^nvidia-driver-[0-9]+$" | awk '{print $1}')
    fi

    if [[ -z "$drivers" ]]; then
        return 1
    fi

    # 정규화된 목록 생성 (이름 추천여부)
    echo "$drivers" | awk '/nvidia-driver-[0-9]+/ {
        sub(/,$/, "", $1);
        rec = ($0 ~ /\(recommended\)/ || $3 == "(recommended)") ? "(recommended)" : "";
        print $1, rec;
    }' | sort -Vr | uniq
    
    return 0
}

# -----------------------------------------------------------------------------
# @description 지정된 NVIDIA 드라이버를 설치하고 기존 드라이버를 정리합니다.
# @param $1 selected_driver (설치할 드라이버 패키지 명)
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
install_nvidia_driver_logic() {
    local selected_driver="$1"

    if [[ -z "${selected_driver}" ]]; then
        log_error "No driver name provided."
        return 1
    fi

    # 0. 필수 의존성 확인
    ensure_packages_installed "PACKAGES_LIST" "NVIDIA Driver Utils" "ubuntu-drivers-common" || return 1

    # 1. 배포판 의존성 확인
    if [[ $(_get_package_manager_type) != "dpkg" ]]; then
        log_error "NVIDIA driver cleanup logic is currently only supported on Debian/Ubuntu-based systems."
        return 1
    fi

    # 2. 기존 설치된 다른 NVIDIA 드라이버 감지
    log_info "Searching for previously installed NVIDIA drivers..."
    local installed_drivers
    mapfile -t installed_drivers < <(dpkg-query -W -f='${Status} ${Package}\n' 'nvidia-driver-*' 2>/dev/null | awk '/^install ok installed/ {print $4}')
    
    local drivers_to_uninstall=()
    for installed in "${installed_drivers[@]}"; do
        if [[ "${installed}" != "${selected_driver}" ]]; then
            drivers_to_uninstall+=("${installed}")
        fi
    done

    # 3. 충돌 드라이버 제거
    if [[ ${#drivers_to_uninstall[@]} -gt 0 ]]; then
        if [[ "${G_IS_ROOT}" == "false" && -z "${G_SUDO_PREFIX}" ]]; then
            log_error "Root privileges (or sudo) are required to remove conflicting drivers."
            return 5
        fi
        log_info "Removing conflicting drivers: ${drivers_to_uninstall[*]}"
        ${_PKG_REMOVE_CMD} "${drivers_to_uninstall[@]}"
        if [[ -n "$_PKG_AUTOREMOVE_CMD" ]]; then
            ${_PKG_AUTOREMOVE_CMD}
        fi
    fi

    # 4. 새 드라이버 설치
    log_info "Installing selected driver: ${selected_driver}"
    if ensure_packages_installed "DRIVER_LIST" "${selected_driver}"; then
        local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
        set_config_value "${G_STATE_FILE}" "DRIVER_LIST" "nvidia-driver" "${selected_driver} (${timestamp})"
        log_success "NVIDIA Driver '${selected_driver}' installed successfully."
        return 0
    else
        log_error "Failed to install '${selected_driver}'."
        return 1
    fi
}
