#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/init.sh
# 설명: 설치 관련 모든 UI(패키지, GPU, 소프트웨어, 서비스)를 통합 관리하는 메인 메뉴.
# ==============================================================================

ui_install_main_menu() {
    while true; do
        local choice
        choice=$(ui_create_menu "Installation & Setup" "Main Installation Menu" \
            "Select an installation category to manage:" 20 70 10 \
            "SYSTEM"   "System Base Packages (apt/dpkg)" \
            "GPU"      "NVIDIA GPU Acceleration Stack" \
            "SOFTWARE" "General Application Software" \
            "SERVICE"  "Custom Services & Automations" \
            "BACK"     "Return to Main Menu")

        case "${choice}" in
            "SYSTEM")   ui_package_management "${CONFIG_FILE}" ;;
            "GPU")      ui_install_gpu_stack ;;
            "SOFTWARE") ui_install_software_main ;;
            "SERVICE")  ui_manage_custom_services ;;
            "BACK" | "CANCEL") break ;;
        esac
    done
}
