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
SYSTEM_DIR="${SCRIPT_DIR}/script/system"

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

# 백엔드 로직 스크립트 로드
scripts_to_load=(
    "install/conda.sh" "install/nvidia_driver.sh" "install/cuda_toolkit.sh"
    "install/cudnn_library.sh" "install/vscode.sh" "install/docker.sh"
    "install/ros2.sh" "install/opencv.sh"
    "system/02_storage.sh" "system/02_network.sh" "system/02_account.sh"
)
for script in "${scripts_to_load[@]}"; do
    [[ -f "${SCRIPT_DIR}/script/${script}" ]] && source "${SCRIPT_DIR}/script/${script}"
done

# -----------------------------------------------------------------------------
# @description 프로필 기반 자동 설치 엔진
# -----------------------------------------------------------------------------
run_provisioning() {
    log_info "========================================================================"
    log_info " Starting ASAP Automatic Provisioning (Profile-Based)"
    log_info " Config Source: $CONFIG_FILE"
    log_info " State Target : $G_STATE_FILE"
    log_info "========================================================================"

    # --- 1. 표준 패키지 설치 ([PACKAGES_LIST]) ---
    log_info ">>> Processing [PACKAGES_LIST]..."
    local pkgs_to_install=()
    local pkg_keys; pkg_keys=$(get_config_keys "PACKAGES_LIST" "$CONFIG_FILE")
    
    if [[ -n "$pkg_keys" ]]; then
        while read -r pkg; do
            [[ -z "$pkg" ]] && continue
            local ver; ver=$(get_config_value "$CONFIG_FILE" "PACKAGES_LIST" "$pkg")
            if [[ -n "$ver" ]]; then
                pkgs_to_install+=("${pkg}=${ver}")
            else
                pkgs_to_install+=("${pkg}")
            fi
        done <<< "$pkg_keys"
    fi

    if [[ ${#pkgs_to_install[@]} -gt 0 ]]; then
        log_info "Syncing ${#pkgs_to_install[@]} standard packages..."
        sync_package "PACKAGES_LIST" "Auto Provisioning" "${pkgs_to_install[@]}"
    fi

    # --- 2. 드라이버 설치 ([DRIVER_LIST]) ---
    log_info ">>> Processing [DRIVER_LIST]..."
    local driver_keys; driver_keys=$(get_config_keys "DRIVER_LIST" "$CONFIG_FILE")
    if [[ -n "$driver_keys" ]]; then
        while read -r driver; do
            [[ -z "$driver" ]] && continue
            local ver; ver=$(get_config_value "$CONFIG_FILE" "DRIVER_LIST" "$driver")
            local full_driver_pkg="${driver}"
            [[ -n "$ver" ]] && full_driver_pkg="${driver}-${ver}"
            
            if ! is_installed_nvidia_driver; then
                log_info "Installing driver: ${full_driver_pkg}"
                install_nvidia_driver_logic "${full_driver_pkg}"
            else
                log_info "Driver '${driver}' is already satisfied. Skipping."
            fi
        done <<< "$driver_keys"
    fi

    # --- 3. 애플리케이션 프로필 처리 ---
    log_info ">>> Processing Application Profiles..."

    # [CONDA_PROFILE]
    if grep -q "\[CONDA_PROFILE\]" "$CONFIG_FILE"; then
        if is_installed_conda; then
            log_info "Conda is already installed. Skipping."
        else
            log_info "[PROVISION] Applying [CONDA_PROFILE]..."
            local mode; mode=$(get_config_value "$CONFIG_FILE" "CONDA_PROFILE" "mode")
            local type; type=$(get_config_value "$CONFIG_FILE" "CONDA_PROFILE" "type")
            install_conda_logic "${mode:-user}" "${type:-miniconda}"
        fi
    fi

    # [VSCODE_PROFILE]
    if grep -q "\[VSCODE_PROFILE\]" "$CONFIG_FILE"; then
        if is_installed_vscode; then
            log_info "Visual Studio Code is already installed. Skipping."
        else
            log_info "[PROVISION] Applying [VSCODE_PROFILE]..."
            install_vscode_logic
        fi
    fi

    # [CUDA_TOOLKIT_PROFILE]
    if grep -q "\[CUDA_TOOLKIT_PROFILE\]" "$CONFIG_FILE"; then
        local ver; ver=$(get_config_value "$CONFIG_FILE" "CUDA_TOOLKIT_PROFILE" "version")
        local arch; arch=$(get_config_value "$CONFIG_FILE" "CUDA_TOOLKIT_PROFILE" "arch")
        if [[ -n "$ver" ]]; then
            log_info "[PROVISION] Applying [CUDA_TOOLKIT_PROFILE] (Version: $ver)..."
            install_cuda_toolkit_logic "INSTALL" "$ver" "$arch"
        fi
    fi

    # [CUDNN_LIBRARY_PROFILE]
    if grep -q "\[CUDNN_LIBRARY_PROFILE\]" "$CONFIG_FILE"; then
        if is_installed_cudnn_library; then
            log_info "cuDNN Library is already installed. Skipping."
        else
            log_info "[PROVISION] Applying [CUDNN_LIBRARY_PROFILE]..."
            local ver; ver=$(get_config_value "$CONFIG_FILE" "CUDNN_LIBRARY_PROFILE" "version")
            [[ -n "$ver" ]] && install_cudnn_library_logic "$ver"
        fi
    fi

    # [DOCKER_PROFILE]
    if grep -q "\[DOCKER_PROFILE\]" "$CONFIG_FILE"; then
        if is_installed_docker; then
            log_info "Docker is already installed. Skipping."
        else
            log_info "[PROVISION] Applying [DOCKER_PROFILE]..."
            install_docker_logic
        fi
    fi

    # [ROS2_PROFILE]
    if grep -q "\[ROS2_PROFILE\]" "$CONFIG_FILE"; then
        if is_installed_ros2; then
            log_info "ROS2 is already installed. Skipping."
        else
            log_info "[PROVISION] Applying [ROS2_PROFILE]..."
            install_ros2_logic
        fi
    fi

    # [OPENCV_PROFILE]
    if grep -q "\[OPENCV_PROFILE\]" "$CONFIG_FILE"; then
        log_info "[PROVISION] Applying [OPENCV_PROFILE]..."
        local ver; ver=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "version")
        local cuda; cuda=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "with_cuda")
        local arch; arch=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "gpu_arch")
        local jobs; jobs=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "jobs")
        local prefix; prefix=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "prefix")
        local bpath; bpath=$(get_config_value "$CONFIG_FILE" "OPENCV_PROFILE" "build_path")
        
        install_opencv_logic "${ver:-4.10.0}" "${cuda:-OFF}" "${arch}" "${jobs}" "${prefix}" "${bpath:-/tmp/opencv_build}"
    fi

    # --- 4. 저장소 프로필 처리 (STORAGE_PROFILE_*) ---
    log_info ">>> Processing Storage Profiles..."
    local storage_profiles; storage_keys=$(get_profile_list "$CONFIG_FILE" "STORAGE_PROFILE_")
    if [[ -n "$storage_keys" ]]; then
        while read -r profile; do
            [[ -z "$profile" ]] && continue
            log_info "[PROVISION] Applying storage profile: $profile"
            
            declare -A profile_data
            parse_config_to_array "profile_data" < <(get_config_section "$CONFIG_FILE" "$profile")
            profile_data["_CONF_FILE"]="$CONFIG_FILE"
            
            apply_storage_profile "$profile" "profile_data"
        done <<< "$storage_keys"
    fi

    # --- 5. 네트워크 프로필 처리 (NETWORK_PROFILE_*) ---
    log_info ">>> Processing Network Profiles..."
    local network_profiles; network_keys=$(get_profile_list "$CONFIG_FILE" "NETWORK_PROFILE_")
    if [[ -n "$network_keys" ]]; then
        while read -r profile; do
            [[ -z "$profile" ]] && continue
            log_info "[PROVISION] Applying network profile: $profile"
            # TODO: 백엔드에 network_profile_logic 추가 필요
        done <<< "$network_keys"
    fi

    log_info "========================================================================"
    log_success " ASAP Provisioning Completed Successfully."
    log_info "========================================================================"
}

# 루트 권한 확인
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root (or with sudo)."
   exit 1
fi

# 실행
run_provisioning
