#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/software/ros2.sh
# 설명: ROS 2 설치를 위한 전용 UI.
# ==============================================================================

ui_install_ros2() {
    local status="(Not Installed)"
    is_installed_ros2 && status="(Installed)"

    local choice
    choice=$(ui_create_menu "ROS 2 Management" "Robot Operating System 2" "Status: ${status}

Select action:" 15 60 5 \
        "INSTALL" "Install ROS 2 (Humble/Jazzy)" \
        "UNINSTALL" "Uninstall ROS 2" \
        "BACK" "Back")

    case "${choice}" in
        "INSTALL")
            clear
            install_ros2_logic
            read -rp $'
Press Enter to continue...'
            ;;
        "UNINSTALL")
            if ui_confirm "Are you sure you want to uninstall ROS 2?" "Confirm Uninstall"; then
                clear
                uninstall_ros2_logic
                read -rp $'
Press Enter to continue...'
            fi
            ;;
    esac
}
