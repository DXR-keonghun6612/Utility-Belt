#!/bin/bash
# ==============================================================================
# 파일명: ros2.sh
# 설명: ROS 2 (Robot Operating System 2) 설치 로직
# 가이드: https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html
# ==============================================================================

# -----------------------------------------------------------------------------
# @description ROS 2 설치 여부 확인 및 설정 동기화
# @return 0: 설치됨, 1: 설치 안 됨
# -----------------------------------------------------------------------------
is_installed_ros2() {
    local installed=1
    local distro=""

    # 1. /opt/ros 디렉토리 하위 확인
    if ls /opt/ros/*/bin/ros2 &> /dev/null; then
        installed=0
        # 설치된 distro 이름 추출 (가장 높은 버전 우선)
        distro=$(ls /opt/ros/ 2>/dev/null | grep -vE 'setup\.' | sort -Vr | head -n 1)
    elif command -v ros2 &> /dev/null; then
        installed=0
        # TODO: ros2 명령어로 distro 확인 로직 보강 가능
    fi

    # [Sync Config] 설치 상태 동기화
    if [[ -n "${G_STATE_FILE}" ]]; then
        if [[ $installed -eq 0 ]]; then
            local conf_key="ros2"
            [[ -n "$distro" ]] && conf_key="ros2-${distro}"
            
            local current_val
            current_val=$(get_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "${conf_key}")
            if [[ -z "${current_val}" ]]; then
                local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
                add_config_section "${G_STATE_FILE}" "APPLICATION_LIST"
                set_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "${conf_key}" "${timestamp}"
            fi
        else
            # ROS 2 관련 모든 기록 삭제
            delete_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "ros2"
            delete_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "ros2-humble"
            delete_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "ros2-foxy"
            delete_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "ros2-jazzy"
        fi
    fi

    return $installed
}

# -----------------------------------------------------------------------------
# @description Ubuntu 버전에 맞는 ROS 2 Distro 이름을 반환합니다.
# -----------------------------------------------------------------------------
_get_ros2_distro() {
    source /etc/os-release
    case "${VERSION_ID}" in
        "24.04") echo "jazzy" ;;
        "22.04") echo "humble" ;;
        "20.04") echo "foxy" ;;
        *) echo "unknown" ;;
    esac
}

# -----------------------------------------------------------------------------
# @description ROS 2 설치 로직
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
install_ros2_logic() {
    source /etc/os-release
    if [[ "${ID}" != "ubuntu" ]]; then
        log_error "ROS 2 installation script currently supports Ubuntu only."
        return 1
    fi

    local distro
    distro=$(_get_ros2_distro)
    if [[ "${distro}" == "unknown" ]]; then
        log_error "Unsupported Ubuntu version for ROS 2 automatic installation: ${VERSION_ID}"
        return 1
    fi

    log_info "Setting up locales and essential dependencies..."
    ensure_packages_installed "SYSTEM_TOOLS" "ROS 2 Dependencies" "locales" "curl" "gnupg2" "lsb-release" "software-properties-common" || return 1
    
    ${G_SUDO_PREFIX} locale-gen en_US en_US.UTF-8 > /dev/null
    ${G_SUDO_PREFIX} update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 > /dev/null
    export LANG=en_US.UTF-8

    log_info "Enabling Ubuntu Universe repository..."
    ${G_SUDO_PREFIX} add-apt-repository -y universe > /dev/null 2>&1

    log_info "Setting up ROS 2 APT repository for ${distro}..."
    local gpg_key_url="https://raw.githubusercontent.com/ros/rosdistro/master/ros.key"
    local gpg_keyring="/usr/share/keyrings/ros-archive-keyring.gpg"
    
    if ! install_apt_gpg_key "${gpg_key_url}" "${gpg_keyring}" "true"; then
        return 1
    fi

    local arch
    arch=$(dpkg --print-architecture)
    local repo_line="deb [arch=${arch} signed-by=${gpg_keyring}] http://packages.ros.org/ros2/ubuntu ${VERSION_CODENAME} main"
    
    if ! setup_apt_repository "ros2" "${repo_line}"; then
        return 1
    fi

    log_info "Installing ROS 2 ${distro} (desktop version)..."
    local ros_pkg="ros-${distro}-desktop"
    
    if sync_package "APPLICATION_LIST" "ros2-${distro}" "${ros_pkg}"; then
        log_success "ROS 2 ${distro} installed successfully."
        return 0
    else
        log_error "Failed to install ROS 2 ${distro}."
        return 1
    fi
}
