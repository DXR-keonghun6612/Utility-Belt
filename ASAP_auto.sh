#!/bin/bash
# ==============================================================================
# 파일명: ASAP_auto.sh
# 설명: 설정 파일(config.conf)의 프로필 섹션을 기반으로 한 무인 자동 설치 스크립트
# 사용법: sudo ./ASAP_auto.sh [config_file_path]
# ==============================================================================

# 1. 자동화 모드 강제 설정 (UI 팝업 차단)
export G_INTERACTIVE="false"

# 2. 초기화 로직
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
CORE_DIR="${SCRIPT_DIR}/script/core"
INSTALL_DIR="${SCRIPT_DIR}/script/install"

if [[ -f "${CORE_DIR}/core.sh" ]]; then
    source "${CORE_DIR}/core.sh"
else
    echo "[FATAL] Core loader not found."
    exit 1
fi

# 설정 파일 경로 결정 및 초기화 (is_interactive=false 전달)
CONFIG_PATH="${1:-${SCRIPT_DIR}/conf/config.conf}"
TEMPLATE_PATH="${SCRIPT_DIR}/template/config.conf"

if ! load_core_libraries "${SCRIPT_DIR}" "${CONFIG_PATH}" "${TEMPLATE_PATH}" "false"; then
    echo "[FATAL] Library initialization failed."
    exit 1
fi

# 설치 로직 및 확인 함수 스크립트 로드
install_scripts=("conda.sh" "nvidia_driver.sh" "cuda_toolkit.sh" "cudnn_library.sh" "vscode.sh" "docker.sh" "ros2.sh" "opencv.sh")
for script in "${install_scripts[@]}"; do
    [[ -f "${INSTALL_DIR}/${script}" ]] && source "${INSTALL_DIR}/${script}"
done

# -----------------------------------------------------------------------------
# @description 프로필 기반 자동 설치 엔진
# -----------------------------------------------------------------------------
run_provisioning() {
    echo "========================================================================"
    echo " Starting ASAP Automatic Provisioning (Profile-Based)"
    echo " Config: $CONFIG_FILE"
    echo "========================================================================"

    # --- 1. 일반 패키지 설치 ([PACKAGES_LIST] 섹션) ---
    echo ">>> Checking [PACKAGES_LIST] for standard packages..."
    local pkg_section="PACKAGES_LIST"
    local pkgs_to_install=()
    
    local pkg_keys_output
    if pkg_keys_output=$(get_config_keys "$pkg_section" "$CONFIG_FILE"); then
        while read -r pkg; do
            [[ -n "$pkg" ]] && pkgs_to_install+=("$pkg")
        done <<< "$pkg_keys_output"
    fi

    if [[ ${#pkgs_to_install[@]} -gt 0 ]]; then
        echo "[PROVISION] Syncing ${#pkgs_to_install[@]} packages from $pkg_section..."
        sync_package "$pkg_section" "Auto Provisioning" "${pkgs_to_install[@]}"
    fi

    # --- 2. 애플리케이션 프로필 처리 ---
    echo -e "\n>>> Checking Application Profiles..."

    # -------------------------------------------------------------------------
    # [CONDA_PROFILE]
    # -------------------------------------------------------------------------
    if grep -q "\[CONDA_PROFILE\]" "$CONFIG_FILE"; then
        if is_installed_conda; then
            echo "[INFO] Conda is already installed. Skipping."
        else
            echo "[PROVISION] Processing [CONDA_PROFILE]..."
            local mode=$(get_config_value "$CONFIG_FILE" "CONDA_PROFILE" "mode")
            local type=$(get_config_value "$CONFIG_FILE" "CONDA_PROFILE" "type")
            install_conda_logic "${mode:-user}" "${type:-miniconda}"
        fi
    fi

    # -------------------------------------------------------------------------
    # [VSCODE_PROFILE]
    # -------------------------------------------------------------------------
    if grep -q "\[VSCODE_PROFILE\]" "$CONFIG_FILE"; then
        if is_installed_vscode; then
            echo "[INFO] Visual Studio Code is already installed. Skipping."
        else
            echo "[PROVISION] Processing [VSCODE_PROFILE]..."
            install_vscode_logic
        fi
    fi

    # -------------------------------------------------------------------------
    # [NVIDIA_DRIVER_PROFILE]
    # -------------------------------------------------------------------------
    if grep -q "\[NVIDIA_DRIVER_PROFILE\]" "$CONFIG_FILE"; then
        if is_installed_nvidia_driver; then
            echo "[INFO] NVIDIA Driver is already installed. Skipping."
        else
            echo "[PROVISION] Processing [NVIDIA_DRIVER_PROFILE]..."
            local driver=$(get_config_value "$CONFIG_FILE" "NVIDIA_DRIVER_PROFILE" "driver_version")
            [[ -n "$driver" ]] && install_nvidia_driver_logic "$driver"
        fi
    fi

    # -------------------------------------------------------------------------
    # [CUDA_TOOLKIT_PROFILE]
    # -------------------------------------------------------------------------
    if grep -q "\[CUDA_TOOLKIT_PROFILE\]" "$CONFIG_FILE"; then
        echo "[PROVISION] Processing [CUDA_TOOLKIT_PROFILE]..."
        local ver=$(get_config_value "$CONFIG_FILE" "CUDA_TOOLKIT_PROFILE" "version")
        local arch=$(get_config_value "$CONFIG_FILE" "CUDA_TOOLKIT_PROFILE" "arch")
        
        # CUDA는 여러 버전이 있을 수 있으므로 logic 내부의 switch/install 로직에 맡김
        if [[ -n "$ver" ]]; then
            install_cuda_toolkit_logic "INSTALL" "$ver" "$arch"
        fi
    fi

    # -------------------------------------------------------------------------
    # [CUDNN_LIBRARY_PROFILE]
    # -------------------------------------------------------------------------
    if grep -q "\[CUDNN_LIBRARY_PROFILE\]" "$CONFIG_FILE"; then
        if is_installed_cudnn_library; then
            echo "[INFO] cuDNN Library is already installed. Skipping."
        else
            echo "[PROVISION] Processing [CUDNN_LIBRARY_PROFILE]..."
            local ver=$(get_config_value "$CONFIG_FILE" "CUDNN_LIBRARY_PROFILE" "version")
            [[ -n "$ver" ]] && install_cudnn_library_logic "$ver"
        fi
    fi

    # -------------------------------------------------------------------------
    # [DOCKER_PROFILE]
    # -------------------------------------------------------------------------
    if grep -q "\[DOCKER_PROFILE\]" "$CONFIG_FILE"; then
        if is_installed_docker; then
            echo "[INFO] Docker is already installed. Skipping."
        else
            echo "[PROVISION] Processing [DOCKER_PROFILE]..."
            install_docker_logic
        fi
    fi

    # -------------------------------------------------------------------------
    # [ROS2_PROFILE]
    # -------------------------------------------------------------------------
    if grep -q "\[ROS2_PROFILE\]" "$CONFIG_FILE"; then
        if is_installed_ros2; then
            echo "[INFO] ROS2 is already installed. Skipping."
        else
            echo "[PROVISION] Processing [ROS2_PROFILE]..."
            install_ros2_logic
        fi
    fi

    # -------------------------------------------------------------------------
    # [OPENCV_PROFILE]
    # -------------------------------------------------------------------------
    if grep -q "\[OPENCV_PROFILE\]" "$CONFIG_FILE"; then
        # OpenCV는 시스템 설치 여부(pkg-config)와 상관없이 
        # 사용자가 프로필을 명시했다면 빌드 경로를 체크하여 설치 로직을 태움 (reinstall/update 대응)
        echo "[PROVISION] Processing [OPENCV_PROFILE]..."
        local ver=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "version")
        local cuda=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "with_cuda")
        local arch=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "gpu_arch")
        local jobs=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "jobs")
        local prefix=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "prefix")
        local bpath=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "build_path")
        
        install_opencv_logic "${ver:-4.10.0}" "${cuda:-OFF}" "${arch}" "${jobs}" "${prefix}" "${bpath:-/tmp/opencv_build}"
    fi

    echo "========================================================================"
    echo " Provisioning Completed"
    echo "========================================================================"
}

# 실행
run_provisioning