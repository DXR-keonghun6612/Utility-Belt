#!/bin/bash
# ==============================================================================
# 파일명: ASAP_auto.sh
# 설명: 설정 파일(config.conf)에 기반한 무인 자동 설치(Headless Provisioning) 스크립트
# 사용법: sudo ./ASAP_auto.sh [config_file_path]
# ==============================================================================

# 1. 자동화 모드 강제 설정
export G_INTERACTIVE="false"

# 2. 초기화 로직 (ASAP.sh의 로직 공유)
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
CORE_DIR="${SCRIPT_DIR}/script/core"
INSTALL_DIR="${SCRIPT_DIR}/script/install"
SYSTEM_DIR="${SCRIPT_DIR}/script/system"

if [[ -f "${CORE_DIR}/core.sh" ]]; then
    source "${CORE_DIR}/core.sh"
else
    echo "[FATAL] Core loader not found."
    exit 1
fi

# 설정 파일 경로 결정
CONFIG_PATH="${1:-${SCRIPT_DIR}/conf/config.conf}"
TEMPLATE_PATH="${SCRIPT_DIR}/template/config.conf"

if ! load_core_libraries "${SCRIPT_DIR}" "${CONFIG_PATH}" "${TEMPLATE_PATH}"; then
    echo "[FATAL] Library initialization failed."
    exit 1
fi

# 설치 관련 스크립트 소싱 (로직 함수들을 메모리에 로드)
install_scripts=("conda.sh" "nvidia_driver.sh" "cuda_toolkit.sh" "cudnn_library.sh" "vscode.sh" "docker.sh" "ros2.sh" "opencv.sh")
for script in "${install_scripts[@]}"; do
    [[ -f "${INSTALL_DIR}/${script}" ]] && source "${INSTALL_DIR}/${script}"
done

# -----------------------------------------------------------------------------
# @description 자동 설치 엔진 로직
# -----------------------------------------------------------------------------
run_provisioning() {
    echo "========================================================================"
    echo " Starting ASAP Automatic Provisioning"
    echo " Config: $CONFIG_FILE"
    echo "========================================================================"

    # --- 1. 일반 패키지 설치 ([PACKAGES_LIST] 섹션) ---
    echo ">>> Checking [PACKAGES_LIST] for standard packages..."
    local pkg_section="PACKAGES_LIST"
    local pkgs_to_install=()
    
    local pkg_keys
    if command -v get_config_keys &>/dev/null; then
        pkg_keys=$(get_config_keys "$pkg_section" "$CONFIG_FILE")
    else
        pkg_keys=$(sed -n "/^\[$pkg_section\]/,/^\[/p" "$CONFIG_FILE" | grep -E '^[a-zA-Z0-9_-]+=' | cut -d= -f1 | tr -d ' ')
    fi

    for pkg in $pkg_keys; do
        # 값이 비어있지 않더라도 sync_package가 중복 설치를 방지하므로 
        # 설정에 존재하는 모든 키를 대상으로 실행 (상태 동기화 포함)
        pkgs_to_install+=("$pkg")
    done

    if [[ ${#pkgs_to_install[@]} -gt 0 ]]; then
        echo "[PROVISION] Syncing ${#pkgs_to_install[@]} packages from $pkg_section..."
        # sync_package <section> <comment> <pkgs...>
        sync_package "$pkg_section" "Auto Provisioning" "${pkgs_to_install[@]}"
    fi

    # --- 2. 애플리케이션 설치 ([AUTO_INSTALL] 섹션) ---
    echo -e "\n>>> Checking [AUTO_INSTALL] for specialized applications..."
    declare -A SCRIPT_MAP=(
        ["conda.sh"]="Conda|conda|APPLICATION_LIST"
        ["vscode.sh"]="VS Code|code|APPLICATION_LIST"
        ["nvidia_driver.sh"]="NVIDIA Driver|nvidia-driver|DRIVER_LIST"
        ["cuda_toolkit.sh"]="CUDA Toolkit|cuda-toolkit|APPLICATION_LIST"
        ["cudnn_library.sh"]="cuDNN Library|cudnn-library|APPLICATION_LIST"
        ["docker.sh"]="Docker|docker|APPLICATION_LIST"
        ["ros2.sh"]="ROS 2|ros2|APPLICATION_LIST"
        ["opencv.sh"]="OpenCV|opencv|APPLICATION_LIST"
    )
    
    declare -A NAME_TO_LOGIC=(
        ["Conda"]="install_conda_logic"
        ["VS Code"]="install_vscode_logic"
        ["NVIDIA Driver"]="install_nvidia_driver_logic"
        ["CUDA Toolkit"]="install_cuda_toolkit_logic"
        ["cuDNN Library"]="install_cudnn_library_logic"
        ["Docker"]="install_docker_logic"
        ["ROS 2"]="install_ros2_logic"
        ["OpenCV"]="install_opencv_logic"
    )

    local section="AUTO_INSTALL"
    local keys_raw
    if command -v get_config_keys &>/dev/null; then
        keys_raw=$(get_config_keys "$section" "$CONFIG_FILE")
    else
        keys_raw=$(sed -n "/^\[$section\]/,/^\[/p" "$CONFIG_FILE" | grep -E '^[a-zA-Z0-9_-]+=' | cut -d= -f1 | tr -d ' ')
    fi

    [[ -z "$keys_raw" ]] && { echo "[INFO] No items in [$section]."; exit 0; }

    for key in $keys_raw; do
        local value=$(get_config_value "$CONFIG_FILE" "$section" "$key")
        [[ -z "$value" || "$value" == "no" || "$value" == "false" ]] && continue

        local target_name=""
        for script in "${!SCRIPT_MAP[@]}"; do
            IFS='|' read -r name conf_key conf_section <<< "${SCRIPT_MAP[$script]}"
            [[ "$conf_key" == "$key" ]] && { target_name="$name"; break; }
        done

        [[ -z "$target_name" ]] && continue

        echo "------------------------------------------------------------------------"
        echo "[PROVISION] Installing: $target_name"
        
        local args=()
        if [[ "$value" != "yes" && "$value" != "true" ]]; then
            IFS=':, ' read -r -a args <<< "$value"
        fi

        local logic_func="${NAME_TO_LOGIC[$target_name]}"
        if [[ -n "$logic_func" && "$(type -t $logic_func)" == "function" ]]; then
            "$logic_func" "${args[@]}"
        fi
    done

    echo "========================================================================"
    echo " Provisioning Completed"
    echo "========================================================================"
}

# 실행
run_provisioning
