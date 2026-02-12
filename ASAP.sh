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

    # --- 2. 모듈 초기화 (System, User, Install, UI) ---
    # 각 디렉토리의 init.sh를 로드하고 초기화 함수를 호출합니다.
    
    # System 모듈 로드
    if [[ -f "${SYSTEM_DIR}/init.sh" ]]; then
        source "${SYSTEM_DIR}/init.sh"
        initialize_system_modules
    fi

    # User 모듈 로드
    if [[ -f "${USER_MODULE_DIR}/init.sh" ]]; then
        source "${USER_MODULE_DIR}/init.sh"
        initialize_user_modules
    fi

    # Install 모듈 로드
    if [[ -f "${INSTALL_DIR}/init.sh" ]]; then
        source "${INSTALL_DIR}/init.sh"
        initialize_install_modules
    fi

    # UI 프로세스 로드
    if [[ -f "${UI_DIR}/init.sh" ]]; then
        source "${UI_DIR}/init.sh"
        initialize_ui_processes
    fi
}

# ==============================================================================
# --- 서브 메뉴 UI 함수 ---
# ==============================================================================

## @description '소프트웨어 설치' 관련 서브 메뉴를 표시합니다.
ui_menu_installation() {
    while true; do
        local menu_options=()
        local idx=1

        # 1. 시스템 패키지 (항상 노출, 내부에서 OS별 처리)
        menu_options+=("${idx}" "System Packages & Libraries (Native/Build)")
        local cmd_1="ui_menu_system_packages"
        ((idx++))

        # 2. 하드웨어 스택 (지원 여부 확인)
        local cmd_2=""
        if is_supported_nvidia_driver || is_supported_cuda_toolkit; then
            menu_options+=("${idx}" "Hardware Stacks & Drivers (NVIDIA/GPU)")
            cmd_2="ui_install_gpu_stack"
            ((idx++))
        fi

        # 3. 일반 애플리케이션 (항상 노출)
        menu_options+=("${idx}" "General Applications (Docker/Conda/etc)")
        local cmd_3="ui_install_application"
        ((idx++))

        # 4. 커스텀 서비스
        menu_options+=("${idx}" "Manage Custom Services")
        local cmd_4="ui_manage_custom_services"
        ((idx++))

        menu_options+=("0" "Back to Main Menu")

        local choice
        choice=$(ui_create_menu "Main Menu > Software Installation" "Software Installation" "Select a category:" \
            "18" "65" "10" "${menu_options[@]}")

        case "${choice}" in
            1) ${cmd_1} ;;
            2) [[ -n "${cmd_2}" ]] && ${cmd_2} || ${cmd_3} ;;
            3) [[ -n "${cmd_2}" ]] && ${cmd_3} || ${cmd_4} ;;
            4) [[ -n "${cmd_2}" ]] && ${cmd_4} ;;
            0 | CANCEL) break ;;
        esac
    done
}

## @description 시스템 패키지 및 빌드 라이브러리 설치 서브 메뉴
ui_menu_system_packages() {
    while true; do
        local choice
        choice=$(ui_create_menu "Software Installation > System Packages" "Packages & Libraries" "Select a task:" \
            "15" "60" "5" \
            "1" "Manage System Packages (Native)" \
            "2" "Install OpenCV (Build-based)" \
            "0" "Return to Category Selection")

        case "${choice}" in
            1) ui_package_management "${CONFIG_FILE}" ;;
            2) ui_install_opencv ;;
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
            1) ui_account_management ;; 
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

    # Check permissions using G_IS_ROOT defined in base/init.sh
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
