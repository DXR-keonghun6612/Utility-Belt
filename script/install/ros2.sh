#!/bin/bash
# ==============================================================================
# 파일명: ros2.sh
# 설명: ROS 2 (Robot Operating System 2) 설치 로직
# 가이드: https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html
# ==============================================================================

# -----------------------------------------------------------------------------
# @description ROS 2 설치 여부 확인
# @return 0: 설치됨, 1: 설치 안 됨
# -----------------------------------------------------------------------------
is_installed_ros2() {
    # /opt/ros 디렉토리 하위에 ros2 관련 폴더가 있는지 확인하거나 ros2 명령어로 확인
    if command -v ros2 &> /dev/null; then
        return 0
    fi
    
    if ls /opt/ros/*/bin/ros2 &> /dev/null; then
        return 0
    fi

    return 1
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
    # 0. OS 확인
    source /etc/os-release
    if [[ "${ID}" != "ubuntu" ]]; then
        echo "[ERROR] ROS 2 installation script currently supports Ubuntu only." >&2
        return 1
    fi

    local distro
    distro=$(_get_ros2_distro)
    if [[ "${distro}" == "unknown" ]]; then
        echo "[ERROR] Unsupported Ubuntu version for ROS 2 automatic installation: ${VERSION_ID}" >&2
        return 1
    fi

    # 1. 필수 의존성 및 로케일 설정
    echo "[INFO] Setting up locales and essential dependencies..."
    ensure_packages_installed "SYSTEM_TOOLS" "ROS 2 Dependencies" "locales" "curl" "gnupg2" "lsb-release" "software-properties-common" || return 1
    
    # 로케일 설정 (UTF-8)
    ${G_SUDO_PREFIX} locale-gen en_US en_US.UTF-8 > /dev/null
    ${G_SUDO_PREFIX} update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 > /dev/null
    export LANG=en_US.UTF-8

    # 2. Universe 저장소 활성화
    echo "[INFO] Enabling Ubuntu Universe repository..."
    ${G_SUDO_PREFIX} add-apt-repository -y universe > /dev/null 2>&1

    # 3. ROS 2 GPG 키 및 저장소 설정
    echo "[INFO] Setting up ROS 2 APT repository for ${distro}..."
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

    # 4. ROS 2 패키지 설치 (Desktop 버전 기본)
    echo "[INFO] Installing ROS 2 ${distro} (desktop version)..."
    local ros_pkg="ros-${distro}-desktop"
    
    if sync_package "APPLICATION_LIST" "ros2-${distro}" "${ros_pkg}"; then
        echo "[SUCCESS] ROS 2 ${distro} installed successfully."
        
        # 5. 환경 변수 안내
        echo "========================================================"
        echo " ROS 2 ${distro} Installation Complete."
        echo " To start using ROS 2, source the setup script:"
        echo "   source /opt/ros/${distro}/setup.bash"
        echo " To automate this, add it to your .bashrc:"
        echo "   echo "source /opt/ros/${distro}/setup.bash" >> ~/.bashrc"
        echo "========================================================"
        
        return 0
    else
        echo "[ERROR] Failed to install ROS 2 ${distro}." >&2
        return 1
    fi
}
