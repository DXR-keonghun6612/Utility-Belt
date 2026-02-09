#!/bin/bash
# ==============================================================================
# 파일명: pilot.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: dialog를 사용하여 서버의 주요 기능을 관리하는 메인 스크립트입니다.
#       계정, 스토리지, Samba 등 각 기능은 별도의 모듈로 분리되어 관리됩니다.
# ==============================================================================

# ==============================================================================
# --- 초기화 ---
# ==============================================================================
##
# @description UI에 필요한 패키지를 확인하고 설치함.
#
_initialize_script() {
    local custom_conf="$1"

    # 1. 스크립트 실행 위치(프로젝트 루트) 파악
    SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
    
    # 프로젝트 디렉토리 구조 정의
    CORE_DIR="${SCRIPT_DIR}/script/core"
    SYSTEM_DIR="${SCRIPT_DIR}/script/system"
    USER_MODULE_DIR="${SCRIPT_DIR}/script/user"
    INSTALL_DIR="${SCRIPT_DIR}/script/install"
    UI_DIR="${SCRIPT_DIR}/ui"

    # 2. Core 라이브러리 로드 및 초기화
    # core.sh는 load_core_libraries 함수만 정의함
    if [[ -f "${CORE_DIR}/core.sh" ]]; then
        source "${CORE_DIR}/core.sh"
    else
        echo "[FATAL] Failed to load core loader. '${CORE_DIR}/core.sh' not found."
        exit 1
    fi

    # 3. 설정 초기화 및 모듈 로드 통합 실행
    # 인자: [프로젝트 루트] [설정 파일 경로] [템플릿 파일 경로]
    local config_path="${custom_conf:-${SCRIPT_DIR}/conf/config.conf}"
    local template_path="${SCRIPT_DIR}/template/config.conf"
    
    if ! load_core_libraries "${SCRIPT_DIR}" "${config_path}" "${template_path}"; then
        echo "[FATAL] Core library initialization failed."
        exit 1
    fi

    # --- 2. System 모듈 로드 ---
    # 각 기능별 백엔드 로직을 로드합니다.
    local system_scripts=("02_account.sh" "02_samba.sh" "02_network.sh" "02_storage.sh" "02_system_moniter.sh")
    for script in "${system_scripts[@]}"; do
        if [[ -f "${SYSTEM_DIR}/${script}" ]]; then
            source "${SYSTEM_DIR}/${script}"
        else
            echo "[WARN] System script '${script}' not found in ${SYSTEM_DIR}."
        fi
    done

    # --- 2-1. User 모듈 로드 ---
    # 사용자 관련 유틸리티(Git, SSH 등)를 로드합니다.
    local user_scripts=("02_git.sh" "02_ssh.sh")
    for script in "${user_scripts[@]}"; do
        if [[ -f "${USER_MODULE_DIR}/${script}" ]]; then
            source "${USER_MODULE_DIR}/${script}"
        else
            echo "[WARN] User script '${script}' not found in ${USER_MODULE_DIR}."
        fi
    done

    # --- 3. Install 모듈 로드 ---
    # 설치 관련 로직을 로드합니다.
    local install_scripts=("conda.sh" "nvidia_driver.sh" "cuda_toolkit.sh" "cudnn_library.sh" "vscode.sh" "docker.sh" "ros2.sh" "opencv.sh")
    for script in "${install_scripts[@]}"; do
        if [[ -f "${INSTALL_DIR}/${script}" ]]; then
            source "${INSTALL_DIR}/${script}"
        fi
    done

    # --- 4. UI 모듈 로드 ---
    # 사용자 인터페이스 스크립트를 로드합니다.
    local ui_scripts=(
        "proc_account.sh" "proc_storage.sh" "proc_samba.sh" 
        "proc_network.sh" "proc_install_package.sh" 
        "proc_install_application.sh" "proc_custom_service.sh" 
        "proc_system_moniter.sh" 
        "proc_git.sh" "proc_ssh.sh"
    )
    for script in "${ui_scripts[@]}"; do
        if [[ -f "${UI_DIR}/${script}" ]]; then
            source "${UI_DIR}/${script}"
        else
            echo "[WARN] UI script '${script}' not found in ${UI_DIR}."
        fi
    done

    # --- 설정값 확인 ---
    USER_HOME_BASE=$(get_config_value "${CONFIG_FILE}" "USER" "USER_HOME_BASE")
    if [[ -z "${USER_HOME_BASE}" ]]; then
        # Dialog가 로드되었으므로 UI 메시지 박스 사용 가능
        if command -v ui_message_box &> /dev/null; then
            ui_message_box "Error: USER_HOME_BASE not found in ${CONFIG_FILE}. Please check the configuration." "Configuration Error" 8 70
        else
            echo "[ERROR] USER_HOME_BASE not found in ${CONFIG_FILE}."
        fi
        exit 1
    fi
}

# ==============================================================================
# --- 서브 메뉴 UI 함수 ---
# ==============================================================================

## @description '소프트웨어 설치' 관련 서브 메뉴를 표시합니다.
#  (기존 Provisioning에서 모니터링 제외, Custom Service 포함)
ui_menu_installation() {
    while true; do
        local choice
        choice=$(ui_create_menu "Main Menu > Software Installation" "Software Installation" "Select a task:" \
            "18" "60" "10" \
            "1" "Manage APT Packages" \
            "2" "Install Additional Applications" \
            "3" "Manage Custom Services" \
            "0" "Back to Main Menu")

        case "${choice}" in
            1) ui_package_management "${CONFIG_FILE}" ;;
            2) ui_install_application ;; 
            3) ui_manage_custom_services ;; 
            0 | CANCEL) break ;;
        esac
    done
}

## @description '시스템 설정' 관련 서브 메뉴를 표시합니다.
#  (기존 System Configuration에서 Custom Service 제외)
ui_menu_configuration() {
    while true; do
        local choice
        choice=$(ui_create_menu "Main Menu > System Configuration" "System Configuration" "Select a task:" \
            "18" "60" "10" \
            "1" "Account and Group Management" \
            "2" "Network Management" \
            "3" "Samba Management" \
            "0" "Back to Main Menu")

        case "${choice}" in
            1) ui_account_management "${USER_HOME_BASE}" ;; 
            2) ui_network_management ;; 
            3) ui_samba_management ;; 
            0 | CANCEL) break ;;
        esac
    done
}

# ==============================================================================
# --- 메인 실행 루프 ---
# ==============================================================================
main() {
    export G_INTERACTIVE="true"

    # Check permissions using G_IS_ROOT defined in 00_conf.sh
    if [[ "${G_IS_ROOT}" == "true" ]]; then
        # ==============================================================================
        # [Administrator Mode]
        # Full system management capabilities (Install, Config, Storage, etc.)
        # ==============================================================================
        while true; do
            local choice
            choice=$(ui_create_menu "Integrated Server Management (Admin)" "Admin Menu" "Select a category:" \
                "20" "65" "12" \
                "1" "System Monitoring" \
                "2" "Software Installation" \
                "3" "System Configuration" \
                "4" "Storage Management" \
                "0" "Exit")

            case "${choice}" in
                1) ui_system_monitor_menu ;; 
                2) ui_menu_installation ;; 
                3) ui_menu_configuration ;; 
                4) ui_storage_management "${CONFIG_FILE}" ;; 
                0 | CANCEL) break ;; 
            esac
        done
    else
        # ==============================================================================
        # [User Mode]
        # Limited capabilities for user-specific settings (No sudo required)
        # ==============================================================================
        while true; do
            local choice
            choice=$(ui_create_menu "Integrated Server Management (User)" "User Menu" "Select a task:" \
                "15" "60" "10" \
                "1" "Git Management" \
                "2" "SSH Management" \
                "0" "Exit")

            case "${choice}" in
                1) ui_git_management_menu ;;
                2) ui_ssh_management_menu ;;
                0 | CANCEL) break ;;
            esac
        done
    fi

    clear
    echo "Exiting the program."
}

# --- 초기화 실행 ---
# 스크립트가 처음 로드될 때 필요한 패키지 설치 여부를 확인.
_initialize_script "$1"
# --- 스크립트 시작 ---
main
