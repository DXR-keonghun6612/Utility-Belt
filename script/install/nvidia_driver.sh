#!/bin/bash
# ==============================================================================
# 파일명: nvidia_driver.sh
# 설명: NVIDIA 드라이버 확인 및 설치 로직
# ==============================================================================

# -----------------------------------------------------------------------------
# @description NVIDIA 드라이버 설치 여부 확인
# @return 0: 설치됨, 1: 설치 안 됨
# -----------------------------------------------------------------------------
is_installed_nvidia_driver() {
    # 1. nvidia-smi 명령어가 있으면 설치된 것으로 간주
    if command -v nvidia-smi &> /dev/null; then
        return 0
    fi

    # 2. 패키지 매니저(dpkg)를 통해 확인
    if dpkg-query -W -f='${Status}' 'nvidia-driver-*' 2>/dev/null | grep -q 'install ok installed'; then
        return 0
    fi

    return 1
}

# -----------------------------------------------------------------------------
# @description 설치 가능한 NVIDIA 드라이버 목록을 반환합니다.
#           - 내부적으로 ubuntu-drivers-common 패키지가 필요합니다.
# @return 0: 성공, 1: 지원하지 않는 시스템 또는 드라이버 없음
# @stdout "driver_name recommended" 형식의 목록
# -----------------------------------------------------------------------------
get_available_nvidia_drivers() {
    # 1. 배포판 의존성 확인
    if [[ $(get_package_manager_type) != "dpkg" ]]; then
        echo "[ERROR] 'ubuntu-drivers' utility is only supported on Debian/Ubuntu-based systems." >&2
        return 1
    fi

    # 2. 필수 패키지 확인 및 설치 보장
    ensure_packages_installed "SYSTEM_TOOLS" "ubuntu-drivers-common" || return $?

    # 3. 드라이버 목록 추출 및 정렬
    local drivers
    drivers=$(ubuntu-drivers list 2>/dev/null | awk \
        '/nvidia-driver-[0-9]+/ {
            sub(/,$/, "", $1);
            rec = ($3 == "(recommended)") ? "(recommended)" : "";
            print $1, rec;
        }
    ' | sort -Vr)

    if [[ -z "$drivers" ]]; then
        return 1
    fi

    echo "$drivers"
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
        echo "[ERROR] No driver name provided." >&2
        return 1
    fi

    # 0. 필수 의존성 확인
    ensure_packages_installed "SYSTEM_TOOLS" "NVIDIA Driver Utils" "ubuntu-drivers-common" || return 1

    # 1. 배포판 의존성 확인
    if [[ $(get_package_manager_type) != "dpkg" ]]; then
        echo "[ERROR] NVIDIA driver cleanup logic is currently only supported on Debian/Ubuntu-based systems." >&2
        return 1
    fi

    # 2. 기존 설치된 다른 NVIDIA 드라이버 감지
    echo "[INFO] Searching for previously installed NVIDIA drivers..."
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
            echo "[ERROR] Root privileges (or sudo) are required to remove conflicting drivers." >&2
            return 5
        fi
        echo "[INFO] Removing conflicting drivers: ${drivers_to_uninstall[*]}"
        ${_PKG_REMOVE_CMD} "${drivers_to_uninstall[@]}"
        if [[ -n "$_PKG_AUTOREMOVE_CMD" ]]; then
            ${_PKG_AUTOREMOVE_CMD}
        fi
    fi

    # 4. 새 드라이버 설치
    echo "[INFO] Installing selected driver: ${selected_driver}"
    if ensure_packages_installed "DRIVER_LIST" "${selected_driver}"; then
        echo "[SUCCESS] NVIDIA Driver '${selected_driver}' installed successfully."
        return 0
    else
        echo "[ERROR] Failed to install '${selected_driver}'." >&2
        return 1
    fi
}
